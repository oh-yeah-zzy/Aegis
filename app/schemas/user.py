"""
用户相关模型

用户的创建、更新、响应模型
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """用户基础模型"""

    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    email: EmailStr = Field(..., description="邮箱")


class UserCreate(UserBase):
    """创建用户请求"""

    password: str = Field(..., min_length=8, description="密码")
    is_active: bool = Field(default=True, description="是否启用")
    is_superuser: bool = Field(default=False, description="是否为超级管理员")
    role_ids: Optional[list[str]] = Field(default=None, description="角色ID列表")


class UserUpdate(BaseModel):
    """更新用户请求"""

    username: Optional[str] = Field(None, min_length=3, max_length=64)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8)
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    role_ids: Optional[list[str]] = None


class UserResponse(BaseModel):
    """用户响应"""

    id: str
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    roles: list[str] = Field(default_factory=list, description="角色码列表")

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """用户列表响应"""

    items: list[UserResponse]
    total: int
    page: int
    page_size: int
