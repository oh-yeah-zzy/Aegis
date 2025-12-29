"""
数据库会话管理

提供异步数据库引擎和会话工厂
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# 创建异步数据库引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # 调试模式下打印 SQL
    future=True,
)

# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖函数

    用于 FastAPI 的 Depends 注入

    Yields:
        AsyncSession: 异步数据库会话
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
