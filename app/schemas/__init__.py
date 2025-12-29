"""Pydantic 数据验证模型"""

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    TokenPayload,
)
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
)
from app.schemas.role import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    PermissionCreate,
    PermissionResponse,
)
from app.schemas.service import (
    ServiceCreate,
    ServiceUpdate,
    ServiceResponse,
    ServiceCredentialCreate,
    ServiceCredentialResponse,
    S2STokenRequest,
    S2STokenResponse,
)
from app.schemas.route import (
    RouteCreate,
    RouteUpdate,
    RouteResponse,
)
from app.schemas.common import (
    APIResponse,
    PaginationParams,
    PaginatedResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "RefreshResponse",
    "TokenPayload",
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    # Role
    "RoleCreate",
    "RoleUpdate",
    "RoleResponse",
    "PermissionCreate",
    "PermissionResponse",
    # Service
    "ServiceCreate",
    "ServiceUpdate",
    "ServiceResponse",
    "ServiceCredentialCreate",
    "ServiceCredentialResponse",
    "S2STokenRequest",
    "S2STokenResponse",
    # Route
    "RouteCreate",
    "RouteUpdate",
    "RouteResponse",
    # Common
    "APIResponse",
    "PaginationParams",
    "PaginatedResponse",
]
