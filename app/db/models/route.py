"""
路由模型

定义网关路由规则，用于请求匹配和转发
"""

from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import Boolean, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.role import Permission


class Route(Base, TimestampMixin):
    """
    路由表

    定义网关的路由规则，包括路径匹配、权限要求、上游服务等
    """

    __tablename__ = "routes"

    # 主键
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # 路由名称
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    # 匹配的 Host（可选，默认匹配所有）
    host: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # 路径匹配模式（支持通配符）
    # 例如：/api/v1/users, /api/v1/users/*, /api/**
    path_pattern: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        index=True,
    )

    # 允许的 HTTP 方法（逗号分隔）
    # 例如：GET,POST,PUT,DELETE 或 * 表示所有
    methods: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="*",
    )

    # 优先级（数值越大优先级越高）
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
    )

    # 上游服务ID（关联到注册中心的服务）
    upstream_service_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
    )

    # 上游服务 URL（直接指定，与 upstream_service_id 二选一）
    upstream_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )

    # 上游路径前缀
    upstream_path_prefix: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
    )

    # 是否剥离匹配的路径前缀
    strip_prefix: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # 超时时间（毫秒）
    timeout_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30000,
    )

    # 重试次数
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # 负载均衡策略：round_robin, random, least_conn
    lb_strategy: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="round_robin",
    )

    # 是否需要用户认证
    auth_required: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # 是否需要服务间认证
    s2s_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # 权限模式：any（满足任一权限）/ all（满足所有权限）
    permission_mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="any",
    )

    # 是否启用
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # 每分钟请求限制（0 表示不限制）
    rate_limit_per_min: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # 路由描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # 关系：路由权限关联
    route_permissions: Mapped[list["RoutePermission"]] = relationship(
        "RoutePermission",
        back_populates="route",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Route(id={self.id}, name={self.name}, path_pattern={self.path_pattern})>"


class RoutePermission(Base):
    """
    路由-权限关联表

    定义访问某个路由需要的权限
    """

    __tablename__ = "route_permissions"

    # 复合主键
    route_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("routes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # 关系
    route: Mapped["Route"] = relationship("Route", back_populates="route_permissions")
    permission: Mapped["Permission"] = relationship("Permission")

    def __repr__(self) -> str:
        return f"<RoutePermission(route_id={self.route_id}, permission_id={self.permission_id})>"
