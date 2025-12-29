"""
用户模型

存储用户基本信息和认证数据
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import Boolean, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user_role import UserRole
    from app.db.models.token import RefreshToken


class User(Base, TimestampMixin):
    """用户表"""

    __tablename__ = "users"

    # 主键：使用 UUID 字符串
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # 用户名：唯一且必填
    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    # 邮箱：唯一且必填
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    # 密码哈希：必填
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # 用户状态
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # 是否为超级管理员
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # 令牌版本：用于使所有令牌失效
    token_version: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # 最后登录时间
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 关系：用户角色（多对多）
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # 关系：刷新令牌（一对多）
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
