"""
服务注册模块

将 Aegis 注册到 ServiceAtlas 服务注册中心，并维护心跳

优先使用 ServiceAtlas SDK，若未安装则使用内置实现
"""

import asyncio
from typing import Optional
from datetime import datetime
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# 尝试导入 SDK
try:
    from serviceatlas_client import AsyncServiceAtlasClient
    SDK_AVAILABLE = True
    logger.debug("[Aegis] 使用 ServiceAtlas SDK")
except ImportError:
    SDK_AVAILABLE = False
    logger.debug("[Aegis] SDK 未安装，使用内置实现")


# ================== 内置实现（SDK 不可用时使用）==================
if not SDK_AVAILABLE:
    class AsyncServiceAtlasClient:
        """
        内置的 ServiceAtlas 异步注册客户端
        仅在 SDK 未安装时使用
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
            is_gateway: bool = False,
            base_path: str = "",
            metadata: Optional[dict] = None,
            heartbeat_interval: int = 30,
            trust_env: bool = True,
        ):
            self.registry_url = registry_url.rstrip("/")
            self.service_id = service_id
            self.service_name = service_name
            self.host = host
            self.port = port
            self.protocol = protocol
            self.health_check_path = health_check_path
            self.is_gateway = is_gateway
            self.base_path = base_path
            self.metadata = metadata or {}
            self.heartbeat_interval = heartbeat_interval
            self.trust_env = trust_env

            self._heartbeat_task: Optional[asyncio.Task] = None
            self._running = False
            self._client: Optional[httpx.AsyncClient] = None

        async def start(self) -> bool:
            """启动客户端：注册服务并开始心跳"""
            if self._running:
                return True

            self._running = True
            self._client = httpx.AsyncClient(timeout=10.0, trust_env=self.trust_env)

            # 注册服务
            if not await self._register():
                print(f"[Aegis] 服务注册失败")
                return False

            # 启动心跳任务
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            print(f"[Aegis] 已注册到服务注册中心: {self.registry_url}")
            print(f"[Aegis] 服务ID: {self.service_id}, 心跳间隔: {self.heartbeat_interval}秒")
            return True

        async def stop(self):
            """停止客户端：停止心跳并注销服务"""
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

        async def _register(self) -> bool:
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
                    "description": "身份认证与访问管理系统",
                    "registered_at": datetime.utcnow().isoformat(),
                },
            }
            # 只有设置了 base_path 才发送该字段
            if self.base_path:
                payload["base_path"] = self.base_path

            try:
                response = await self._client.post(url, json=payload)
                if response.status_code in (200, 201):
                    print(f"[Aegis] 服务注册成功")
                    return True
                else:
                    print(f"[Aegis] 服务注册失败: {response.status_code} - {response.text}")
                    return False
            except Exception as e:
                print(f"[Aegis] 服务注册异常: {e}")
                return False

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
                if response.status_code != 200:
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


class ServiceRegistryClient:
    """
    ServiceAtlas 服务注册客户端

    负责将 Aegis 注册到服务注册中心，并定期发送心跳
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
        base_path: str = "",
        metadata: Optional[dict] = None,
        heartbeat_interval: int = 30,
        trust_env: bool = False,
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
            base_path: 代理路径前缀（通过其他网关代理时设置）
            metadata: 扩展元数据
            heartbeat_interval: 心跳间隔（秒）
            trust_env: 是否信任环境变量中的代理配置
        """
        self.registry_url = registry_url.rstrip("/")
        self.service_id = service_id
        self.trust_env = trust_env

        # 创建 SDK 客户端（或内置实现）
        # Aegis 是 IAM 系统，不是网关，因此 is_gateway=False
        self._sdk_client = AsyncServiceAtlasClient(
            registry_url=registry_url,
            service_id=service_id,
            service_name=service_name,
            host=host,
            port=port,
            protocol=protocol,
            health_check_path=health_check_path,
            is_gateway=False,  # Aegis 不是网关
            base_path=base_path,
            metadata=metadata,
            heartbeat_interval=heartbeat_interval,
            trust_env=trust_env,
        )

        self._running = False

    async def start(self):
        """
        启动服务注册客户端

        注册服务并启动心跳任务
        """
        if self._running:
            return

        self._running = True

        # 使用 SDK 客户端启动
        await self._sdk_client.start()

    async def stop(self):
        """
        停止服务注册客户端

        注销服务并停止心跳任务
        """
        if not self._running:
            return

        self._running = False

        # 使用 SDK 客户端停止
        await self._sdk_client.stop()


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
        base_path=settings.registry_service_base_path,
        metadata={
            "service_type": "authentication",  # 标记为认证服务
            "auth_endpoint": "/api/v1/auth/login",  # API 登录端点
            "login_path": "/admin/login",  # Web 登录页面路径
            "auth_methods": ["jwt"],
            # 认证服务自身的认证配置
            "auth_config": {
                "require_auth": True,
                "auth_service_id": settings.registry_service_id,  # 自己验证自己
                # 登录相关接口必须公开，否则无法登录
                # API 文档不再公开，需要认证后才能访问
                "public_paths": [
                    "/health",
                    "/admin/login",  # Web 登录页面
                    "/admin/login/submit",  # Web 登录提交
                    "/api/v1/auth/login",  # API 登录端点
                    "/api/v1/auth/refresh",  # 令牌刷新
                    "/static/**",  # 静态资源
                ],
            },
        },
        heartbeat_interval=settings.registry_heartbeat_interval,
        trust_env=False,  # 默认禁用代理，避免环境变量干扰
    )

    await _registry_client.start()


async def shutdown_registry_client():
    """关闭服务注册客户端"""
    global _registry_client

    if _registry_client:
        await _registry_client.stop()
        _registry_client = None
