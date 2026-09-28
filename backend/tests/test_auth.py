"""
tests/test_auth.py - 认证相关测试
"""

from __future__ import annotations

import os
import sys
import uuid
import importlib
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "app"))
sys.path.insert(0, PROJECT_ROOT)


class _FakeService:
    def __init__(self, *args, **kwargs):
        pass

    def ask(self, *args, **kwargs):
        return {"success": True, "code": "OK", "message": "ok", "data": {}}


def _build_server(monkeypatch, api_token=""):
    monkeypatch.setenv("API_TOKEN", api_token)
    server = importlib.import_module("backend.app.server")
    config = importlib.import_module("backend.app.config")
    importlib.reload(config)
    importlib.reload(server)
    server.SECURITY_CONFIG = config.SECURITY_CONFIG
    server.RUNTIME_CONFIG = config.RUNTIME_CONFIG
    server._service = _FakeService()
    return server


class _FakeCache:
    def stats(self):
        return {"capacity": 128, "size": 0, "hits": 0, "misses": 0, "hit_rate_pct": 0.0, "ttl_seconds": 3600}


def test_login_success(monkeypatch):
    server = _build_server(monkeypatch)
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "access_token" in data.get("data", {})


def test_login_failure(monkeypatch):
    server = _build_server(monkeypatch)
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_register_then_login(monkeypatch):
    server = _build_server(monkeypatch)
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    username = f"testuser_{uuid.uuid4().hex[:6]}"
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    response = client.post("/api/auth/register", json={"username": username, "email": email, "password": "test123"})
    assert response.status_code == 200, response.text

    response = client.post("/api/auth/login", json={"username": username, "password": "test123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data.get("data", {})
