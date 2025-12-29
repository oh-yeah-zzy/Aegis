"""
认证策略模型

用于配置哪些路径需要认证、需要什么权限
支持对远程路由（来自 ServiceAtlas）应用认证策略
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


# 认证策略与权限的多对多关联表
auth_policy_permission = Table(
    "auth_policy_permissions",
    Base.metadata,
    Column("policy_id", Integer, ForeignKey("auth_policies.id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id"), primary_key=True),
)


class AuthPolicy(Base, TimestampMixin):
    """
    认证策略表

    用于配置哪些路径需要认证和权限检查
    对于远程路由（来自 ServiceAtlas），通过路径模式匹配应用认证策略
    """

    __tablename__ = "auth_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 策略名称（用于管理识别）
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # 路径模式（支持通配符）
    # 例如：/** 匹配所有，/deckview-*/** 匹配所有 deckview 开头的服务
    path_pattern: Mapped[str] = mapped_column(String(256), nullable=False)

    # 优先级（数字越大优先级越高，用于路径模式冲突时的选择）
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # 是否需要用户认证
    auth_required: Mapped[bool] = mapped_column(Boolean, default=True)

    # 是否需要服务间认证
    s2s_required: Mapped[bool] = mapped_column(Boolean, default=False)

    # 权限检查模式：any（任一权限即可）或 all（需要所有权限）
    permission_mode: Mapped[str] = mapped_column(String(16), default="any")

    # 是否启用此策略
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # 描述
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 关联的权限列表
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        secondary=auth_policy_permission,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AuthPolicy(id={self.id}, name={self.name}, path={self.path_pattern})>"


# 避免循环导入，在这里导入 Permission
from app.db.models.role import Permission
