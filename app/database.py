"""
数据库连接与会话管理（SQLAlchemy 2.0 异步模式）
"""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.models import Base

settings = get_settings()

# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=False,  # 调试时可改为 True 查看 SQL
)

# 异步 Session 工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def _migrate_sqlite(conn) -> None:
    """SQLite 轻量迁移：为已有库补充新增列（create_all 不会 ALTER 旧表）"""
    migrations = [
        "ALTER TABLE jobs ADD COLUMN platform_job_id VARCHAR(128)",
        "ALTER TABLE candidates ADD COLUMN platform VARCHAR(32) DEFAULT 'generic'",
        "ALTER TABLE candidates ADD COLUMN resume_text TEXT",
        "ALTER TABLE candidates ADD COLUMN resume_summary TEXT",
    ]
    for sql in migrations:
        try:
            await conn.execute(text(sql))
        except Exception:
            pass  # 列已存在则忽略


async def init_db() -> None:
    """初始化数据库：建表 + 增量迁移"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_sqlite(conn)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入：提供数据库会话
    请求结束后自动关闭会话
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
