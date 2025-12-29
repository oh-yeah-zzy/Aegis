"""
JWT 令牌处理模块

提供 JWT 令牌的创建、验证和解析功能
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from jose import JWTError, jwt

from app.core.config import settings


class TokenError(Exception):
    """令牌错误基类"""
    pass


class TokenExpiredError(TokenError):
    """令牌已过期"""
    pass


class TokenInvalidError(TokenError):
    """令牌无效"""
    pass


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    创建访问令牌（Access Token）

    Args:
        subject: 令牌主体（通常是用户ID或服务ID）
        expires_delta: 过期时间增量，默认使用配置值
        extra_claims: 额外的 JWT claims

    Returns:
        编码后的 JWT 字符串
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    # 构建 JWT payload
    to_encode = {
        "sub": subject,  # 主体
        "iat": now,  # 签发时间
        "exp": expire,  # 过期时间
        "jti": str(uuid4()),  # 唯一标识符，用于令牌撤销
        "type": "access",  # 令牌类型
    }

    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str]:
    """
    创建刷新令牌（Refresh Token）

    Args:
        subject: 令牌主体
        expires_delta: 过期时间增量，默认使用配置值

    Returns:
        (编码后的 JWT 字符串, jti 唯一标识符)
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    jti = str(uuid4())

    to_encode = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "jti": jti,
        "type": "refresh",
    }

    token = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    """
    解码并验证 JWT 令牌

    Args:
        token: JWT 字符串

    Returns:
        解码后的 payload 字典

    Raises:
        TokenExpiredError: 令牌已过期
        TokenInvalidError: 令牌无效
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("令牌已过期")
    except JWTError as e:
        raise TokenInvalidError(f"令牌无效: {str(e)}")


def get_token_subject(token: str) -> str:
    """
    从令牌中提取主体（subject）

    Args:
        token: JWT 字符串

    Returns:
        主体字符串
    """
    payload = decode_token(token)
    subject = payload.get("sub")
    if not subject:
        raise TokenInvalidError("令牌缺少主体信息")
    return subject


def get_token_jti(token: str) -> str:
    """
    从令牌中提取唯一标识符（jti）

    Args:
        token: JWT 字符串

    Returns:
        jti 字符串
    """
    payload = decode_token(token)
    jti = payload.get("jti")
    if not jti:
        raise TokenInvalidError("令牌缺少唯一标识符")
    return jti
