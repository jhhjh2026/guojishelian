"""
scripts/seed_db.py - 数据库初始化脚本
运行方式：
  python -m scripts.seed_db
或：
  python scripts/seed_db.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import select

# Ensure repo root is on sys.path so `backend.*` imports work when running script directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.db.models import Base, User, Role, Rule
from backend.app.services.auth_service import hash_password, get_default_role_id
from backend.app.config import get_path_config

# 与 database.py 一致的默认数据库连接
DEFAULT_DB_URL = "sqlite+aiosqlite:///data/issf.db"

engine = create_async_engine(DEFAULT_DB_URL, echo=False, future=True)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("数据库表初始化完成。")

    async with session_factory() as session:
        # 初始化角色
        roles = [
            {"id": str(uuid.uuid4()), "name": "admin", "description": "管理员", "permissions": ["admin", "ask"]},
            {"id": str(uuid.uuid4()), "name": "user", "description": "普通用户", "permissions": ["ask"]},
        ]
        for r in roles:
            exists = await session.execute(select(Role).where(Role.name == r["name"]))
            if not exists.scalar_one_or_none():
                session.add(Role(**r))

        await session.commit()
        print("角色初始化完成：admin / user")

        # 初始化管理员账号（仅当不存在时）
        admin_username = "admin"
        admin_email = "admin@example.com"
        exist = await session.execute(select(User).where(User.username == admin_username))
        if not exist.scalar_one_or_none():
            role_id = await get_default_role_id(session)
            # 确保管理员有 admin 权限
            admin_role = (await session.execute(select(Role).where(Role.name == "admin"))).scalar_one()
            admin = User(
                username=admin_username,
                email=admin_email,
                hashed_password=hash_password("admin123"),
                display_name="系统管理员",
                role_id=admin_role.id,
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            print("默认管理员账号已创建：admin / admin123")
        else:
            print("管理员账号已存在，跳过创建。")

        # 可选：插入示例规则
        sample_rules = [
            {
                "rule_id": "RULE_2026_001",
                "title": "混合团体比赛计分规则",
                "category": "比赛规则",
                "subcategory": "混合团体",
                "content": "取消赋分制，总环值直接决胜。",
                "keywords": ["混合团体", "计分", "赋分制", "环值"],
                "related_rules": [],
                "examples": ["2026年4月格拉纳达站王子菲/盛李豪逆转夺冠"],
                "version": "2026",
                "source": "ISSF 2026 新规",
                "is_published": True,
            }
        ]
        for r in sample_rules:
            exists = await session.execute(select(Rule).where(Rule.rule_id == r["rule_id"]))
            if not exists.scalar_one_or_none():
                session.add(Rule(**r))
        await session.commit()
        print("示例规则导入完成。")


async def reset() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("数据库表已清空。")
    await init()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        asyncio.run(reset())
    else:
        asyncio.run(init())
