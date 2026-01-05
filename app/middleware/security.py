"""
安全中间件模块

包含多个安全相关的中间件：
- IPFilterMiddleware: IP 黑白名单过滤
- RequestSizeMiddleware: 请求体大小限制
- RateLimitMiddleware: 全局速率限制
- SecurityHeadersMiddleware: 安全响应头

中间件执行顺序（从外到内）：
1. IPFilterMiddleware - 最先执行，拦截黑名单 IP
2. RequestSizeMiddleware - 限制请求体大小
3. RateLimitMiddleware - 全局速率限制
4. SecurityHeadersMiddleware - 添加安全响应头
"""

from datetime import datetime, timezone
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.security_config import security_settings
from app.core.rate_limiter import rate_limiter


def get_client_ip(request: Request) -> str:
    """
    获取客户端真实 IP 地址

    支持代理场景，会检查以下头部：
    - X-Forwarded-For: 标准代理头，取第一个 IP（客户端真实 IP）
    - X-Real-IP: Nginx 常用头
    - 直接连接的 client.host

    Args:
        request: FastAPI 请求对象

    Returns:
        客户端 IP 地址字符串
    """
    # 优先从 X-Forwarded-For 获取（多级代理场景）
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For 格式: client, proxy1, proxy2
        # 取第一个即为客户端真实 IP
        return forwarded_for.split(",")[0].strip()

    # 其次从 X-Real-IP 获取（单级代理场景）
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # 最后使用直连 IP
    if request.client:
        return request.client.host

    return "unknown"


class IPFilterMiddleware(BaseHTTPMiddleware):
    """
    IP 过滤中间件

    执行顺序：最外层（最先执行）

    功能：
    - 白名单模式：只允许白名单中的 IP 访问
    - 黑名单模式：阻止黑名单和数据库中封禁的 IP

    配置：
    - ip_whitelist_enabled: 启用白名单模式
    - ip_whitelist: 白名单列表
    - ip_blacklist_enabled: 启用黑名单模式
    - ip_blacklist: 静态黑名单列表
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = get_client_ip(request)

        # 将客户端 IP 存储到 request.state，供后续使用
        request.state.client_ip = client_ip

        # 白名单模式：只允许白名单 IP
        if security_settings.ip_whitelist_enabled and security_settings.ip_whitelist:
            if not self._is_ip_in_list(client_ip, security_settings.ip_whitelist):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "访问被拒绝：IP 不在白名单中",
                        "error_code": "IP_NOT_IN_WHITELIST",
                    },
                )

        # 黑名单模式：阻止黑名单 IP
        if security_settings.ip_blacklist_enabled:
            # 检查静态黑名单
            if self._is_ip_in_list(client_ip, security_settings.ip_blacklist):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "访问被拒绝：IP 已被永久封禁",
                        "error_code": "IP_PERMANENTLY_BANNED",
                    },
                )

            # 检查数据库中的封禁记录
            is_banned, reason = await self._check_ip_banned(client_ip)
            if is_banned:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": f"访问被拒绝：{reason}",
                        "error_code": "IP_TEMPORARILY_BANNED",
                    },
                )

        return await call_next(request)

    def _is_ip_in_list(self, ip: str, ip_list: list) -> bool:
        """
        检查 IP 是否在列表中

        支持精确匹配和 CIDR 格式（简化实现）

        Args:
            ip: 要检查的 IP
            ip_list: IP 列表

        Returns:
            True 如果 IP 在列表中
        """
        # 简单实现：精确匹配
        # TODO: 可扩展支持 CIDR 格式（如 192.168.1.0/24）
        return ip in ip_list

    async def _check_ip_banned(self, ip: str) -> tuple[bool, str]:
        """
        检查 IP 是否在数据库封禁列表中

        Args:
            ip: 要检查的 IP

        Returns:
            (是否被封禁, 封禁原因)
        """
        try:
            from sqlalchemy import select
            from app.db.models.ip_ban import IPBanRecord
            from app.db.session import async_session_maker

            async with async_session_maker() as db:
                now = datetime.now(timezone.utc)
                result = await db.execute(
                    select(IPBanRecord).where(
                        IPBanRecord.ip == ip,
                        IPBanRecord.unbanned_at.is_(None),
                        (IPBanRecord.expires_at.is_(None)) | (IPBanRecord.expires_at > now),
                    ).limit(1)
                )
                record = result.scalar_one_or_none()

                if record:
                    return True, record.reason

            return False, ""

        except Exception as e:
            # 数据库查询失败不应阻止正常请求
            # 只记录日志，不拒绝请求
            import logging
            logging.getLogger(__name__).warning(f"IP 封禁检查失败: {e}")
            return False, ""


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """
    请求体大小限制中间件

    执行顺序：第二层

    功能：
    - 检查 Content-Length 头，拒绝过大的请求
    - 防止大请求造成的 DoS 攻击

    配置：
    - request_max_body_size: 最大请求体大小（字节）
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                size = int(content_length)
                max_size = security_settings.request_max_body_size

                if size > max_size:
                    max_size_mb = max_size // 1024 // 1024
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"请求体过大，最大允许 {max_size_mb}MB",
                            "error_code": "REQUEST_ENTITY_TOO_LARGE",
                            "max_size_bytes": max_size,
                            "actual_size_bytes": size,
                        },
                    )
            except ValueError:
                # Content-Length 不是有效数字，忽略
                pass

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    全局速率限制中间件

    执行顺序：第三层

    功能：
    - 限制单 IP 的全局请求频率
    - 返回标准的速率限制响应头

    配置：
    - rate_limit_enabled: 是否启用
    - rate_limit_global_max: 最大请求数
    - rate_limit_global_window: 时间窗口（秒）

    响应头：
    - X-RateLimit-Limit: 限制的请求数
    - X-RateLimit-Remaining: 剩余请求数
    - X-RateLimit-Reset: 重置时间（秒）
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 如果未启用速率限制，直接放行
        if not security_settings.rate_limit_enabled:
            return await call_next(request)

        # 获取客户端 IP
        client_ip = getattr(request.state, "client_ip", None) or get_client_ip(request)
        key = f"global:{client_ip}"

        # 检查速率限制
        allowed, remaining, reset_seconds = await rate_limiter.is_allowed(
            key,
            security_settings.rate_limit_global_max,
            security_settings.rate_limit_global_window,
        )

        if not allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "请求过于频繁，请稍后再试",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "retry_after": reset_seconds,
                },
            )
        else:
            response = await call_next(request)

        # 添加速率限制响应头
        response.headers["X-RateLimit-Limit"] = str(security_settings.rate_limit_global_max)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_seconds)

        if not allowed:
            response.headers["Retry-After"] = str(reset_seconds)

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全响应头中间件

    执行顺序：第四层（最内层，靠近业务逻辑）

    功能：
    - 添加各种安全相关的 HTTP 响应头
    - 防止点击劫持、XSS、MIME 嗅探等攻击

    配置：
    - security_headers_enabled: 是否启用
    - csp_policy: Content-Security-Policy
    - frame_options: X-Frame-Options
    - content_type_options: X-Content-Type-Options
    - xss_protection: X-XSS-Protection
    - referrer_policy: Referrer-Policy
    - hsts_max_age: HSTS max-age
    - permissions_policy: Permissions-Policy
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if not security_settings.security_headers_enabled:
            return response

        # Content-Security-Policy: 限制资源加载来源
        response.headers["Content-Security-Policy"] = security_settings.csp_policy

        # X-Frame-Options: 防止点击劫持
        response.headers["X-Frame-Options"] = security_settings.frame_options

        # X-Content-Type-Options: 防止 MIME 类型嗅探
        response.headers["X-Content-Type-Options"] = security_settings.content_type_options

        # X-XSS-Protection: XSS 过滤器（旧浏览器）
        response.headers["X-XSS-Protection"] = security_settings.xss_protection

        # Referrer-Policy: 控制 Referer 头的发送
        response.headers["Referrer-Policy"] = security_settings.referrer_policy

        # Permissions-Policy: 限制浏览器功能
        response.headers["Permissions-Policy"] = security_settings.permissions_policy

        # Strict-Transport-Security: 强制 HTTPS（仅在 HTTPS 连接时有效）
        # 通过代理时检查 X-Forwarded-Proto
        is_https = (
            request.url.scheme == "https"
            or request.headers.get("X-Forwarded-Proto") == "https"
        )
        if is_https:
            hsts_value = f"max-age={security_settings.hsts_max_age}"
            if security_settings.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            response.headers["Strict-Transport-Security"] = hsts_value

        return response
