"""
路由相关模型

网关路由的创建、更新、响应模型
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RouteBase(BaseModel):
    """路由基础模型"""

    name: str = Field(..., min_length=1, max_length=128, description="路由名称")
    path_pattern: str = Field(..., min_length=1, max_length=512, description="路径匹配模式")
    methods: str = Field(default="*", max_length=64, description="允许的HTTP方法")


class RouteCreate(RouteBase):
    """创建路由请求"""

    host: Optional[str] = Field(None, max_length=255, description="匹配的Host")
    priority: int = Field(default=0, description="优先级")
    upstream_service_id: Optional[str] = Field(None, description="上游服务ID")
    upstream_url: Optional[str] = Field(None, max_length=512, description="上游服务URL")
    upstream_path_prefix: Optional[str] = Field(None, max_length=256, description="上游路径前缀")
    strip_prefix: bool = Field(default=False, description="是否剥离匹配的路径前缀")
    timeout_ms: int = Field(default=30000, ge=1000, le=300000, description="超时时间（毫秒）")
    retry_count: int = Field(default=0, ge=0, le=5, description="重试次数")
    lb_strategy: str = Field(default="round_robin", description="负载均衡策略")
    auth_required: bool = Field(default=True, description="是否需要用户认证")
    s2s_required: bool = Field(default=False, description="是否需要服务间认证")
    permission_mode: str = Field(default="any", description="权限模式：any/all")
    enabled: bool = Field(default=True, description="是否启用")
    rate_limit_per_min: int = Field(default=0, ge=0, description="每分钟请求限制")
    description: Optional[str] = Field(None, description="路由描述")
    permission_ids: Optional[list[str]] = Field(None, description="所需权限ID列表")


class RouteUpdate(BaseModel):
    """更新路由请求"""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    host: Optional[str] = Field(None, max_length=255)
    path_pattern: Optional[str] = Field(None, min_length=1, max_length=512)
    methods: Optional[str] = Field(None, max_length=64)
    priority: Optional[int] = None
    upstream_service_id: Optional[str] = None
    upstream_url: Optional[str] = Field(None, max_length=512)
    upstream_path_prefix: Optional[str] = Field(None, max_length=256)
    strip_prefix: Optional[bool] = None
    timeout_ms: Optional[int] = Field(None, ge=1000, le=300000)
    retry_count: Optional[int] = Field(None, ge=0, le=5)
    lb_strategy: Optional[str] = None
    auth_required: Optional[bool] = None
    s2s_required: Optional[bool] = None
    permission_mode: Optional[str] = None
    enabled: Optional[bool] = None
    rate_limit_per_min: Optional[int] = Field(None, ge=0)
    description: Optional[str] = None
    permission_ids: Optional[list[str]] = None


class RouteResponse(BaseModel):
    """路由响应"""

    id: str
    name: str
    host: Optional[str] = None
    path_pattern: str
    methods: str
    priority: int
    upstream_service_id: Optional[str] = None
    upstream_url: Optional[str] = None
    upstream_path_prefix: Optional[str] = None
    strip_prefix: bool
    timeout_ms: int
    retry_count: int
    lb_strategy: str
    auth_required: bool
    s2s_required: bool
    permission_mode: str
    enabled: bool
    rate_limit_per_min: int
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    permissions: list[str] = Field(default_factory=list, description="所需权限码列表")

    model_config = {"from_attributes": True}
