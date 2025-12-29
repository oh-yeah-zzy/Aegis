"""
服务和服务凭证模型

用于服务间认证（Service-to-Service Authentication）
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import Boolean, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class Service(Base, TimestampMixin):
    """
    服务表

    注册到系统中的服务，用于服务间认证
    """

    __tablename__ = "services"

    # 主键
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # 服务码：唯一标识
    code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    # 服务名称
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    # 服务描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # 服务是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # 服务负责人用户ID
    owner_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # 关系：服务凭证（一对多）
    credentials: Mapped[list["ServiceCredential"]] = relationship(
        "ServiceCredential",
        back_populates="service",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Service(id={self.id}, code={self.code})>"


class ServiceCredential(Base, TimestampMixin):
    """
    服务凭证表

    存储服务的认证凭证，支持多种认证方式
    """

    __tablename__ = "service_credentials"

    # 主键
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # 所属服务
    service_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 凭证类型：client_secret, jwt, mtls
    type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="client_secret",
    )

    # 客户端ID：唯一
    client_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    # 密钥哈希（对于 client_secret 类型）
    secret_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # 公钥 PEM（对于 jwt 类型）
    public_key_pem: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # 证书指纹（对于 mtls 类型）
    cert_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )

    # 密钥ID（用于 JWKS）
    kid: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
    )

    # 过期时间
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 撤销时间
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 最后使用时间
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 关系
    service: Mapped["Service"] = relationship(
        "Service",
        back_populates="credentials",
    )

    def __repr__(self) -> str:
        return f"<ServiceCredential(id={self.id}, client_id={self.client_id})>"

    @property
    def is_valid(self) -> bool:
        """检查凭证是否有效"""
        now = datetime.now(timezone.utc)
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at < now:
            return False
        return True
