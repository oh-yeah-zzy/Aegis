"""
访问策略模块

实现网关的访问控制策略
支持本地路由（Route）和远程路由（RemoteRoute）
远程路由通过认证策略表（AuthPolicy）进行权限控制
"""

import fnmatch
import re
from typing import Optional, Union, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import check_permission, get_user_permissions
from app.db.models.user import User
from app.db.models.route import Route
from app.db.models.auth_policy import AuthPolicy
from app.core.registry import RemoteRoute


class AccessDecision:
    """访问决策"""

    def __init__(
        self,
        allowed: bool,
        reason: Optional[str] = None,
    ):
        self.allowed = allowed
        self.reason = reason


def match_path_pattern(pattern: str, path: str) -> bool:
    """
    路径模式匹配

    支持的模式：
    - /** 匹配所有路径
    - /prefix/** 匹配以 prefix 开头的所有路径
    - /prefix-*/** 匹配以 prefix- 开头的所有路径
    - /exact/path 精确匹配
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

    # 精确匹配
    return pattern == path


async def find_matching_auth_policy(
    db: AsyncSession,
    path: str,
) -> Optional[AuthPolicy]:
    """
    查找匹配的认证策略

    按优先级从高到低匹配

    Args:
        db: 数据库会话
        path: 请求路径

    Returns:
        匹配的认证策略，如果没有匹配则返回 None
    """
    # 查询所有启用的认证策略，按优先级排序
    result = await db.execute(
        select(AuthPolicy)
        .where(AuthPolicy.enabled == True)
        .order_by(AuthPolicy.priority.desc())
    )
    policies = result.scalars().all()

    for policy in policies:
        if match_path_pattern(policy.path_pattern, path):
            return policy

    return None


async def evaluate_access(
    db: AsyncSession,
    route: Union[Route, RemoteRoute],
    user: Optional[User] = None,
    service_id: Optional[str] = None,
    is_service_request: bool = False,
    request_path: Optional[str] = None,
) -> AccessDecision:
    """
    评估访问权限

    Args:
        db: 数据库会话
        route: 匹配的路由（Route 或 RemoteRoute）
        user: 当前用户（如果有）
        service_id: 服务ID（如果是服务间请求）
        is_service_request: 是否为服务间请求
        request_path: 请求路径（用于远程路由匹配认证策略）

    Returns:
        访问决策
    """
    # 远程路由（来自 ServiceAtlas）使用认证策略表进行权限控制
    if isinstance(route, RemoteRoute):
        return await _evaluate_remote_route_access(
            db=db,
            route=route,
            user=user,
            service_id=service_id,
            is_service_request=is_service_request,
            request_path=request_path or f"/{route.target_service_id}",
        )

    # 以下是本地路由的权限检查逻辑
    return await _evaluate_local_route_access(
        db=db,
        route=route,
        user=user,
        service_id=service_id,
        is_service_request=is_service_request,
    )


async def _evaluate_remote_route_access(
    db: AsyncSession,
    route: RemoteRoute,
    user: Optional[User],
    service_id: Optional[str],
    is_service_request: bool,
    request_path: str,
) -> AccessDecision:
    """评估远程路由的访问权限（使用认证策略表）"""

    # 查找匹配的认证策略
    policy = await find_matching_auth_policy(db, request_path)

    if not policy:
        # 没有匹配的策略，默认拒绝访问（安全优先）
        return AccessDecision(
            allowed=False,
            reason="没有匹配的认证策略，拒绝访问",
        )

    # 检查是否需要认证
    if policy.auth_required:
        if user is None and not is_service_request:
            return AccessDecision(
                allowed=False,
                reason="需要用户认证",
            )

    # 检查是否需要服务间认证
    if policy.s2s_required:
        if not is_service_request:
            return AccessDecision(
                allowed=False,
                reason="需要服务间认证",
            )

    # 检查权限
    required_permissions = [p.code for p in policy.permissions]

    if required_permissions:
        if user is None and not is_service_request:
            return AccessDecision(
                allowed=False,
                reason="需要认证才能检查权限",
            )

        # 超级管理员跳过权限检查
        if user and user.is_superuser:
            return AccessDecision(allowed=True)

        # 获取用户权限
        if user:
            user_permissions = await get_user_permissions(db, user.id)

            # 检查权限
            has_permission = check_permission(
                user_permissions,
                required_permissions,
                policy.permission_mode,
            )

            if not has_permission:
                return AccessDecision(
                    allowed=False,
                    reason=f"缺少所需权限: {required_permissions}",
                )

    return AccessDecision(allowed=True)


async def _evaluate_local_route_access(
    db: AsyncSession,
    route: Route,
    user: Optional[User],
    service_id: Optional[str],
    is_service_request: bool,
) -> AccessDecision:
    """评估本地路由的访问权限"""

    # 检查是否需要认证
    if route.auth_required:
        if user is None and not is_service_request:
            return AccessDecision(
                allowed=False,
                reason="需要用户认证",
            )

    # 检查是否需要服务间认证
    if route.s2s_required:
        if not is_service_request:
            return AccessDecision(
                allowed=False,
                reason="需要服务间认证",
            )

    # 检查权限
    required_permissions = [
        rp.permission.code for rp in route.route_permissions
    ]

    if required_permissions:
        if user is None and not is_service_request:
            return AccessDecision(
                allowed=False,
                reason="需要认证才能检查权限",
            )

        # 超级管理员跳过权限检查
        if user and user.is_superuser:
            return AccessDecision(allowed=True)

        # 获取用户权限
        if user:
            user_permissions = await get_user_permissions(db, user.id)

            # 检查权限
            has_permission = check_permission(
                user_permissions,
                required_permissions,
                route.permission_mode,
            )

            if not has_permission:
                return AccessDecision(
                    allowed=False,
                    reason=f"缺少所需权限: {required_permissions}",
                )

    return AccessDecision(allowed=True)
