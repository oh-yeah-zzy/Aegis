"""
IP 封禁记录模型

记录手动和自动的 IP 封禁信息，支持：
- 永久封禁
- 临时封禁（带过期时间）
- 自动封禁（由威胁检测触发）
- 封禁解除
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IPBanRecord(Base):
    """
    IP 封禁记录表

    存储所有 IP 封禁记录，包括手动封禁和自动封禁。
    支持查询当前有效的封禁记录。
    """

    __tablename__ = "ip_ban_records"

    # 添加复合索引以优化查询
    __table_args__ = (
        # 查询有效封禁记录的索引
        Index(
            "ix_ip_ban_active",
            "ip",
            "unbanned_at",
            "expires_at",
        ),
    )

    # 主键：UUID 字符串
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # IP 地址（支持 IPv4 和 IPv6）
    ip: Mapped[str] = mapped_column(
        String(45),  # IPv6 最长 45 字符
        nullable=False,
        index=True,
    )

    # 封禁原因
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # 封禁类型：manual（手动）、auto_brute_force（暴力破解）、auto_credential_stuffing（凭据填充）
    ban_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="manual",
    )

    # 封禁时间
    banned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 过期时间（None 表示永久封禁）
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # 操作人 ID（None 表示系统自动封禁）
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
    )

    # 解除封禁时间（None 表示未解除）
    unbanned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 解除封禁的操作人 ID
    unbanned_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
    )

    # 解除封禁的原因
    unban_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # 相关的认证事件数量（用于统计）
    related_event_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    @property
    def is_active(self) -> bool:
        """
        检查封禁是否仍然有效

        Returns:
            True 如果封禁仍然有效，否则 False
        """
        # 已被手动解除
        if self.unbanned_at is not None:
            return False

        # 临时封禁已过期
        if self.expires_at is not None:
            if self.expires_at < datetime.now(timezone.utc):
                return False

        return True

    @property
    def is_permanent(self) -> bool:
        """
        检查是否为永久封禁

        Returns:
            True 如果是永久封禁，否则 False
        """
        return self.expires_at is None

    @property
    def remaining_seconds(self) -> Optional[int]:
        """
        获取剩余封禁时间（秒）

        Returns:
            剩余秒数，永久封禁返回 None，已过期返回 0
        """
        if not self.is_active:
            return 0

        if self.expires_at is None:
            return None

        remaining = (self.expires_at - datetime.now(timezone.utc)).total_seconds()
        return max(0, int(remaining))

    def __repr__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"<IPBanRecord(ip={self.ip}, type={self.ban_type}, status={status})>"
