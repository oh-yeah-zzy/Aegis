"""
服务门户代理路由

处理 /s/{service_id}/ 格式的请求，动态代理到对应服务
"""

import re
from typing import Annotated, Optional
from urllib.parse import quote
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.jwt import decode_token, TokenError
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.audit import AuditLog
from app.gateway.policy import find_matching_auth_policy, AccessDecision
from app.core.rbac import check_permission, get_user_permissions

router = APIRouter(tags=["服务代理"])
security = HTTPBearer(auto_error=False)
templates = Jinja2Templates(directory="templates")


def is_browser_request(request: Request) -> bool:
    """判断是否为浏览器请求"""
    accept = request.headers.get("accept", "")
    return "text/html" in accept


def auth_error_response(
    request: Request,
    status_code: int,
    message: str,
    detail: str,
) -> Response:
    """
    根据请求类型返回适当的错误响应

    浏览器请求返回友好的 HTML 页面，API 请求返回 JSON
    """
    if is_browser_request(request):
        # 浏览器请求，返回友好的 HTML 页面
        redirect_url = quote(str(request.url), safe="")
        # 根据状态码确定错误类型
        error_type = "auth" if status_code == 401 else "forbidden"
        title = "需要登录" if status_code == 401 else "访问被拒绝"

        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "title": title,
                "error_type": error_type,
                "status_code": status_code,
                "message": message,
                "path": str(request.url.path),
                "redirect_url": redirect_url,
            },
            status_code=status_code,
        )
    else:
        # API 请求，抛出 HTTP 异常返回 JSON
        raise HTTPException(status_code=status_code, detail=detail)

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

    # 解析用户认证信息
    user = None
    is_service_request = False
    principal_type = "anonymous"
    principal_id = None
    principal_label = None

    # 获取 token：优先从 Authorization 头获取，其次从 Cookie 获取
    token = None
    if credentials:
        token = credentials.credentials
    elif request.cookies.get("access_token"):
        token = request.cookies.get("access_token")

    if token:
        try:
            payload = decode_token(token)
            token_type = payload.get("type")

            if token_type == "access":
                subject = payload.get("sub", "")
                if subject.startswith("service:"):
                    # 服务令牌
                    is_service_request = True
                    principal_type = "service"
                    principal_id = subject.replace("service:", "")
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
            # 令牌无效，继续作为匿名用户处理，后续策略检查会拒绝
            pass

    # 查找并检查认证策略
    policy = await find_matching_auth_policy(db, full_path)

    if not policy:
        # 没有匹配的策略，默认拒绝访问
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
                status_code=403,
                latency_ms=0,
                decision="deny",
                deny_reason="没有匹配的认证策略",
            )
            db.add(audit_log)
            await db.commit()

        return auth_error_response(
            request,
            status.HTTP_403_FORBIDDEN,
            "访问此资源需要配置认证策略，请联系管理员。",
            "没有匹配的认证策略，拒绝访问",
        )

    # 检查是否需要用户认证
    if policy.auth_required:
        if user is None and not is_service_request:
            if settings.audit_log_enabled:
                audit_log = AuditLog(
                    request_id=request_id,
                    principal_type=principal_type,
                    client_ip=request.client.host if request.client else "unknown",
                    user_agent=request.headers.get("user-agent"),
                    method=request.method,
                    host=request.url.netloc,
                    path=full_path,
                    query_string=request.url.query,
                    status_code=401,
                    latency_ms=0,
                    decision="deny",
                    deny_reason="需要用户认证",
                )
                db.add(audit_log)
                await db.commit()

            return auth_error_response(
                request,
                status.HTTP_401_UNAUTHORIZED,
                "访问此服务需要先登录，请使用您的账号登录后再试。",
                "需要用户认证",
            )

    # 检查是否需要服务间认证
    if policy.s2s_required:
        if not is_service_request:
            return auth_error_response(
                request,
                status.HTTP_403_FORBIDDEN,
                "此接口仅供内部服务调用，不支持直接访问。",
                "需要服务间认证",
            )

    # 检查权限
    required_permissions = [p.code for p in policy.permissions]
    if required_permissions:
        if user is None and not is_service_request:
            return auth_error_response(
                request,
                status.HTTP_401_UNAUTHORIZED,
                "访问此资源需要特定权限，请先登录。",
                "需要认证才能检查权限",
            )

        # 超级管理员跳过权限检查
        if user and not user.is_superuser:
            user_permissions = await get_user_permissions(db, user.id)
            has_permission = check_permission(
                user_permissions,
                required_permissions,
                policy.permission_mode,
            )

            if not has_permission:
                return auth_error_response(
                    request,
                    status.HTTP_403_FORBIDDEN,
                    f"您没有访问此资源的权限。所需权限: {', '.join(required_permissions)}",
                    f"缺少所需权限: {required_permissions}",
                )

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
