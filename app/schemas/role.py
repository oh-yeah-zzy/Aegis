"""
角色和权限模型

角色、权限的创建、更新、响应模型
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PermissionBase(BaseModel):
    """权限基础模型"""

    code: str = Field(..., min_length=1, max_length=128, description="权限码")
    name: str = Field(..., min_length=1, max_length=128, description="权限名称")
    description: Optional[str] = Field(None, description="权限描述")
    service_code: Optional[str] = Field(None, max_length=64, description="所属服务码")
    resource: Optional[str] = Field(None, max_length=64, description="资源类型")
    action: Optional[str] = Field(None, max_length=32, description="操作类型")


class PermissionCreate(PermissionBase):
    """创建权限请求"""

    pass


class PermissionUpdate(BaseModel):
    """更新权限请求"""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    service_code: Optional[str] = Field(None, max_length=64)
    resource: Optional[str] = Field(None, max_length=64)
    action: Optional[str] = Field(None, max_length=32)


class PermissionResponse(BaseModel):
    """权限响应"""

    id: str
    code: str
    name: str
    description: Optional[str] = None
    service_code: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleBase(BaseModel):
    """角色基础模型"""

    code: str = Field(..., min_length=1, max_length=64, description="角色码")
    name: str = Field(..., min_length=1, max_length=128, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")


class RoleCreate(RoleBase):
    """创建角色请求"""

    permission_ids: Optional[list[str]] = Field(None, description="权限ID列表")


class RoleUpdate(BaseModel):
    """更新角色请求"""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    permission_ids: Optional[list[str]] = None


class RoleResponse(BaseModel):
    """角色响应"""

    id: str
    code: str
    name: str
    description: Optional[str] = None
    is_system: bool
    created_at: datetime
    permissions: list[PermissionResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
