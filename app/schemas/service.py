"""
服务相关模型

服务和服务凭证的创建、更新、响应模型
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ServiceBase(BaseModel):
    """服务基础模型"""

    code: str = Field(..., min_length=1, max_length=64, description="服务码")
    name: str = Field(..., min_length=1, max_length=128, description="服务名称")
    description: Optional[str] = Field(None, description="服务描述")


class ServiceCreate(ServiceBase):
    """创建服务请求"""

    is_active: bool = Field(default=True, description="是否启用")
    owner_user_id: Optional[str] = Field(None, description="服务负责人用户ID")


class ServiceUpdate(BaseModel):
    """更新服务请求"""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    owner_user_id: Optional[str] = None


class ServiceResponse(BaseModel):
    """服务响应"""

    id: str
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool
    owner_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ServiceCredentialCreate(BaseModel):
    """创建服务凭证请求"""

    type: str = Field(default="client_secret", description="凭证类型")
    expires_in_days: Optional[int] = Field(None, ge=1, description="有效期（天）")


class ServiceCredentialResponse(BaseModel):
    """服务凭证响应"""

    id: str
    service_id: str
    type: str
    client_id: str
    # 只在创建时返回明文密钥
    client_secret: Optional[str] = Field(None, description="客户端密钥（仅创建时返回）")
    kid: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class S2STokenRequest(BaseModel):
    """服务间令牌请求"""

    client_id: str = Field(..., description="客户端ID")
    client_secret: str = Field(..., description="客户端密钥")
    grant_type: str = Field(default="client_credentials", description="授权类型")


class S2STokenResponse(BaseModel):
    """服务间令牌响应"""

    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="Bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")
