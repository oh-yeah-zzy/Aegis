"""
权限管理端点

提供权限的 CRUD 操作
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_permissions
from app.db.models.user import User
from app.db.models.role import Permission
from app.schemas.role import PermissionCreate, PermissionUpdate, PermissionResponse

router = APIRouter(prefix="/permissions", tags=["权限管理"])


@router.get("", response_model=list[PermissionResponse], summary="获取权限列表")
async def list_permissions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:permissions:read"]))],
    search: Optional[str] = Query(default=None, description="搜索关键词"),
    service_code: Optional[str] = Query(default=None, description="服务码过滤"),
):
    """
    获取权限列表
    """
    query = select(Permission)

    if search:
        query = query.where(
            Permission.code.ilike(f"%{search}%")
            | Permission.name.ilike(f"%{search}%")
        )

    if service_code:
        query = query.where(Permission.service_code == service_code)

    query = query.order_by(Permission.code)

    result = await db.execute(query)
    permissions = result.scalars().all()

    return [
        PermissionResponse(
            id=p.id,
            code=p.code,
            name=p.name,
            description=p.description,
            service_code=p.service_code,
            resource=p.resource,
            action=p.action,
            created_at=p.created_at,
        )
        for p in permissions
    ]


@router.post(
    "", response_model=PermissionResponse, status_code=201, summary="创建权限"
)
async def create_permission(
    data: PermissionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:permissions:write"]))],
):
    """
    创建新权限
    """
    # 检查权限码是否已存在
    result = await db.execute(select(Permission).where(Permission.code == data.code))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="权限码已存在",
        )

    # 创建权限
    permission = Permission(
        code=data.code,
        name=data.name,
        description=data.description,
        service_code=data.service_code,
        resource=data.resource,
        action=data.action,
    )
    db.add(permission)
    await db.commit()
    await db.refresh(permission)

    return PermissionResponse(
        id=permission.id,
        code=permission.code,
        name=permission.name,
        description=permission.description,
        service_code=permission.service_code,
        resource=permission.resource,
        action=permission.action,
        created_at=permission.created_at,
    )


@router.get(
    "/{permission_id}", response_model=PermissionResponse, summary="获取权限详情"
)
async def get_permission(
    permission_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:permissions:read"]))],
):
    """
    获取权限详情
    """
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    permission = result.scalar_one_or_none()

    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在",
        )

    return PermissionResponse(
        id=permission.id,
        code=permission.code,
        name=permission.name,
        description=permission.description,
        service_code=permission.service_code,
        resource=permission.resource,
        action=permission.action,
        created_at=permission.created_at,
    )


@router.patch(
    "/{permission_id}", response_model=PermissionResponse, summary="更新权限"
)
async def update_permission(
    permission_id: str,
    data: PermissionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:permissions:write"]))],
):
    """
    更新权限
    """
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    permission = result.scalar_one_or_none()

    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在",
        )

    # 更新字段
    if data.name is not None:
        permission.name = data.name
    if data.description is not None:
        permission.description = data.description
    if data.service_code is not None:
        permission.service_code = data.service_code
    if data.resource is not None:
        permission.resource = data.resource
    if data.action is not None:
        permission.action = data.action

    await db.commit()
    await db.refresh(permission)

    return PermissionResponse(
        id=permission.id,
        code=permission.code,
        name=permission.name,
        description=permission.description,
        service_code=permission.service_code,
        resource=permission.resource,
        action=permission.action,
        created_at=permission.created_at,
    )


@router.delete("/{permission_id}", status_code=204, summary="删除权限")
async def delete_permission(
    permission_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:permissions:delete"]))],
):
    """
    删除权限
    """
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    permission = result.scalar_one_or_none()

    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在",
        )

    await db.delete(permission)
    await db.commit()
