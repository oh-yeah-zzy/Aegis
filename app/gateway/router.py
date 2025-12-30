"""
网关路由

处理所有需要代理转发的请求
"""

from typing import Annotated, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.jwt import decode_token, TokenError
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.audit import AuditLog
from app.gateway.matcher import find_matching_route
from app.gateway.policy import evaluate_access
from app.gateway.proxy import proxy_request

router = APIRouter(tags=["网关"])
security = HTTPBearer(auto_error=False)


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    summary="网关代理",
    include_in_schema=False,  # 不在 OpenAPI 文档中显示
)
async def gateway_proxy(
    request: Request,
    path: str,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """
    网关代理端点

    处理所有需要代理转发的请求：
    1. 匹配路由规则
    2. 验证认证信息
    3. 检查访问权限
    4. 转发请求到上游服务
    5. 记录审计日志

    注意：此路由必须在所有其他路由之后注册，作为兜底路由
    """
    request_id = str(uuid4())
    full_path = f"/{path}"

    # 获取请求信息
    method = request.method
    host = request.url.netloc

    # 查找匹配的路由
    route = await find_matching_route(db, method, host, full_path)

    if route is None:
        # 没有匹配的路由，返回 404
        # 记录审计日志
        if settings.audit_log_enabled:
            audit_log = AuditLog(
                request_id=request_id,
                principal_type="anonymous",
                client_ip=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("user-agent"),
                method=method,
                host=host,
                path=full_path,
                query_string=request.url.query,
                status_code=404,
                latency_ms=0,
                decision="deny",
                deny_reason="没有匹配的路由",
            )
            db.add(audit_log)
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="路由不存在",
        )

    # 解析认证信息
    user = None
    service_id = None
    is_service_request = False
    principal_type = "anonymous"
    principal_id = None
    principal_label = None

    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            token_type = payload.get("type")

            if token_type == "access":
                # 检查是否为服务令牌
                subject = payload.get("sub", "")
                if subject.startswith("service:"):
                    is_service_request = True
                    service_id = subject.replace("service:", "")
                    principal_type = "service"
                    principal_id = service_id
                    principal_label = payload.get("service_code")
                else:
                    # 用户令牌
                    result = await db.execute(
                        select(User).where(User.id == subject)
                    )
                    user = result.scalar_one_or_none()

                    if user:
                        # 检查令牌版本
                        token_version = payload.get("token_version", 0)
                        if token_version < user.token_version:
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="令牌已失效",
                            )

                        principal_type = "user"
                        principal_id = user.id
                        principal_label = user.username

        except TokenError as e:
            if route.auth_required or route.s2s_required:
                # 记录审计日志
                if settings.audit_log_enabled:
                    audit_log = AuditLog(
                        request_id=request_id,
                        principal_type="anonymous",
                        client_ip=request.client.host if request.client else "unknown",
                        user_agent=request.headers.get("user-agent"),
                        method=method,
                        host=host,
                        path=full_path,
                        query_string=request.url.query,
                        route_id=route.id,
                        status_code=401,
                        latency_ms=0,
                        decision="deny",
                        deny_reason=str(e),
                    )
                    db.add(audit_log)
                    await db.commit()

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(e),
                )

    # 评估访问权限
    decision = await evaluate_access(
        db=db,
        route=route,
        user=user,
        service_id=service_id,
        is_service_request=is_service_request,
        request_path=full_path,
    )

    if not decision.allowed:
        # 记录审计日志
        if settings.audit_log_enabled:
            audit_log = AuditLog(
                request_id=request_id,
                principal_type=principal_type,
                principal_id=principal_id,
                principal_label=principal_label,
                client_ip=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("user-agent"),
                method=method,
                host=host,
                path=full_path,
                query_string=request.url.query,
                route_id=route.id,
                status_code=403,
                latency_ms=0,
                decision="deny",
                deny_reason=decision.reason,
            )
            db.add(audit_log)
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=decision.reason,
        )

    # 代理转发请求
    return await proxy_request(
        request=request,
        route=route,
        db=db,
        principal_type=principal_type,
        principal_id=principal_id,
        principal_label=principal_label,
    )
