"""
令牌模型

存储刷新令牌，用于令牌管理和撤销
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import String, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class RefreshToken(Base):
    """
    刷新令牌表

    存储刷新令牌的哈希值，支持令牌轮换和撤销
    """

    __tablename__ = "refresh_tokens"

    # 主键
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # 所属用户
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 令牌哈希值（不存储明文）
    token_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    # JWT 唯一标识符
    jti: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
    )

    # 签发时间
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 过期时间
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # 撤销时间（如果已撤销）
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 被替换的令牌ID（用于令牌轮换）
    replaced_by_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )

    # 客户端信息
    ip: Mapped[Optional[str]] = mapped_column(
        String(45),  # 支持 IPv6
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    device_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, jti={self.jti})>"

    @property
    def is_valid(self) -> bool:
        """检查令牌是否有效"""
        now = datetime.now(timezone.utc)
        if self.revoked_at is not None:
            return False
        if self.expires_at < now:
            return False
        return True
