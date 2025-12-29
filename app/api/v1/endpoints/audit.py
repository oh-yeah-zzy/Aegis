"""
审计日志端点

提供审计日志查询功能
"""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_permissions
from app.db.models.user import User
from app.db.models.audit import AuditLog, AuthEvent
from pydantic import BaseModel

router = APIRouter(prefix="/audit", tags=["审计日志"])


class AuditLogResponse(BaseModel):
    """审计日志响应"""

    id: str
    ts: datetime
    request_id: str
    principal_type: str
    principal_id: Optional[str] = None
    principal_label: Optional[str] = None
    client_ip: str
    method: str
    host: str
    path: str
    route_id: Optional[str] = None
    status_code: int
    latency_ms: int
    decision: str
    deny_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class AuthEventResponse(BaseModel):
    """认证事件响应"""

    id: str
    ts: datetime
    event_type: str
    principal_type: str
    principal_id: Optional[str] = None
    ip: str
    result: str
    failure_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """审计日志列表响应"""

    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class AuthEventListResponse(BaseModel):
    """认证事件列表响应"""

    items: list[AuthEventResponse]
    total: int
    page: int
    page_size: int


@router.get("/logs", response_model=AuditLogListResponse, summary="获取审计日志")
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:audit:read"]))],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    principal_type: Optional[str] = Query(default=None, description="主体类型过滤"),
    principal_id: Optional[str] = Query(default=None, description="主体ID过滤"),
    decision: Optional[str] = Query(default=None, description="决策结果过滤"),
    start_time: Optional[datetime] = Query(default=None, description="开始时间"),
    end_time: Optional[datetime] = Query(default=None, description="结束时间"),
):
    """
    获取审计日志列表

    支持分页和多种过滤条件
    """
    query = select(AuditLog)

    if principal_type:
        query = query.where(AuditLog.principal_type == principal_type)
    if principal_id:
        query = query.where(AuditLog.principal_id == principal_id)
    if decision:
        query = query.where(AuditLog.decision == decision)
    if start_time:
        query = query.where(AuditLog.ts >= start_time)
    if end_time:
        query = query.where(AuditLog.ts <= end_time)

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(desc(AuditLog.ts))

    result = await db.execute(query)
    logs = result.scalars().all()

    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                ts=log.ts,
                request_id=log.request_id,
                principal_type=log.principal_type,
                principal_id=log.principal_id,
                principal_label=log.principal_label,
                client_ip=log.client_ip,
                method=log.method,
                host=log.host,
                path=log.path,
                route_id=log.route_id,
                status_code=log.status_code,
                latency_ms=log.latency_ms,
                decision=log.decision,
                deny_reason=log.deny_reason,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/events", response_model=AuthEventListResponse, summary="获取认证事件")
async def list_auth_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:audit:read"]))],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    event_type: Optional[str] = Query(default=None, description="事件类型过滤"),
    principal_id: Optional[str] = Query(default=None, description="主体ID过滤"),
    result: Optional[str] = Query(default=None, description="结果过滤"),
    start_time: Optional[datetime] = Query(default=None, description="开始时间"),
    end_time: Optional[datetime] = Query(default=None, description="结束时间"),
):
    """
    获取认证事件列表

    包括登录、登出、令牌刷新等事件
    """
    query = select(AuthEvent)

    if event_type:
        query = query.where(AuthEvent.event_type == event_type)
    if principal_id:
        query = query.where(AuthEvent.principal_id == principal_id)
    if result:
        query = query.where(AuthEvent.result == result)
    if start_time:
        query = query.where(AuthEvent.ts >= start_time)
    if end_time:
        query = query.where(AuthEvent.ts <= end_time)

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(desc(AuthEvent.ts))

    result_query = await db.execute(query)
    events = result_query.scalars().all()

    return AuthEventListResponse(
        items=[
            AuthEventResponse(
                id=event.id,
                ts=event.ts,
                event_type=event.event_type,
                principal_type=event.principal_type,
                principal_id=event.principal_id,
                ip=event.ip,
                result=event.result,
                failure_reason=event.failure_reason,
            )
            for event in events
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
