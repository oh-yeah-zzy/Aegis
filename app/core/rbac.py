"""
RBAC 权限控制模块

提供基于角色的访问控制核心逻辑
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.user import User
from app.db.models.role import Role, Permission, RolePermission
from app.db.models.user_role import UserRole


async def get_user_permissions(
    db: AsyncSession,
    user_id: str,
) -> set[str]:
    """
    获取用户的所有权限码

    通过用户 -> 角色 -> 权限的关系链获取

    Args:
        db: 数据库会话
        user_id: 用户ID

    Returns:
        权限码集合
    """
    # 查询用户的所有角色关联的权限
    query = (
        select(Permission.code)
        .select_from(UserRole)
        .join(RolePermission, UserRole.role_id == RolePermission.role_id)
        .join(Permission, RolePermission.permission_id == Permission.id)
        .where(UserRole.user_id == user_id)
    )

    result = await db.execute(query)
    return set(result.scalars().all())


async def get_user_roles(
    db: AsyncSession,
    user_id: str,
) -> set[str]:
    """
    获取用户的所有角色码

    Args:
        db: 数据库会话
        user_id: 用户ID

    Returns:
        角色码集合
    """
    query = (
        select(Role.code)
        .select_from(UserRole)
        .join(Role, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )

    result = await db.execute(query)
    return set(result.scalars().all())


def check_permission(
    user_permissions: set[str],
    required_permissions: list[str],
    mode: str = "any",
) -> bool:
    """
    检查用户是否拥有所需权限

    Args:
        user_permissions: 用户拥有的权限集合
        required_permissions: 所需的权限列表
        mode: 权限模式，"any" 表示满足任一即可，"all" 表示需要满足所有

    Returns:
        是否通过权限检查
    """
    if not required_permissions:
        return True

    required_set = set(required_permissions)

    if mode == "all":
        # 需要满足所有权限
        return required_set.issubset(user_permissions)
    else:
        # 满足任一权限即可
        return bool(required_set & user_permissions)


def check_permission_with_wildcard(
    user_permissions: set[str],
    required_permission: str,
) -> bool:
    """
    检查权限（支持通配符）

    权限码格式：{service}:{resource}:{action}
    支持通配符：
    - aegis:* 匹配所有 aegis 服务的权限
    - aegis:users:* 匹配 aegis:users 下的所有操作
    - *:*:read 匹配所有服务的读取权限

    Args:
        user_permissions: 用户拥有的权限集合
        required_permission: 所需的权限

    Returns:
        是否通过权限检查
    """
    # 直接匹配
    if required_permission in user_permissions:
        return True

    # 解析权限码
    required_parts = required_permission.split(":")

    for user_perm in user_permissions:
        user_parts = user_perm.split(":")

        # 确保部分数量相同
        if len(user_parts) != len(required_parts):
            continue

        # 逐部分匹配
        matched = True
        for user_part, required_part in zip(user_parts, required_parts):
            if user_part != "*" and user_part != required_part:
                matched = False
                break

        if matched:
            return True

    return False


class PermissionChecker:
    """
    权限检查器

    用于 FastAPI 依赖注入的权限检查
    """

    def __init__(
        self,
        required_permissions: list[str],
        mode: str = "any",
        allow_superuser: bool = True,
    ):
        """
        初始化权限检查器

        Args:
            required_permissions: 所需权限列表
            mode: 权限模式，"any" 或 "all"
            allow_superuser: 是否允许超级管理员跳过权限检查
        """
        self.required_permissions = required_permissions
        self.mode = mode
        self.allow_superuser = allow_superuser

    async def __call__(
        self,
        user: User,
        db: AsyncSession,
    ) -> bool:
        """
        执行权限检查

        Args:
            user: 当前用户
            db: 数据库会话

        Returns:
            是否通过权限检查
        """
        # 超级管理员跳过检查
        if self.allow_superuser and user.is_superuser:
            return True

        # 获取用户权限
        user_permissions = await get_user_permissions(db, user.id)

        # 检查权限
        return check_permission(
            user_permissions,
            self.required_permissions,
            self.mode,
        )
