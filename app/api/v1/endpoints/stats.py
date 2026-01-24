"""
统计数据端点

提供系统统计数据，用于仪表盘展示
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.deps import get_db, require_permissions
from app.db.models.user import User
from app.db.models.role import Role, Permission
from app.db.models.audit import AuthEvent

router = APIRouter(prefix="/stats", tags=["统计数据"])


class DashboardStatsResponse(BaseModel):
    """仪表盘统计数据响应"""

    total_users: int
    total_roles: int
    total_permissions: int
    today_logins: int


@router.get("/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:stats:read"]))],
):
    """
    获取仪表盘统计数据

    需要权限: aegis:stats:read

    返回:
    - total_users: 总用户数
    - total_roles: 总角色数
    - total_permissions: 总权限数
    - today_logins: 今日登录成功次数
    """
    # 统计总用户数
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar() or 0

    # 统计总角色数
    total_roles_result = await db.execute(select(func.count(Role.id)))
    total_roles = total_roles_result.scalar() or 0

    # 统计总权限数
    total_permissions_result = await db.execute(select(func.count(Permission.id)))
    total_permissions = total_permissions_result.scalar() or 0

    # 统计今日登录成功次数
    # 获取今天的开始时间（UTC 时区）
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    today_logins_result = await db.execute(
        select(func.count(AuthEvent.id)).where(
            AuthEvent.event_type == "login",
            AuthEvent.result == "success",
            AuthEvent.ts >= today_start,
        )
    )
    today_logins = today_logins_result.scalar() or 0

    return DashboardStatsResponse(
        total_users=total_users,
        total_roles=total_roles,
        total_permissions=total_permissions,
        today_logins=today_logins,
    )
