"""
路由管理端点

提供网关路由规则的 CRUD 操作
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, require_permissions
from app.db.models.user import User
from app.db.models.role import Permission
from app.db.models.route import Route, RoutePermission
from app.schemas.route import RouteCreate, RouteUpdate, RouteResponse

router = APIRouter(prefix="/routes", tags=["路由管理"])


@router.get("", response_model=list[RouteResponse], summary="获取路由列表")
async def list_routes(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:routes:read"]))],
    enabled: Optional[bool] = Query(default=None, description="是否启用"),
):
    """
    获取路由列表
    """
    query = select(Route).options(
        selectinload(Route.route_permissions).selectinload(RoutePermission.permission)
    )

    if enabled is not None:
        query = query.where(Route.enabled == enabled)

    query = query.order_by(Route.priority.desc(), Route.created_at.desc())

    result = await db.execute(query)
    routes = result.scalars().all()

    return [
        RouteResponse(
            id=r.id,
            name=r.name,
            host=r.host,
            path_pattern=r.path_pattern,
            methods=r.methods,
            priority=r.priority,
            upstream_service_id=r.upstream_service_id,
            upstream_url=r.upstream_url,
            upstream_path_prefix=r.upstream_path_prefix,
            strip_prefix=r.strip_prefix,
            timeout_ms=r.timeout_ms,
            retry_count=r.retry_count,
            lb_strategy=r.lb_strategy,
            auth_required=r.auth_required,
            s2s_required=r.s2s_required,
            permission_mode=r.permission_mode,
            enabled=r.enabled,
            rate_limit_per_min=r.rate_limit_per_min,
            description=r.description,
            created_at=r.created_at,
            updated_at=r.updated_at,
            permissions=[rp.permission.code for rp in r.route_permissions],
        )
        for r in routes
    ]


@router.post("", response_model=RouteResponse, status_code=201, summary="创建路由")
async def create_route(
    data: RouteCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:routes:write"]))],
):
    """
    创建新路由
    """
    route = Route(
        name=data.name,
        host=data.host,
        path_pattern=data.path_pattern,
        methods=data.methods,
        priority=data.priority,
        upstream_service_id=data.upstream_service_id,
        upstream_url=data.upstream_url,
        upstream_path_prefix=data.upstream_path_prefix,
        strip_prefix=data.strip_prefix,
        timeout_ms=data.timeout_ms,
        retry_count=data.retry_count,
        lb_strategy=data.lb_strategy,
        auth_required=data.auth_required,
        s2s_required=data.s2s_required,
        permission_mode=data.permission_mode,
        enabled=data.enabled,
        rate_limit_per_min=data.rate_limit_per_min,
        description=data.description,
    )
    db.add(route)
    await db.flush()

    # 添加权限关联
    permission_codes = []
    if data.permission_ids:
        for permission_id in data.permission_ids:
            result = await db.execute(
                select(Permission).where(Permission.id == permission_id)
            )
            permission = result.scalar_one_or_none()
            if permission:
                route_permission = RoutePermission(
                    route_id=route.id, permission_id=permission_id
                )
                db.add(route_permission)
                permission_codes.append(permission.code)

    await db.commit()
    await db.refresh(route)

    return RouteResponse(
        id=route.id,
        name=route.name,
        host=route.host,
        path_pattern=route.path_pattern,
        methods=route.methods,
        priority=route.priority,
        upstream_service_id=route.upstream_service_id,
        upstream_url=route.upstream_url,
        upstream_path_prefix=route.upstream_path_prefix,
        strip_prefix=route.strip_prefix,
        timeout_ms=route.timeout_ms,
        retry_count=route.retry_count,
        lb_strategy=route.lb_strategy,
        auth_required=route.auth_required,
        s2s_required=route.s2s_required,
        permission_mode=route.permission_mode,
        enabled=route.enabled,
        rate_limit_per_min=route.rate_limit_per_min,
        description=route.description,
        created_at=route.created_at,
        updated_at=route.updated_at,
        permissions=permission_codes,
    )


@router.get("/{route_id}", response_model=RouteResponse, summary="获取路由详情")
async def get_route(
    route_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:routes:read"]))],
):
    """
    获取路由详情
    """
    result = await db.execute(
        select(Route)
        .where(Route.id == route_id)
        .options(
            selectinload(Route.route_permissions).selectinload(RoutePermission.permission)
        )
    )
    route = result.scalar_one_or_none()

    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="路由不存在",
        )

    return RouteResponse(
        id=route.id,
        name=route.name,
        host=route.host,
        path_pattern=route.path_pattern,
        methods=route.methods,
        priority=route.priority,
        upstream_service_id=route.upstream_service_id,
        upstream_url=route.upstream_url,
        upstream_path_prefix=route.upstream_path_prefix,
        strip_prefix=route.strip_prefix,
        timeout_ms=route.timeout_ms,
        retry_count=route.retry_count,
        lb_strategy=route.lb_strategy,
        auth_required=route.auth_required,
        s2s_required=route.s2s_required,
        permission_mode=route.permission_mode,
        enabled=route.enabled,
        rate_limit_per_min=route.rate_limit_per_min,
        description=route.description,
        created_at=route.created_at,
        updated_at=route.updated_at,
        permissions=[rp.permission.code for rp in route.route_permissions],
    )


@router.patch("/{route_id}", response_model=RouteResponse, summary="更新路由")
async def update_route(
    route_id: str,
    data: RouteUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:routes:write"]))],
):
    """
    更新路由
    """
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()

    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="路由不存在",
        )

    # 更新字段
    update_data = data.model_dump(exclude_unset=True, exclude={"permission_ids"})
    for field, value in update_data.items():
        setattr(route, field, value)

    # 更新权限关联
    if data.permission_ids is not None:
        # 删除现有权限
        result = await db.execute(
            select(RoutePermission).where(RoutePermission.route_id == route_id)
        )
        for rp in result.scalars().all():
            await db.delete(rp)

        # 添加新权限
        for permission_id in data.permission_ids:
            result = await db.execute(
                select(Permission).where(Permission.id == permission_id)
            )
            if result.scalar_one_or_none():
                route_permission = RoutePermission(
                    route_id=route.id, permission_id=permission_id
                )
                db.add(route_permission)

    await db.commit()

    # 重新加载
    result = await db.execute(
        select(Route)
        .where(Route.id == route_id)
        .options(
            selectinload(Route.route_permissions).selectinload(RoutePermission.permission)
        )
    )
    route = result.scalar_one()

    return RouteResponse(
        id=route.id,
        name=route.name,
        host=route.host,
        path_pattern=route.path_pattern,
        methods=route.methods,
        priority=route.priority,
        upstream_service_id=route.upstream_service_id,
        upstream_url=route.upstream_url,
        upstream_path_prefix=route.upstream_path_prefix,
        strip_prefix=route.strip_prefix,
        timeout_ms=route.timeout_ms,
        retry_count=route.retry_count,
        lb_strategy=route.lb_strategy,
        auth_required=route.auth_required,
        s2s_required=route.s2s_required,
        permission_mode=route.permission_mode,
        enabled=route.enabled,
        rate_limit_per_min=route.rate_limit_per_min,
        description=route.description,
        created_at=route.created_at,
        updated_at=route.updated_at,
        permissions=[rp.permission.code for rp in route.route_permissions],
    )


@router.delete("/{route_id}", status_code=204, summary="删除路由")
async def delete_route(
    route_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:routes:delete"]))],
):
    """
    删除路由
    """
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()

    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="路由不存在",
        )

    await db.delete(route)
    await db.commit()
