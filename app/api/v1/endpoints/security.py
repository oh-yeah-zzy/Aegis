"""
安全管理 API 端点

提供 IP 封禁管理和安全统计功能：
- IP 封禁列表查询
- 手动添加 IP 封禁
- 解除 IP 封禁
- 安全统计信息
- 速率限制状态查询
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_permissions
from app.core.rate_limiter import rate_limiter
from app.core.threat_detection import threat_detector
from app.core.security_config import security_settings
from app.db.models.user import User
from app.db.models.ip_ban import IPBanRecord
from app.db.models.audit import AuthEvent

router = APIRouter(prefix="/security", tags=["安全管理"])


# ============ 请求/响应模型 ============


class IPBanCreate(BaseModel):
    """创建 IP 封禁请求"""

    ip: str = Field(..., description="要封禁的 IP 地址", examples=["192.168.1.100"])
    reason: str = Field(..., description="封禁原因", examples=["恶意攻击"])
    duration_hours: Optional[int] = Field(
        None,
        description="封禁时长（小时），None 表示永久封禁",
        ge=1,
        le=8760,  # 最长 1 年
        examples=[24],
    )


class IPBanResponse(BaseModel):
    """IP 封禁记录响应"""

    id: str
    ip: str
    reason: str
    ban_type: str
    banned_at: datetime
    expires_at: Optional[datetime]
    created_by: Optional[str]
    unbanned_at: Optional[datetime]
    is_active: bool
    remaining_seconds: Optional[int]

    model_config = {"from_attributes": True}


class IPBanListResponse(BaseModel):
    """IP 封禁列表响应"""

    items: list[IPBanResponse]
    total: int
    page: int
    page_size: int


class UnbanRequest(BaseModel):
    """解除封禁请求"""

    reason: str = Field(..., description="解除封禁的原因", examples=["误封"])


class SecurityStatsResponse(BaseModel):
    """安全统计响应"""

    # 登录统计
    login_failures_24h: int = Field(description="过去 24 小时登录失败次数")
    login_failures_1h: int = Field(description="过去 1 小时登录失败次数")
    unique_failed_ips_24h: int = Field(description="过去 24 小时失败登录的不同 IP 数")

    # 封禁统计
    active_bans: int = Field(description="当前活跃的封禁数")
    auto_bans_24h: int = Field(description="过去 24 小时自动封禁次数")
    manual_bans_24h: int = Field(description="过去 24 小时手动封禁次数")

    # 速率限制统计
    rate_limit_stats: dict = Field(description="速率限制器统计")

    # 账户锁定统计
    locked_accounts: int = Field(description="当前被锁定的账户数")


class RateLimitStatsResponse(BaseModel):
    """速率限制统计响应"""

    total_keys: int
    total_records: int
    prefix_stats: dict
    last_cleanup: str


# ============ API 端点 ============


@router.get(
    "/ip-bans",
    response_model=IPBanListResponse,
    summary="获取 IP 封禁列表",
)
async def list_ip_bans(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:security:read"]))],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    active_only: bool = Query(default=False, description="只显示活跃的封禁"),
    ip_filter: Optional[str] = Query(default=None, description="IP 地址过滤"),
    ban_type: Optional[str] = Query(default=None, description="封禁类型过滤"),
):
    """
    获取 IP 封禁记录列表

    需要权限：aegis:security:read
    """
    # 构建查询条件
    conditions = []

    if active_only:
        now = datetime.now(timezone.utc)
        conditions.append(IPBanRecord.unbanned_at.is_(None))
        conditions.append(
            or_(
                IPBanRecord.expires_at.is_(None),
                IPBanRecord.expires_at > now,
            )
        )

    if ip_filter:
        conditions.append(IPBanRecord.ip.contains(ip_filter))

    if ban_type:
        conditions.append(IPBanRecord.ban_type == ban_type)

    # 查询总数
    count_query = select(func.count(IPBanRecord.id))
    if conditions:
        count_query = count_query.where(*conditions)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 查询列表
    query = (
        select(IPBanRecord)
        .order_by(IPBanRecord.banned_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if conditions:
        query = query.where(*conditions)

    result = await db.execute(query)
    records = result.scalars().all()

    return IPBanListResponse(
        items=[
            IPBanResponse(
                id=r.id,
                ip=r.ip,
                reason=r.reason,
                ban_type=r.ban_type,
                banned_at=r.banned_at,
                expires_at=r.expires_at,
                created_by=r.created_by,
                unbanned_at=r.unbanned_at,
                is_active=r.is_active,
                remaining_seconds=r.remaining_seconds,
            )
            for r in records
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/ip-bans",
    response_model=IPBanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="添加 IP 封禁",
)
async def create_ip_ban(
    data: IPBanCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(["aegis:security:write"]))],
):
    """
    手动添加 IP 封禁

    需要权限：aegis:security:write
    """
    now = datetime.now(timezone.utc)

    # 检查是否已有活跃的封禁
    existing = await db.execute(
        select(IPBanRecord).where(
            IPBanRecord.ip == data.ip,
            IPBanRecord.unbanned_at.is_(None),
            or_(
                IPBanRecord.expires_at.is_(None),
                IPBanRecord.expires_at > now,
            ),
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"IP {data.ip} 已被封禁",
        )

    # 计算过期时间
    expires_at = None
    if data.duration_hours:
        expires_at = now + timedelta(hours=data.duration_hours)

    # 创建封禁记录
    record = IPBanRecord(
        ip=data.ip,
        reason=data.reason,
        ban_type="manual",
        banned_at=now,
        expires_at=expires_at,
        created_by=current_user.id,
    )
    db.add(record)

    # 记录审计事件
    event = AuthEvent(
        event_type="ip_manual_banned",
        principal_type="user",
        principal_id=current_user.id,
        ip=data.ip,
        result="success",
        details={
            "reason": data.reason,
            "duration_hours": data.duration_hours,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "ban_record_id": record.id,
        },
    )
    db.add(event)

    await db.commit()
    await db.refresh(record)

    return IPBanResponse(
        id=record.id,
        ip=record.ip,
        reason=record.reason,
        ban_type=record.ban_type,
        banned_at=record.banned_at,
        expires_at=record.expires_at,
        created_by=record.created_by,
        unbanned_at=record.unbanned_at,
        is_active=record.is_active,
        remaining_seconds=record.remaining_seconds,
    )


@router.delete(
    "/ip-bans/{ban_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="解除 IP 封禁",
)
async def delete_ip_ban(
    ban_id: str,
    data: UnbanRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(["aegis:security:write"]))],
):
    """
    解除 IP 封禁

    需要权限：aegis:security:write
    """
    # 查找封禁记录
    result = await db.execute(
        select(IPBanRecord).where(IPBanRecord.id == ban_id)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="封禁记录不存在",
        )

    if record.unbanned_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该封禁已被解除",
        )

    # 解除封禁
    record.unbanned_at = datetime.now(timezone.utc)
    record.unbanned_by = current_user.id
    record.unban_reason = data.reason

    # 记录审计事件
    event = AuthEvent(
        event_type="ip_unbanned",
        principal_type="user",
        principal_id=current_user.id,
        ip=record.ip,
        result="success",
        details={
            "unban_reason": data.reason,
            "ban_record_id": record.id,
            "original_reason": record.reason,
        },
    )
    db.add(event)

    await db.commit()


@router.get(
    "/stats",
    response_model=SecurityStatsResponse,
    summary="获取安全统计",
)
async def get_security_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:security:read"]))],
):
    """
    获取安全相关的统计信息

    需要权限：aegis:security:read
    """
    now = datetime.now(timezone.utc)
    time_24h_ago = now - timedelta(hours=24)
    time_1h_ago = now - timedelta(hours=1)

    # 登录失败统计（24小时）
    login_failures_24h = await db.execute(
        select(func.count(AuthEvent.id)).where(
            AuthEvent.event_type == "login",
            AuthEvent.result == "failure",
            AuthEvent.ts >= time_24h_ago,
        )
    )

    # 登录失败统计（1小时）
    login_failures_1h = await db.execute(
        select(func.count(AuthEvent.id)).where(
            AuthEvent.event_type == "login",
            AuthEvent.result == "failure",
            AuthEvent.ts >= time_1h_ago,
        )
    )

    # 不同失败 IP 数
    unique_failed_ips = await db.execute(
        select(func.count(func.distinct(AuthEvent.ip))).where(
            AuthEvent.event_type == "login",
            AuthEvent.result == "failure",
            AuthEvent.ts >= time_24h_ago,
        )
    )

    # 活跃封禁数
    active_bans = await db.execute(
        select(func.count(IPBanRecord.id)).where(
            IPBanRecord.unbanned_at.is_(None),
            or_(
                IPBanRecord.expires_at.is_(None),
                IPBanRecord.expires_at > now,
            ),
        )
    )

    # 自动封禁数（24小时）
    auto_bans = await db.execute(
        select(func.count(IPBanRecord.id)).where(
            IPBanRecord.ban_type.like("auto_%"),
            IPBanRecord.banned_at >= time_24h_ago,
        )
    )

    # 手动封禁数（24小时）
    manual_bans = await db.execute(
        select(func.count(IPBanRecord.id)).where(
            IPBanRecord.ban_type == "manual",
            IPBanRecord.banned_at >= time_24h_ago,
        )
    )

    # 锁定账户数
    locked_accounts = await db.execute(
        select(func.count(User.id)).where(
            User.locked_until.isnot(None),
            User.locked_until > now,
        )
    )

    # 速率限制统计
    rate_limit_stats = await rate_limiter.get_stats()

    return SecurityStatsResponse(
        login_failures_24h=login_failures_24h.scalar() or 0,
        login_failures_1h=login_failures_1h.scalar() or 0,
        unique_failed_ips_24h=unique_failed_ips.scalar() or 0,
        active_bans=active_bans.scalar() or 0,
        auto_bans_24h=auto_bans.scalar() or 0,
        manual_bans_24h=manual_bans.scalar() or 0,
        rate_limit_stats=rate_limit_stats,
        locked_accounts=locked_accounts.scalar() or 0,
    )


@router.get(
    "/config",
    summary="获取安全配置（脱敏）",
)
async def get_security_config(
    _: Annotated[User, Depends(require_permissions(["aegis:security:read"]))],
):
    """
    获取当前安全配置（脱敏版本）

    需要权限：aegis:security:read
    """
    return {
        "rate_limit": {
            "enabled": security_settings.rate_limit_enabled,
            "login_max": security_settings.rate_limit_login_max,
            "login_window": security_settings.rate_limit_login_window,
            "global_max": security_settings.rate_limit_global_max,
            "global_window": security_settings.rate_limit_global_window,
        },
        "account_lockout": {
            "enabled": security_settings.account_lockout_enabled,
            "threshold": security_settings.account_lockout_threshold,
            "duration": security_settings.account_lockout_duration,
        },
        "ip_management": {
            "whitelist_enabled": security_settings.ip_whitelist_enabled,
            "blacklist_enabled": security_settings.ip_blacklist_enabled,
            "auto_ban_enabled": security_settings.ip_auto_ban_enabled,
            "auto_ban_threshold": security_settings.ip_auto_ban_threshold,
            "auto_ban_duration": security_settings.ip_auto_ban_duration,
        },
        "threat_detection": {
            "enabled": security_settings.threat_detection_enabled,
            "brute_force_threshold": security_settings.threat_brute_force_threshold,
            "credential_stuffing_threshold": security_settings.threat_credential_stuffing_threshold,
        },
        "security_headers": {
            "enabled": security_settings.security_headers_enabled,
        },
    }


@router.post(
    "/unlock-account/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="解锁用户账户",
)
async def unlock_account(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(["aegis:security:write"]))],
):
    """
    手动解锁被锁定的用户账户

    需要权限：aegis:security:write
    """
    # 查找用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    if not user.locked_until:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户账户未被锁定",
        )

    # 解锁账户
    user.locked_until = None
    user.failed_login_attempts = 0

    # 记录审计事件
    event = AuthEvent(
        event_type="account_unlocked",
        principal_type="user",
        principal_id=current_user.id,
        ip="",
        result="success",
        details={
            "unlocked_user_id": user.id,
            "unlocked_username": user.username,
        },
    )
    db.add(event)

    await db.commit()
