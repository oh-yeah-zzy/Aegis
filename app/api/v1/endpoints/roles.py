"""
角色管理端点

提供角色的 CRUD 操作
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, require_permissions
from app.db.models.user import User
from app.db.models.role import Role, Permission, RolePermission
from app.schemas.role import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    PermissionResponse,
)

router = APIRouter(prefix="/roles", tags=["角色管理"])


@router.get("", response_model=list[RoleResponse], summary="获取角色列表")
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:roles:read"]))],
    search: Optional[str] = Query(default=None, description="搜索关键词"),
):
    """
    获取角色列表
    """
    query = select(Role).options(
        selectinload(Role.role_permissions).selectinload(RolePermission.permission)
    )

    if search:
        query = query.where(
            Role.code.ilike(f"%{search}%") | Role.name.ilike(f"%{search}%")
        )

    query = query.order_by(Role.created_at.desc())

    result = await db.execute(query)
    roles = result.scalars().all()

    items = []
    for role in roles:
        permissions = [
            PermissionResponse(
                id=rp.permission.id,
                code=rp.permission.code,
                name=rp.permission.name,
                description=rp.permission.description,
                service_code=rp.permission.service_code,
                resource=rp.permission.resource,
                action=rp.permission.action,
                created_at=rp.permission.created_at,
            )
            for rp in role.role_permissions
        ]
        items.append(
            RoleResponse(
                id=role.id,
                code=role.code,
                name=role.name,
                description=role.description,
                is_system=role.is_system,
                created_at=role.created_at,
                permissions=permissions,
            )
        )

    return items


@router.post("", response_model=RoleResponse, status_code=201, summary="创建角色")
async def create_role(
    data: RoleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:roles:write"]))],
):
    """
    创建新角色
    """
    # 检查角色码是否已存在
    result = await db.execute(select(Role).where(Role.code == data.code))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色码已存在",
        )

    # 创建角色
    role = Role(
        code=data.code,
        name=data.name,
        description=data.description,
    )
    db.add(role)
    await db.flush()

    # 分配权限
    permissions = []
    if data.permission_ids:
        for permission_id in data.permission_ids:
            result = await db.execute(
                select(Permission).where(Permission.id == permission_id)
            )
            permission = result.scalar_one_or_none()
            if permission:
                role_permission = RolePermission(
                    role_id=role.id, permission_id=permission_id
                )
                db.add(role_permission)
                permissions.append(
                    PermissionResponse(
                        id=permission.id,
                        code=permission.code,
                        name=permission.name,
                        description=permission.description,
                        service_code=permission.service_code,
                        resource=permission.resource,
                        action=permission.action,
                        created_at=permission.created_at,
                    )
                )

    await db.commit()
    await db.refresh(role)

    return RoleResponse(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        created_at=role.created_at,
        permissions=permissions,
    )


@router.get("/{role_id}", response_model=RoleResponse, summary="获取角色详情")
async def get_role(
    role_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:roles:read"]))],
):
    """
    获取角色详情
    """
    result = await db.execute(
        select(Role)
        .where(Role.id == role_id)
        .options(
            selectinload(Role.role_permissions).selectinload(RolePermission.permission)
        )
    )
    role = result.scalar_one_or_none()

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在",
        )

    permissions = [
        PermissionResponse(
            id=rp.permission.id,
            code=rp.permission.code,
            name=rp.permission.name,
            description=rp.permission.description,
            service_code=rp.permission.service_code,
            resource=rp.permission.resource,
            action=rp.permission.action,
            created_at=rp.permission.created_at,
        )
        for rp in role.role_permissions
    ]

    return RoleResponse(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        created_at=role.created_at,
        permissions=permissions,
    )


@router.patch("/{role_id}", response_model=RoleResponse, summary="更新角色")
async def update_role(
    role_id: str,
    data: RoleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:roles:write"]))],
):
    """
    更新角色
    """
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在",
        )

    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系统角色不可修改",
        )

    # 更新字段
    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description

    # 更新权限
    if data.permission_ids is not None:
        # 删除现有权限
        result = await db.execute(
            select(RolePermission).where(RolePermission.role_id == role_id)
        )
        for rp in result.scalars().all():
            await db.delete(rp)

        # 添加新权限
        for permission_id in data.permission_ids:
            result = await db.execute(
                select(Permission).where(Permission.id == permission_id)
            )
            if result.scalar_one_or_none():
                role_permission = RolePermission(
                    role_id=role.id, permission_id=permission_id
                )
                db.add(role_permission)

    await db.commit()

    # 重新加载角色及其权限
    result = await db.execute(
        select(Role)
        .where(Role.id == role_id)
        .options(
            selectinload(Role.role_permissions).selectinload(RolePermission.permission)
        )
    )
    role = result.scalar_one()

    permissions = [
        PermissionResponse(
            id=rp.permission.id,
            code=rp.permission.code,
            name=rp.permission.name,
            description=rp.permission.description,
            service_code=rp.permission.service_code,
            resource=rp.permission.resource,
            action=rp.permission.action,
            created_at=rp.permission.created_at,
        )
        for rp in role.role_permissions
    ]

    return RoleResponse(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        created_at=role.created_at,
        permissions=permissions,
    )


@router.delete("/{role_id}", status_code=204, summary="删除角色")
async def delete_role(
    role_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:roles:delete"]))],
):
    """
    删除角色
    """
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在",
        )

    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系统角色不可删除",
        )

    await db.delete(role)
    await db.commit()
