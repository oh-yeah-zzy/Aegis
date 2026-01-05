"""
安全配置模块

所有安全相关的配置项，支持环境变量覆盖。
环境变量前缀: AEGIS_SECURITY_

功能包括：
- JWT 密钥检查
- Cookie 安全设置
- 速率限制配置
- 账户锁定配置
- IP 管理配置
- 安全响应头配置
- 威胁检测配置
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseSettings):
    """
    安全配置类

    所有配置项都可以通过环境变量覆盖，前缀为 AEGIS_SECURITY_
    例如：AEGIS_SECURITY_RATE_LIMIT_LOGIN_MAX=10
    """

    model_config = SettingsConfigDict(
        env_prefix="AEGIS_SECURITY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ============ JWT 安全检查 ============
    # 启动时检查 JWT 密钥是否为默认值
    jwt_secret_check_enabled: bool = True
    # JWT 密钥最小长度要求
    jwt_secret_min_length: int = 32
    # 已知的不安全默认密钥列表
    jwt_known_weak_keys: list[str] = [
        "your-secret-key-change-in-production",
        "secret",
        "jwt-secret",
        "changeme",
        "your-secret-key",
    ]

    # ============ Cookie 安全 ============
    # 自动检测模式：非 debug 模式自动启用 Secure 标志
    cookie_secure_auto: bool = True
    # 强制设置：优先于自动检测，None 表示使用自动检测结果
    cookie_secure_force: Optional[bool] = None
    # SameSite 属性
    cookie_samesite: str = "lax"
    # HttpOnly 属性
    cookie_httponly: bool = True

    # ============ CORS 安全 ============
    # 严格模式：禁止使用 "*" 作为允许的源
    cors_strict_mode: bool = False

    # ============ 登录速率限制 ============
    # 是否启用速率限制
    rate_limit_enabled: bool = True
    # 单 IP 登录尝试次数限制
    rate_limit_login_max: int = 5
    # 登录限制时间窗口（秒）
    rate_limit_login_window: int = 300
    # 是否同时按用户名限制
    rate_limit_login_by_username: bool = True
    # 单用户名登录尝试次数限制
    rate_limit_login_by_username_max: int = 10
    # 单用户名限制时间窗口（秒）
    rate_limit_login_by_username_window: int = 600

    # ============ 全局速率限制 ============
    # 单 IP 每分钟全局请求数限制
    rate_limit_global_max: int = 100
    # 全局限制时间窗口（秒）
    rate_limit_global_window: int = 60

    # ============ 账户锁定 ============
    # 是否启用账户锁定
    account_lockout_enabled: bool = True
    # 触发锁定的连续失败次数
    account_lockout_threshold: int = 5
    # 账户锁定时长（秒），默认 30 分钟
    account_lockout_duration: int = 1800
    # 登录成功后是否重置失败计数
    account_lockout_reset_on_success: bool = True

    # ============ IP 白名单 ============
    # 是否启用白名单模式（开启后只允许白名单 IP 访问）
    ip_whitelist_enabled: bool = False
    # IP 白名单列表（支持单个 IP 和 CIDR 格式）
    ip_whitelist: list[str] = []

    # ============ IP 黑名单 ============
    # 是否启用黑名单模式
    ip_blacklist_enabled: bool = True
    # 静态 IP 黑名单列表
    ip_blacklist: list[str] = []

    # ============ 自动 IP 封禁 ============
    # 是否启用自动封禁
    ip_auto_ban_enabled: bool = True
    # 触发自动封禁的失败次数阈值
    ip_auto_ban_threshold: int = 10
    # 检测时间窗口（秒）
    ip_auto_ban_window: int = 300
    # 自动封禁时长（秒），默认 1 小时
    ip_auto_ban_duration: int = 3600

    # ============ 请求限制 ============
    # 最大请求体大小（字节），默认 10MB
    request_max_body_size: int = 10 * 1024 * 1024

    # ============ 安全响应头 ============
    # 是否启用安全响应头
    security_headers_enabled: bool = True
    # Content-Security-Policy
    csp_policy: str = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'"
    # X-Frame-Options
    frame_options: str = "DENY"
    # X-Content-Type-Options
    content_type_options: str = "nosniff"
    # X-XSS-Protection
    xss_protection: str = "1; mode=block"
    # Referrer-Policy
    referrer_policy: str = "strict-origin-when-cross-origin"
    # HSTS max-age（秒），默认 1 年
    hsts_max_age: int = 31536000
    # HSTS 是否包含子域名
    hsts_include_subdomains: bool = True
    # Permissions-Policy
    permissions_policy: str = "geolocation=(), microphone=(), camera=()"

    # ============ 威胁检测 ============
    # 是否启用威胁检测
    threat_detection_enabled: bool = True
    # 暴力破解检测：单 IP 短时间内失败次数阈值
    threat_brute_force_threshold: int = 10
    # 暴力破解检测：时间窗口（秒）
    threat_brute_force_window: int = 300
    # 凭据填充检测：单 IP 尝试不同用户数阈值
    threat_credential_stuffing_threshold: int = 5
    # 凭据填充检测：时间窗口（秒）
    threat_credential_stuffing_window: int = 600
    # 检测到威胁后是否自动封禁 IP
    threat_auto_ban_on_detection: bool = True


@lru_cache
def get_security_settings() -> SecuritySettings:
    """获取安全配置单例"""
    return SecuritySettings()


# 全局安全配置单例
security_settings = get_security_settings()
