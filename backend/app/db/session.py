"""
数据库会话管理 - SQLAlchemy 2.0 异步引擎
使用 async_sessionmaker 创建异步会话，配合 FastAPI 依赖注入
"""

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# 异步引擎 - SQLite需要禁用 same_thread 检查 + WAL模式支持并发读写
_engine_kwargs: dict = {"echo": settings.is_development}
if "sqlite" in settings.database_url:
    _engine_kwargs["connect_args"] = {
        "check_same_thread": False,
        "timeout": 30,  # 增加锁等待超时到30秒
    }

engine = create_async_engine(
    settings.database_url,
    **_engine_kwargs,
)

# SQLite WAL模式: 允许并发读写，解决 "database is locked" 问题
if "sqlite" in settings.database_url:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30秒忙等待
        cursor.execute("PRAGMA synchronous=NORMAL")  # 平衡安全性和性能
        cursor.close()

# 异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入 - 提供数据库会话
    自动管理会话生命周期：异常时回滚，结束时关闭
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库 - 创建所有表（开发环境使用）"""
    from app.db.base import Base
    # 确保所有模型已导入
    from app.models import user, competitor, sentiment, spider, audit, payment  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭数据库引擎连接池"""
    await engine.dispose()
