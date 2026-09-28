"""
backend/tests/test_admin_integration.py — 管理后台集成测试
直接构造最小 FastAPI App 并挂载 admin router，避免全量启动/模块重载问题。
"""

from __future__ import annotations

import os
import sys
import uuid
import asyncio

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "app"))
sys.path.insert(0, PROJECT_ROOT)


def _build_test_app():
    import importlib
    os.environ["API_TOKEN"] = "dev-secret-key-change-in-production"
    os.chdir(PROJECT_ROOT)
    sys.path.insert(0, PROJECT_ROOT)
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "app"))

    # 1) Reload config and security first
    import backend.app.config as config
    importlib.reload(config)

    import backend.app.utils.security as sec_mod
    importlib.reload(sec_mod)

    import backend.app.services.auth_service as auth_mod
    importlib.reload(auth_mod)

    # 2) Now import admin router so it picks up reloaded security module
    from backend.app.routers.admin import router as admin_router

    # 3) in-memory sqlite
    from backend.app.db.models import Base
    db_url = "sqlite+aiosqlite://"
    engine = create_async_engine(db_url, echo=False, future=True, poolclass=None)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def get_test_db():
        async with async_session() as session:
            yield session

    async def _init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_session() as session:
            role_id = str(uuid.uuid4())
            user_id = str(uuid.uuid4())
            from backend.app.db.models import Role, User
            from backend.app.services.auth_service import hash_password
            role = Role(id=role_id, name="admin", description="管理员", permissions=["admin"])
            session.add(role)
            await session.flush()
            admin = User(
                id=user_id,
                username=f"admin_{uuid.uuid4().hex[:6]}",
                email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
                hashed_password=hash_password("admin123"),
                display_name="管理员",
                role_id=role.id,
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            return admin, user_id

    admin_user, admin_user_id = asyncio.run(_init_db())

    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")

    # override DB dependency used by admin router
    try:
        from backend.app.db.database import get_db as real_get_db
        app.dependency_overrides[real_get_db] = get_test_db
    except Exception:
        pass

    # override security deps AFTER router import so route deps resolve to override
    async def _fake_current_user(request=None, db=Depends(get_test_db)):
        return admin_user

    def _fake_require_permission(perms):
        async def _dep(request=None, db=Depends(get_test_db)):
            return admin_user
        return _dep

    app.dependency_overrides[sec_mod.get_current_user] = _fake_current_user
    app.dependency_overrides[sec_mod.require_permission] = _fake_require_permission

    return app, admin_user, admin_user_id


def _login(user_id: str, username: str, role_id: str) -> str:
    from backend.app.services.auth_service import create_access_token
    token = create_access_token({"sub": user_id, "username": username, "role_id": role_id})
    return token


def test_dashboard_stats():
    app, admin_user, admin_user_id = _build_test_app()
    client = TestClient(app)
    token = _login(admin_user_id, admin_user.username, admin_user.role_id)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/admin/dashboard", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert "data" in body
    assert "total_rules" in body["data"]


def test_rule_crud():
    app, admin_user, admin_user_id = _build_test_app()
    client = TestClient(app)
    token = _login(admin_user_id, admin_user.username, admin_user.role_id)
    headers = {"Authorization": f"Bearer {token}"}

    rule_id = f"RULE_TEST_{uuid.uuid4().hex[:6]}"
    payload = {
        "rule_id": rule_id,
        "title": "测试规则",
        "category": "测试分类",
        "version": "2026",
        "content": "测试内容",
        "keywords": ["测试"],
        "is_published": True,
    }
    resp = client.post("/api/admin/rules", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["id"] is not None

    resp = client.put(f"/api/admin/rules/{rule_id}", json={"title": "测试规则修订"}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True

    resp = client.delete(f"/api/admin/rules/{rule_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
