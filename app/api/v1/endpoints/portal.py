"""
服务门户端点

提供服务目录功能，从 ServiceAtlas 获取已注册服务列表
"""

from typing import Annotated, Optional, List
from dataclasses import dataclass

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_current_user
from app.core.registry import get_registry_client
from app.db.models.user import User


router = APIRouter(prefix="/portal", tags=["服务门户"])


@dataclass
class PortalService:
    """门户服务信息"""
    id: str
    name: str
    host: str
    port: int
    protocol: str
    status: str
    description: Optional[str] = None
    proxy_path: Optional[str] = None  # 代理访问路径


@router.get("/services", summary="获取可访问的服务列表")
async def list_portal_services(
    current_user: Annotated[User, Depends(get_current_user)],
) -> List[dict]:
    """
    获取服务目录

    从 ServiceAtlas 获取已注册的服务列表，返回可供用户访问的服务入口
    """
    services = []

    # 检查是否启用了服务注册
    if not settings.registry_enabled:
        return services

    registry_client = get_registry_client()
    if not registry_client:
        return services

    # 从 ServiceAtlas 获取服务列表
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.registry_url}/api/v1/services",
                headers={"X-Gateway-ID": settings.registry_service_id},
            )

            if response.status_code == 200:
                remote_services = response.json()

                for svc in remote_services:
                    # 排除 Aegis 自身
                    if svc.get("id") == settings.registry_service_id:
                        continue

                    service_id = svc.get("id", "")
                    # 获取服务注册的 base_path（可能为 None）
                    base_path = svc.get("base_path")
                    # 代理路径始终使用固定格式（Aegis 路由是固定的）
                    proxy_path = f"/s/{service_id}/"
                    # 标记服务是否配置了 base_path
                    proxy_configured = bool(base_path)

                    services.append({
                        "id": service_id,
                        "name": svc.get("name", service_id),
                        "host": svc.get("host", ""),
                        "port": svc.get("port", 0),
                        "protocol": svc.get("protocol", "http"),
                        "status": svc.get("status", "unknown"),
                        "description": svc.get("service_meta", {}).get("description", ""),
                        "base_path": base_path,  # 可能为 None
                        "proxy_path": proxy_path,
                        "proxy_configured": proxy_configured,  # 服务是否配置了代理支持
                    })

    except Exception as e:
        # 获取失败时返回空列表，不抛出异常
        print(f"[Portal] 获取服务列表失败: {e}")

    return services


@router.get("/services/{service_id}", summary="获取服务详情")
async def get_portal_service(
    service_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    获取单个服务详情
    """
    if not settings.registry_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="服务注册未启用",
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.registry_url}/api/v1/services/{service_id}",
                headers={"X-Gateway-ID": settings.registry_service_id},
            )

            if response.status_code == 200:
                svc = response.json()
                svc_id = svc.get("id", "")
                # 获取服务注册的 base_path（可能为 None）
                base_path = svc.get("base_path")
                # 代理路径始终使用固定格式
                proxy_path = f"/s/{svc_id}/"
                # 标记服务是否配置了 base_path
                proxy_configured = bool(base_path)

                return {
                    "id": svc_id,
                    "name": svc.get("name", ""),
                    "host": svc.get("host", ""),
                    "port": svc.get("port", 0),
                    "protocol": svc.get("protocol", "http"),
                    "status": svc.get("status", "unknown"),
                    "description": svc.get("service_meta", {}).get("description", ""),
                    "base_path": base_path,  # 可能为 None
                    "proxy_path": proxy_path,
                    "proxy_configured": proxy_configured,
                }

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="服务不存在",
            )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"无法连接服务注册中心: {e}",
        )
