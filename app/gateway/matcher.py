"""
路由匹配器

根据请求信息匹配路由规则
支持从 ServiceAtlas 获取远程路由规则，同时保留本地路由作为后备
"""

import fnmatch
import re
from typing import Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.route import Route, RoutePermission
from app.core.registry import fetch_remote_routes, RemoteRoute
from app.core.config import settings


class RouteMatcher:
    """路由匹配器"""

    @staticmethod
    def match_path(pattern: str, path: str) -> bool:
        """
        匹配路径

        支持的模式：
        - /api/v1/users - 精确匹配
        - /api/v1/users/* - 匹配一级子路径
        - /api/v1/** - 匹配所有子路径
        - /api/v1/users/{id} - 路径参数

        Args:
            pattern: 路径模式
            path: 请求路径

        Returns:
            是否匹配
        """
        # 将 ** 转换为正则表达式
        if "**" in pattern:
            regex_pattern = pattern.replace("**", ".*")
            regex_pattern = regex_pattern.replace("*", "[^/]*")
            regex_pattern = f"^{regex_pattern}$"
            return bool(re.match(regex_pattern, path))

        # 将 * 转换为 fnmatch 模式
        if "*" in pattern:
            return fnmatch.fnmatch(path, pattern)

        # 处理路径参数 {id}
        if "{" in pattern:
            regex_pattern = re.sub(r"\{[^}]+\}", r"[^/]+", pattern)
            regex_pattern = f"^{regex_pattern}$"
            return bool(re.match(regex_pattern, path))

        # 精确匹配
        return pattern == path

    @staticmethod
    def match_method(methods: str, method: str) -> bool:
        """
        匹配 HTTP 方法

        Args:
            methods: 允许的方法（逗号分隔或 *）
            method: 请求方法

        Returns:
            是否匹配
        """
        if methods == "*":
            return True

        allowed_methods = [m.strip().upper() for m in methods.split(",")]
        return method.upper() in allowed_methods

    @staticmethod
    def match_host(pattern: Optional[str], host: str) -> bool:
        """
        匹配 Host

        Args:
            pattern: Host 模式（None 表示匹配所有）
            host: 请求 Host

        Returns:
            是否匹配
        """
        if pattern is None or pattern == "*":
            return True

        # 支持通配符
        if "*" in pattern:
            return fnmatch.fnmatch(host, pattern)

        return pattern.lower() == host.lower()


async def find_matching_route(
    db: AsyncSession,
    method: str,
    host: str,
    path: str,
) -> Optional[Union[Route, RemoteRoute]]:
    """
    查找匹配的路由

    优先从 ServiceAtlas 获取远程路由规则，如果未启用或获取失败则使用本地路由

    Args:
        db: 数据库会话
        method: HTTP 方法
        host: 请求 Host
        path: 请求路径

    Returns:
        匹配的路由（可能是 Route 或 RemoteRoute），如果没有匹配则返回 None
    """
    matcher = RouteMatcher()

    # 优先尝试从 ServiceAtlas 获取路由规则
    if settings.registry_enabled:
        remote_routes = await fetch_remote_routes()

        if remote_routes:
            for route in remote_routes:
                # 远程路由只匹配路径（不支持 Host 和方法过滤，因为 ServiceAtlas 的路由模型较简单）
                if matcher.match_path(route.path_pattern, path):
                    return route

    # 如果远程路由未找到匹配，使用本地路由
    result = await db.execute(
        select(Route)
        .where(Route.enabled == True)
        .options(
            selectinload(Route.route_permissions).selectinload(RoutePermission.permission)
        )
        .order_by(Route.priority.desc())
    )
    routes = result.scalars().all()

    for route in routes:
        # 检查 Host
        if not matcher.match_host(route.host, host):
            continue

        # 检查路径
        if not matcher.match_path(route.path_pattern, path):
            continue

        # 检查方法
        if not matcher.match_method(route.methods, method):
            continue

        return route

    return None


def build_upstream_url(route: Union[Route, RemoteRoute], path: str) -> str:
    """
    构建上游服务 URL

    Args:
        route: 匹配的路由（Route 或 RemoteRoute）
        path: 请求路径

    Returns:
        上游服务 URL
    """
    # 判断是远程路由还是本地路由
    if isinstance(route, RemoteRoute):
        # 远程路由：使用目标服务的 base_url
        upstream_url = route.target_service.base_url

        # 处理路径前缀剥离
        upstream_path = path
        if route.strip_prefix and route.strip_path:
            prefix = route.strip_path.rstrip("/")
            if path.startswith(prefix):
                upstream_path = path[len(prefix):] or "/"

        return upstream_url.rstrip("/") + upstream_path
    else:
        # 本地路由：使用 upstream_url
        upstream_url = route.upstream_url or ""

        # 处理路径前缀剥离
        upstream_path = path
        if route.strip_prefix and route.path_pattern:
            # 提取前缀（去除通配符部分）
            prefix = route.path_pattern.split("*")[0].rstrip("/")
            if path.startswith(prefix):
                upstream_path = path[len(prefix):] or "/"

        # 添加上游路径前缀
        if route.upstream_path_prefix:
            upstream_path = route.upstream_path_prefix.rstrip("/") + upstream_path

        return upstream_url.rstrip("/") + upstream_path
