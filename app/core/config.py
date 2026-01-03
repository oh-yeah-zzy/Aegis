"""
应用配置模块

使用 pydantic-settings 管理配置，支持环境变量和 .env 文件
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 应用基础配置
    app_name: str = "Aegis"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000

    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./aegis.db"

    # JWT 配置
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # 密码配置
    password_min_length: int = 8

    # 网关配置
    gateway_timeout: int = 30  # 秒
    gateway_max_retries: int = 3

    # 上游服务配置（ServiceAtlas）
    upstream_service_url: Optional[str] = "http://localhost:8001"

    # 审计日志配置
    audit_log_enabled: bool = True
    audit_log_sensitive_fields: list[str] = [
        "password",
        "token",
        "secret",
        "authorization",
    ]

    # CORS 配置
    cors_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # 服务注册配置（ServiceAtlas）
    registry_enabled: bool = True  # 是否启用服务注册
    registry_url: str = "http://localhost:8888"  # ServiceAtlas 地址
    registry_service_id: str = "aegis"  # 服务ID
    registry_service_name: str = "Aegis 权限网关"  # 服务名称
    registry_service_host: str = "127.0.0.1"  # 本服务对外暴露的地址
    registry_service_base_path: str = ""  # 代理路径前缀（通过其他网关代理时设置）
    registry_heartbeat_interval: int = 30  # 心跳间隔（秒）


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
