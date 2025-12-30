"""
服务门户代理路由

处理 /s/{service_id}/ 格式的请求，动态代理到对应服务
"""

import re
from typing import Annotated, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.jwt import decode_token, TokenError
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.audit import AuditLog

router = APIRouter(tags=["服务代理"])
security = HTTPBearer(auto_error=False)

# 服务信息缓存（简单内存缓存）
_service_cache: dict = {}
_cache_timestamp: float = 0
CACHE_TTL = 30  # 缓存30秒


async def get_service_info(service_id: str) -> Optional[dict]:
    """
    从 ServiceAtlas 获取服务信息

    Args:
        service_id: 服务ID

    Returns:
        服务信息字典，包含 host, port, protocol 等
    """
    import time

    global _service_cache, _cache_timestamp

    # 检查缓存
    current_time = time.time()
    if current_time - _cache_timestamp < CACHE_TTL and service_id in _service_cache:
        return _service_cache.get(service_id)

    # 从 ServiceAtlas 获取
    if not settings.registry_enabled:
        return None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.registry_url}/api/v1/services/{service_id}",
                headers={"X-Gateway-ID": settings.registry_service_id},
            )

            if response.status_code == 200:
                service = response.json()
                # 更新缓存
                _service_cache[service_id] = service
                _cache_timestamp = current_time
                return service

    except Exception as e:
        print(f"[Portal Proxy] 获取服务信息失败: {e}")

    return _service_cache.get(service_id)  # 返回旧缓存（如果有）


@router.api_route(
    "/s/{service_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    summary="服务代理",
    include_in_schema=False,
)
async def service_proxy(
    request: Request,
    service_id: str,
    path: str,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """
    服务代理端点

    将 /s/{service_id}/xxx 的请求代理到对应服务的 /xxx
    """
    request_id = str(uuid4())
    full_path = f"/s/{service_id}/{path}"

    # 获取服务信息
    service = await get_service_info(service_id)

    if service is None:
        # 记录审计日志
        if settings.audit_log_enabled:
            audit_log = AuditLog(
                request_id=request_id,
                principal_type="anonymous",
                client_ip=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("user-agent"),
                method=request.method,
                host=request.url.netloc,
                path=full_path,
                query_string=request.url.query,
                status_code=404,
                latency_ms=0,
                decision="deny",
                deny_reason=f"服务不存在: {service_id}",
            )
            db.add(audit_log)
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"服务不存在: {service_id}",
        )

    # 验证用户认证（可选，根据需求配置）
    user = None
    principal_type = "anonymous"
    principal_id = None
    principal_label = None

    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            token_type = payload.get("type")

            if token_type == "access":
                subject = payload.get("sub", "")
                if not subject.startswith("service:"):
                    # 用户令牌
                    result = await db.execute(
                        select(User).where(User.id == subject)
                    )
                    user = result.scalar_one_or_none()

                    if user:
                        principal_type = "user"
                        principal_id = user.id
                        principal_label = user.username

        except TokenError:
            pass  # 忽略令牌错误，允许匿名访问（根据策略）

    # 构建上游 URL
    protocol = service.get("protocol", "http")
    host = service.get("host", "127.0.0.1")
    port = service.get("port", 80)
    upstream_url = f"{protocol}://{host}:{port}"

    # 构建目标路径
    target_path = f"/{path}" if path else "/"
    if request.url.query:
        target_path += f"?{request.url.query}"

    target_url = f"{upstream_url}{target_path}"

    # 准备请求头（headers 是不可变的，需要转换为 dict）
    headers = {k.lower(): v for k, v in request.headers.items()}
    # 移除 hop-by-hop 头
    for header in ["host", "connection", "keep-alive", "transfer-encoding", "upgrade", "content-length"]:
        headers.pop(header, None)

    # 添加代理标识
    headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"
    headers["X-Forwarded-Proto"] = request.url.scheme
    headers["X-Forwarded-Host"] = request.url.netloc
    headers["X-Request-ID"] = request_id
    headers["X-Proxy-By"] = "Aegis"

    # 如果有用户信息，添加到请求头
    if user:
        headers["X-User-ID"] = str(user.id)
        headers["X-User-Name"] = user.username

    import time
    start_time = time.time()

    try:
        # 获取请求体
        body = await request.body()

        # 发送代理请求
        async with httpx.AsyncClient(
            timeout=settings.gateway_timeout,
            follow_redirects=False,
        ) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )

        latency_ms = int((time.time() - start_time) * 1000)

        # 记录审计日志
        if settings.audit_log_enabled:
            audit_log = AuditLog(
                request_id=request_id,
                principal_type=principal_type,
                principal_id=principal_id,
                principal_label=principal_label,
                client_ip=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("user-agent"),
                method=request.method,
                host=request.url.netloc,
                path=full_path,
                query_string=request.url.query,
                upstream_service_id=service_id,  # 使用正确的字段名
                status_code=response.status_code,
                latency_ms=latency_ms,
                decision="allow",
            )
            db.add(audit_log)
            await db.commit()

        # 构建响应
        response_headers = dict(response.headers)
        # 移除 hop-by-hop 头
        for header in ["connection", "keep-alive", "transfer-encoding", "upgrade"]:
            response_headers.pop(header, None)

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get("content-type"),
        )

    except httpx.TimeoutException:
        latency_ms = int((time.time() - start_time) * 1000)

        if settings.audit_log_enabled:
            audit_log = AuditLog(
                request_id=request_id,
                principal_type=principal_type,
                principal_id=principal_id,
                principal_label=principal_label,
                client_ip=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("user-agent"),
                method=request.method,
                host=request.url.netloc,
                path=full_path,
                query_string=request.url.query,
                upstream_service_id=service_id,
                status_code=504,
                latency_ms=latency_ms,
                decision="error",
                deny_reason="上游服务超时",
            )
            db.add(audit_log)
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="上游服务响应超时",
        )

    except httpx.RequestError as e:
        latency_ms = int((time.time() - start_time) * 1000)

        if settings.audit_log_enabled:
            audit_log = AuditLog(
                request_id=request_id,
                principal_type=principal_type,
                principal_id=principal_id,
                principal_label=principal_label,
                client_ip=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("user-agent"),
                method=request.method,
                host=request.url.netloc,
                path=full_path,
                query_string=request.url.query,
                upstream_service_id=service_id,
                status_code=502,
                latency_ms=latency_ms,
                decision="error",
                deny_reason=str(e),
            )
            db.add(audit_log)
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"无法连接上游服务: {e}",
        )


# 处理根路径 /s/{service_id}/
@router.api_route(
    "/s/{service_id}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    summary="服务代理根路径",
    include_in_schema=False,
)
async def service_proxy_root(
    request: Request,
    service_id: str,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """服务代理根路径"""
    return await service_proxy(request, service_id, "", credentials, db)
