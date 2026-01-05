"""
认证相关模型

登录、令牌刷新等请求/响应模型
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """登录请求"""

    username: str = Field(..., min_length=1, max_length=64, description="用户名或邮箱")
    password: str = Field(..., min_length=1, description="密码")


class LoginResponse(BaseModel):
    """登录响应"""

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="Bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌过期时间（秒）")


class RefreshRequest(BaseModel):
    """令牌刷新请求"""

    refresh_token: str = Field(..., description="刷新令牌")


class RefreshResponse(BaseModel):
    """令牌刷新响应"""

    access_token: str = Field(..., description="新的访问令牌")
    refresh_token: str = Field(..., description="新的刷新令牌（轮换）")
    token_type: str = Field(default="Bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌过期时间（秒）")


class LogoutRequest(BaseModel):
    """登出请求（可选）"""

    refresh_token: Optional[str] = Field(default=None, description="刷新令牌")


class TokenPayload(BaseModel):
    """JWT 令牌载荷"""

    sub: str = Field(..., description="主体（用户ID或服务ID）")
    exp: datetime = Field(..., description="过期时间")
    iat: datetime = Field(..., description="签发时间")
    jti: str = Field(..., description="唯一标识符")
    type: str = Field(..., description="令牌类型：access 或 refresh")
    roles: Optional[list[str]] = Field(default=None, description="角色列表")
    permissions: Optional[list[str]] = Field(default=None, description="权限列表")


class CurrentUser(BaseModel):
    """当前用户信息"""

    id: str
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    roles: list[str] = []
    permissions: list[str] = []


class ValidateResponse(BaseModel):
    """Token 验证响应"""

    valid: bool = Field(..., description="Token 是否有效")
    user_id: Optional[str] = Field(default=None, description="用户 ID")
    username: Optional[str] = Field(default=None, description="用户名")
    roles: list[str] = Field(default_factory=list, description="角色列表")
    permissions: list[str] = Field(default_factory=list, description="权限列表")
