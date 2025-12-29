"""
服务注册模块

将 Aegis 注册到 ServiceAtlas 服务注册中心，并维护心跳
同时提供从 ServiceAtlas 获取路由规则的功能
"""

import asyncio
import atexit
import signal
import time
from typing import Optional, List
from datetime import datetime
from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass
class TargetServiceInfo:
    """目标服务信息"""
    id: str
    name: str
    host: str
    port: int
    protocol: str
    status: str
    base_url: str


@dataclass
class RemoteRoute:
    """从 ServiceAtlas 获取的路由规则"""
    id: int
    path_pattern: str
    target_service_id: str
    target_service: TargetServiceInfo
    strip_prefix: bool
    strip_path: Optional[str]
    priority: int
    enabled: bool


class RouteCache:
    """路由规则缓存"""

    def __init__(self, ttl: int = 30):
        """
        初始化路由缓存

        Args:
            ttl: 缓存过期时间（秒）
        """
        self.ttl = ttl
        self._routes: List[RemoteRoute] = []
        self._last_update: float = 0
        self._lock = asyncio.Lock()

    def is_expired(self) -> bool:
        """检查缓存是否过期"""
        return time.time() - self._last_update > self.ttl

    def get(self) -> Optional[List[RemoteRoute]]:
        """获取缓存的路由规则（如果未过期）"""
        if self.is_expired():
            return None
        return self._routes

    def set(self, routes: List[RemoteRoute]):
        """设置缓存"""
        self._routes = routes
        self._last_update = time.time()

    def clear(self):
        """清除缓存"""
        self._routes = []
        self._last_update = 0


class ServiceRegistryClient:
    """
    ServiceAtlas 服务注册客户端

    负责将 Aegis 注册到服务注册中心，并定期发送心跳
    同时提供从 ServiceAtlas 获取路由规则的功能
    """

    def __init__(
        self,
        registry_url: str,
        service_id: str,
        service_name: str,
        host: str,
        port: int,
        protocol: str = "http",
        health_check_path: str = "/health",
        is_gateway: bool = True,
        metadata: Optional[dict] = None,
        heartbeat_interval: int = 30,
        route_cache_ttl: int = 30,
    ):
        """
        初始化服务注册客户端

        Args:
            registry_url: ServiceAtlas 注册中心地址
            service_id: 服务唯一标识
            service_name: 服务显示名称
            host: 服务地址
            port: 服务端口
            protocol: 协议类型
            health_check_path: 健康检查路径
            is_gateway: 是否作为网关
            metadata: 扩展元数据
            heartbeat_interval: 心跳间隔（秒）
            route_cache_ttl: 路由缓存过期时间（秒）
        """
        self.registry_url = registry_url.rstrip("/")
        self.service_id = service_id
        self.service_name = service_name
        self.host = host
        self.port = port
        self.protocol = protocol
        self.health_check_path = health_check_path
        self.is_gateway = is_gateway
        self.metadata = metadata or {}
        self.heartbeat_interval = heartbeat_interval

        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
        self._client: Optional[httpx.AsyncClient] = None

        # 路由规则缓存
        self._route_cache = RouteCache(ttl=route_cache_ttl)

    async def start(self):
        """
        启动服务注册客户端

        注册服务并启动心跳任务
        """
        if self._running:
            return

        self._running = True
        self._client = httpx.AsyncClient(timeout=10.0)

        # 注册服务
        await self._register()

        # 启动心跳任务
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        print(f"[Aegis] 已注册到服务注册中心: {self.registry_url}")
        print(f"[Aegis] 服务ID: {self.service_id}, 心跳间隔: {self.heartbeat_interval}秒")

    async def stop(self):
        """
        停止服务注册客户端

        注销服务并停止心跳任务
        """
        if not self._running:
            return

        self._running = False

        # 取消心跳任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # 注销服务
        await self._deregister()

        # 关闭 HTTP 客户端
        if self._client:
            await self._client.aclose()
            self._client = None

        print(f"[Aegis] 已从服务注册中心注销")

    async def _register(self):
        """注册服务到 ServiceAtlas"""
        url = f"{self.registry_url}/api/v1/services"

        payload = {
            "id": self.service_id,
            "name": self.service_name,
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "health_check_path": self.health_check_path,
            "is_gateway": self.is_gateway,
            "service_meta": {
                **self.metadata,
                "version": settings.app_version,
                "description": "权限控制网关服务",
                "registered_at": datetime.utcnow().isoformat(),
            },
        }

        try:
            response = await self._client.post(url, json=payload)
            if response.status_code in (200, 201):
                print(f"[Aegis] 服务注册成功")
            else:
                print(f"[Aegis] 服务注册失败: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[Aegis] 服务注册异常: {e}")

    async def _deregister(self):
        """从 ServiceAtlas 注销服务"""
        url = f"{self.registry_url}/api/v1/services/{self.service_id}"

        try:
            response = await self._client.delete(url)
            if response.status_code in (200, 204):
                print(f"[Aegis] 服务注销成功")
            else:
                print(f"[Aegis] 服务注销失败: {response.status_code}")
        except Exception as e:
            print(f"[Aegis] 服务注销异常: {e}")

    async def _heartbeat(self):
        """发送心跳"""
        url = f"{self.registry_url}/api/v1/services/{self.service_id}/heartbeat"

        try:
            response = await self._client.post(url)
            if response.status_code == 200:
                # 心跳成功，静默
                pass
            else:
                print(f"[Aegis] 心跳失败: {response.status_code}")
        except Exception as e:
            print(f"[Aegis] 心跳异常: {e}")

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                if self._running:
                    await self._heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Aegis] 心跳循环异常: {e}")

    async def fetch_routes(self, force_refresh: bool = False) -> List[RemoteRoute]:
        """
        从 ServiceAtlas 获取路由规则

        Args:
            force_refresh: 是否强制刷新缓存

        Returns:
            路由规则列表
        """
        # 如果未强制刷新且缓存未过期，直接返回缓存
        if not force_refresh:
            cached = self._route_cache.get()
            if cached is not None:
                return cached

        # 从 ServiceAtlas 获取路由规则
        url = f"{self.registry_url}/api/v1/gateway/routes"
        headers = {"X-Gateway-ID": self.service_id}

        try:
            # 如果客户端未初始化，创建一个临时的
            client = self._client or httpx.AsyncClient(timeout=10.0)
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                routes_data = response.json()
                routes = []

                for r in routes_data:
                    target = r.get("target_service", {})
                    routes.append(RemoteRoute(
                        id=r["id"],
                        path_pattern=r["path_pattern"],
                        target_service_id=r["target_service_id"],
                        target_service=TargetServiceInfo(
                            id=target.get("id", ""),
                            name=target.get("name", ""),
                            host=target.get("host", ""),
                            port=target.get("port", 0),
                            protocol=target.get("protocol", "http"),
                            status=target.get("status", "unknown"),
                            base_url=target.get("base_url", ""),
                        ),
                        strip_prefix=r.get("strip_prefix", False),
                        strip_path=r.get("strip_path"),
                        priority=r.get("priority", 0),
                        enabled=r.get("enabled", True),
                    ))

                # 更新缓存
                self._route_cache.set(routes)
                return routes

            elif response.status_code == 403:
                print(f"[Aegis] 获取路由规则失败: 无权限（服务未标记为网关）")
            elif response.status_code == 404:
                print(f"[Aegis] 获取路由规则失败: 网关服务不存在")
            else:
                print(f"[Aegis] 获取路由规则失败: {response.status_code}")

        except Exception as e:
            print(f"[Aegis] 获取路由规则异常: {e}")

        # 如果获取失败，返回缓存的旧数据（如果有的话）
        return self._route_cache._routes or []

    def clear_route_cache(self):
        """清除路由规则缓存"""
        self._route_cache.clear()


# 全局注册客户端实例
_registry_client: Optional[ServiceRegistryClient] = None


def get_registry_client() -> Optional[ServiceRegistryClient]:
    """获取全局注册客户端实例"""
    return _registry_client


async def init_registry_client():
    """
    初始化服务注册客户端

    从配置中读取参数并启动客户端
    """
    global _registry_client

    # 检查是否启用服务注册
    if not settings.registry_enabled:
        print("[Aegis] 服务注册已禁用")
        return

    if not settings.registry_url:
        print("[Aegis] 未配置服务注册中心地址，跳过注册")
        return

    _registry_client = ServiceRegistryClient(
        registry_url=settings.registry_url,
        service_id=settings.registry_service_id,
        service_name=settings.registry_service_name,
        host=settings.registry_service_host,
        port=settings.port,
        protocol="http",
        health_check_path="/health",
        is_gateway=True,
        metadata={
            "type": "gateway",
            "auth": "jwt",
        },
        heartbeat_interval=settings.registry_heartbeat_interval,
    )

    await _registry_client.start()


async def shutdown_registry_client():
    """关闭服务注册客户端"""
    global _registry_client

    if _registry_client:
        await _registry_client.stop()
        _registry_client = None


async def fetch_remote_routes(force_refresh: bool = False) -> List[RemoteRoute]:
    """
    获取远程路由规则（从 ServiceAtlas）

    Args:
        force_refresh: 是否强制刷新缓存

    Returns:
        路由规则列表，如果未启用注册中心则返回空列表
    """
    if _registry_client:
        return await _registry_client.fetch_routes(force_refresh)
    return []
