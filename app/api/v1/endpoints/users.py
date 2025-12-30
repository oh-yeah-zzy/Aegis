"""
用户管理端点

提供用户的 CRUD 操作
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, get_current_user, require_permissions
from app.core.security import hash_password
from app.core.rbac import get_user_roles
from app.db.models.user import User
from app.db.models.role import Role
from app.db.models.user_role import UserRole
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserListResponse

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", response_model=UserListResponse, summary="获取用户列表")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:users:read"]))],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(default=None, description="搜索关键词"),
    is_active: Optional[bool] = Query(default=None, description="是否启用"),
):
    """
    获取用户列表

    支持分页、搜索和过滤
    """
    # 构建查询
    query = select(User)

    if search:
        query = query.where(
            User.username.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        )

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(User.created_at.desc())

    result = await db.execute(query)
    users = result.scalars().all()

    # 获取每个用户的角色
    items = []
    for user in users:
        roles = await get_user_roles(db, user.id)
        user_response = UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
            roles=list(roles),
        )
        items.append(user_response)

    return UserListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=UserResponse, status_code=201, summary="创建用户")
async def create_user(
    data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:users:write"]))],
):
    """
    创建新用户
    """
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )

    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已存在",
        )

    # 创建用户
    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        is_active=data.is_active,
        is_superuser=data.is_superuser,
    )
    db.add(user)
    await db.flush()

    # 分配角色
    if data.role_ids:
        for role_id in data.role_ids:
            result = await db.execute(select(Role).where(Role.id == role_id))
            role = result.scalar_one_or_none()
            if role:
                user_role = UserRole(user_id=user.id, role_id=role_id)
                db.add(user_role)

    await db.commit()
    await db.refresh(user)

    roles = await get_user_roles(db, user.id)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        roles=list(roles),
    )


@router.get("/{user_id}", response_model=UserResponse, summary="获取用户详情")
async def get_user(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:users:read"]))],
):
    """
    获取用户详情
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    roles = await get_user_roles(db, user.id)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        roles=list(roles),
    )


@router.patch("/{user_id}", response_model=UserResponse, summary="更新用户")
async def update_user(
    user_id: str,
    data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:users:write"]))],
):
    """
    更新用户信息
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 更新字段
    if data.username is not None:
        # 检查用户名是否已被其他用户使用
        result = await db.execute(
            select(User).where(User.username == data.username, User.id != user_id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在",
            )
        user.username = data.username

    if data.email is not None:
        result = await db.execute(
            select(User).where(User.email == data.email, User.id != user_id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已存在",
            )
        user.email = data.email

    if data.password is not None:
        user.password_hash = hash_password(data.password)
        # 增加令牌版本，使所有令牌失效
        user.token_version += 1

    if data.is_active is not None:
        # 超级管理员不能被禁用
        if user.is_superuser and not data.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="超级管理员账户不能被禁用",
            )
        user.is_active = data.is_active

    if data.is_superuser is not None:
        # 超级管理员不能被取消超级管理员权限
        if user.is_superuser and not data.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能取消超级管理员权限",
            )
        user.is_superuser = data.is_superuser

    # 更新角色
    if data.role_ids is not None:
        # 删除现有角色
        await db.execute(
            select(UserRole).where(UserRole.user_id == user_id)
        )
        result = await db.execute(
            select(UserRole).where(UserRole.user_id == user_id)
        )
        for user_role in result.scalars().all():
            await db.delete(user_role)

        # 添加新角色
        for role_id in data.role_ids:
            result = await db.execute(select(Role).where(Role.id == role_id))
            role = result.scalar_one_or_none()
            if role:
                user_role = UserRole(user_id=user.id, role_id=role_id)
                db.add(user_role)

    await db.commit()
    await db.refresh(user)

    roles = await get_user_roles(db, user.id)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        roles=list(roles),
    )


@router.delete("/{user_id}", status_code=204, summary="删除用户")
async def delete_user(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(["aegis:users:delete"]))],
):
    """
    删除用户
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    await db.delete(user)
    await db.commit()
