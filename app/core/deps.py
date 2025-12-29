"""
FastAPI 依赖注入模块

提供认证、权限检查等通用依赖
"""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.jwt import TokenError, decode_token
from app.core.rbac import get_user_permissions, get_user_roles, check_permission
from app.db.session import get_db
from app.db.models.user import User
from app.schemas.auth import CurrentUser

# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    获取当前用户（必须认证）

    从 Authorization 头解析 JWT，验证并返回用户对象

    Raises:
        HTTPException: 未认证或认证失败
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # 解码令牌
        payload = decode_token(credentials.credentials)

        # 检查令牌类型
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌类型无效",
            )

        # 获取用户ID
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌缺少用户信息",
            )

        # 查询用户
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户已被禁用",
            )

        # 检查令牌版本（用于使所有令牌失效）
        token_version = payload.get("token_version", 0)
        if token_version < user.token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌已失效，请重新登录",
            )

        return user

    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Optional[User]:
    """
    获取当前用户（可选认证）

    如果提供了令牌则验证，否则返回 None
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(request, credentials, db)
    except HTTPException:
        return None


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    return current_user


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """获取当前超级管理员用户"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限",
        )
    return current_user


def require_permissions(
    permissions: list[str],
    mode: str = "any",
):
    """
    权限检查依赖工厂

    Args:
        permissions: 所需权限列表
        mode: 权限模式，"any" 或 "all"

    Returns:
        依赖函数
    """

    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        # 超级管理员跳过检查
        if current_user.is_superuser:
            return current_user

        # 获取用户权限
        user_permissions = await get_user_permissions(db, current_user.id)

        # 检查权限
        if not check_permission(user_permissions, permissions, mode):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少所需权限: {permissions}",
            )

        return current_user

    return permission_checker


async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """
    获取当前用户完整信息（包含角色和权限）
    """
    roles = await get_user_roles(db, current_user.id)
    permissions = await get_user_permissions(db, current_user.id)

    return CurrentUser(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        roles=list(roles),
        permissions=list(permissions),
    )
