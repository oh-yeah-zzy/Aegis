"""
代理转发模块

将请求转发到上游服务
支持本地路由（Route）和远程路由（RemoteRoute）
"""

import time
from typing import Optional, Union
from uuid import uuid4

import httpx
from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.route import Route
from app.db.models.audit import AuditLog
from app.gateway.matcher import build_upstream_url
from app.core.registry import RemoteRoute


class ProxyError(Exception):
    """代理错误"""

    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def proxy_request(
    request: Request,
    route: Union[Route, RemoteRoute],
    db: AsyncSession,
    principal_type: str = "anonymous",
    principal_id: Optional[str] = None,
    principal_label: Optional[str] = None,
) -> Response:
    """
    代理转发请求到上游服务

    Args:
        request: FastAPI 请求对象
        route: 匹配的路由（Route 或 RemoteRoute）
        db: 数据库会话
        principal_type: 主体类型
        principal_id: 主体ID
        principal_label: 主体标签

    Returns:
        响应对象
    """
    request_id = str(uuid4())
    start_time = time.time()

    # 判断路由类型，获取相应的配置
    is_remote_route = isinstance(route, RemoteRoute)
    if is_remote_route:
        # 远程路由使用默认配置
        timeout_ms = settings.gateway_timeout * 1000
        retry_count = settings.gateway_max_retries
        upstream_service_id = route.target_service_id
    else:
        # 本地路由使用路由配置
        timeout_ms = route.timeout_ms
        retry_count = route.retry_count
        upstream_service_id = route.upstream_service_id

    # 构建上游 URL
    upstream_url = build_upstream_url(route, request.url.path)
    if request.url.query:
        upstream_url += f"?{request.url.query}"

    # 准备请求头
    headers = dict(request.headers)
    # 移除 hop-by-hop 头
    hop_by_hop = [
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    ]
    for header in hop_by_hop:
        headers.pop(header, None)

    # 添加请求追踪头
    headers["X-Request-ID"] = request_id
    headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"
    headers["X-Forwarded-Proto"] = request.url.scheme
    headers["X-Forwarded-Host"] = request.url.netloc

    # 添加主体信息头（供上游服务使用）
    if principal_id:
        headers["X-Principal-Type"] = principal_type
        headers["X-Principal-ID"] = principal_id
        if principal_label:
            headers["X-Principal-Label"] = principal_label

    # 读取请求体
    body = await request.body()

    # 发送请求
    status_code = 502
    response_headers = {}
    response_body = b""
    error_message = None

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_ms / 1000)
        ) as client:
            # 支持重试
            last_error = None
            for attempt in range(retry_count + 1):
                try:
                    upstream_response = await client.request(
                        method=request.method,
                        url=upstream_url,
                        headers=headers,
                        content=body,
                        follow_redirects=False,
                    )
                    status_code = upstream_response.status_code
                    response_headers = dict(upstream_response.headers)
                    response_body = upstream_response.content
                    break
                except httpx.RequestError as e:
                    last_error = e
                    if attempt < retry_count:
                        continue
                    raise

            if last_error and status_code == 502:
                raise last_error

    except httpx.TimeoutException:
        status_code = 504
        error_message = "上游服务响应超时"
        response_body = b'{"error": "Gateway Timeout"}'
    except httpx.RequestError as e:
        status_code = 502
        error_message = f"上游服务连接失败: {str(e)}"
        response_body = b'{"error": "Bad Gateway"}'

    # 计算延迟
    latency_ms = int((time.time() - start_time) * 1000)

    # 记录审计日志
    if settings.audit_log_enabled:
        # 过滤敏感头
        safe_request_headers = {
            k: v
            for k, v in headers.items()
            if k.lower() not in settings.audit_log_sensitive_fields
        }
        safe_response_headers = {
            k: v
            for k, v in response_headers.items()
            if k.lower() not in settings.audit_log_sensitive_fields
        }

        audit_log = AuditLog(
            request_id=request_id,
            principal_type=principal_type,
            principal_id=principal_id,
            principal_label=principal_label,
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent"),
            method=request.method,
            host=request.url.netloc,
            path=request.url.path,
            query_string=request.url.query,
            route_id=route.id,
            upstream_service_id=upstream_service_id,
            status_code=status_code,
            latency_ms=latency_ms,
            decision="allow",
            request_headers=safe_request_headers,
            response_headers=safe_response_headers,
            request_bytes=len(body),
            response_bytes=len(response_body),
            error=error_message,
        )
        db.add(audit_log)
        await db.commit()

    # 构建响应
    # 移除一些不需要转发的响应头
    for header in ["content-encoding", "content-length", "transfer-encoding"]:
        response_headers.pop(header, None)

    return Response(
        content=response_body,
        status_code=status_code,
        headers=response_headers,
    )
