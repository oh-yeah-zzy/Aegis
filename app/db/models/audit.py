"""
审计日志模型

记录所有请求和认证事件，用于安全审计
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """
    审计日志表

    记录所有经过网关的请求，包括决策结果
    """

    __tablename__ = "audit_logs"

    # 主键（使用自增ID，便于分区和归档）
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # 时间戳
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # 请求追踪ID
    request_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # 分布式追踪ID（可选）
    trace_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    # 主体类型：user, service, anonymous
    principal_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    # 主体ID
    principal_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    # 主体标签（用户名或服务名）
    principal_label: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )

    # 客户端信息
    client_ip: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # 请求信息
    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    host: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )
    query_string: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # 路由信息
    route_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
    )

    # 上游服务信息
    upstream_service_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
    )
    upstream_instance_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )

    # 响应信息
    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # 决策结果
    decision: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
    )
    deny_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # 请求/响应元数据（已脱敏）
    request_headers: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    response_headers: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    # 传输大小
    request_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    response_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # 错误信息
    error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, request_id={self.request_id}, path={self.path})>"


class AuthEvent(Base):
    """
    认证事件表

    记录登录、登出、令牌刷新等认证相关事件
    """

    __tablename__ = "auth_events"

    # 主键
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # 时间戳
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # 事件类型：login, logout, refresh, revoke, password_change, etc.
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    # 主体类型：user, service
    principal_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    # 主体ID
    principal_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    # 客户端信息
    ip: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # 事件详情（JSON）
    details: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    # 事件结果：success, failure
    result: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="success",
    )

    # 失败原因
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AuthEvent(id={self.id}, event_type={self.event_type}, principal_id={self.principal_id})>"
