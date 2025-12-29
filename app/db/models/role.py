"""
角色和权限模型

实现 RBAC 的核心：角色和权限定义
"""

from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import Boolean, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user_role import UserRole


class Permission(Base, TimestampMixin):
    """
    权限表

    权限码格式建议：{service}:{resource}:{action}
    例如：aegis:users:read, aegis:users:write, order:create
    """

    __tablename__ = "permissions"

    # 主键
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # 权限码：唯一标识，如 aegis:users:read
    code: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )

    # 权限名称（用于显示）
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    # 权限描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # 所属服务码（可选，用于分组）
    service_code: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    # 资源类型
    resource: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    # 操作类型
    action: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )

    # 关系：角色权限关联
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, code={self.code})>"


class Role(Base, TimestampMixin):
    """
    角色表

    角色是权限的集合，用户通过角色获得权限
    """

    __tablename__ = "roles"

    # 主键
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # 角色码：唯一标识
    code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    # 角色名称
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    # 角色描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # 是否为系统角色（系统角色不可删除）
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # 关系：用户角色关联
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    # 关系：角色权限关联
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, code={self.code})>"


class RolePermission(Base):
    """
    角色-权限关联表

    多对多关系的中间表
    """

    __tablename__ = "role_permissions"

    # 复合主键
    role_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # 关系
    role: Mapped["Role"] = relationship("Role", back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship(
        "Permission", back_populates="role_permissions"
    )

    def __repr__(self) -> str:
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id})>"
