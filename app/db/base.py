"""
SQLAlchemy 基础模型

提供所有模型的基类和通用 Mixin
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有模型的基类"""

    # 允许使用类型注解
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


class TimestampMixin:
    """时间戳 Mixin，提供 created_at 和 updated_at 字段"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
