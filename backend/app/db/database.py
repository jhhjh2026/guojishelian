"""
database.py - 数据库会话管理
支持 MySQL/SQLite，优先使用 MySQL（通过 DATABASE_URL 配置）。
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from ..config import get_path_config
from ..utils.logger import setup_logging

logger, _ = setup_logging(log_name="database", project_root=get_path_config().PROJECT_ROOT)


def _get_database_url() -> str:
    """从环境变量或 .env 获取数据库连接串，默认 SQLite 便于本地启动。"""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    # 默认 SQLite 异步驱动
    db_path = os.path.join(get_path_config().DATA_DIR, "issf.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return f"sqlite+aiosqlite:///{db_path}"


DATABASE_URL = _get_database_url()

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def init_db():
    """初始化数据库表结构。"""
    from ..db.models import Base  # noqa: F401 确保模型已注册
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表初始化完成: %s", DATABASE_URL)


async def check_db_connection() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover - 网络/配置错误
        logger.warning("数据库连接失败: %s", exc)
        return False
