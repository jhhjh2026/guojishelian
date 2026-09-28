"""
backend/tests/test_server.py - FastAPI 服务层测试
覆盖：健康检查、就绪检查、版本信息、鉴权、限流、静态托管、SSE 流式输出
"""

from __future__ import annotations

import os
import sys
import importlib
from unittest.mock import MagicMock

import pytest

# 确保可导入 backend.app.server
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_backend_app_dir = os.path.join(_project_root, "backend", "app")
if _backend_app_dir not in sys.path:
    sys.path.insert(0, _backend_app_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


class _FakeCache:
    def stats(self) -> dict:
        return {
            "capacity": 128,
            "size": 0,
            "hits": 0,
            "misses": 0,
            "hit_rate_pct": 0.0,
            "ttl_seconds": 3600,
        }


class _FakeService:
    def __init__(self, *args, **kwargs):
        self.cache = _FakeCache()

    def ask(self, question: str, use_cache: bool = True, show_sources: bool = False) -> dict:
        return {
            "success": True,
            "code": "OK",
            "message": "ok",
            "data": {"answer": "fake", "latency_ms": 1, "from_cache": False},
        }


def _build_fresh_server(monkeypatch, api_token: str = "", rate_window: int = 60, rate_max: int = 30):
    monkeypatch.setenv("API_TOKEN", api_token)
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", str(rate_window))
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", str(rate_max))

    server = importlib.import_module("backend.app.server")
    config = importlib.import_module("backend.app.config")
    importlib.reload(config)
    importlib.reload(server)

    # Sync fresh config objects into server module globals
    server.MODEL_CONFIG = config.MODEL_CONFIG
    server.CACHE_CONFIG = config.CACHE_CONFIG
    server.RETRY_CONFIG = config.RETRY_CONFIG
    server.SECURITY_CONFIG = config.SECURITY_CONFIG
    server.RUNTIME_CONFIG = config.RUNTIME_CONFIG

    server._RATE_LIMIT_STATE.clear()
    server._service = _FakeService()
    server._get_service = MagicMock(return_value=_FakeService())
    return server


def test_health_returns_ok(monkeypatch):
    server = _build_fresh_server(monkeypatch)
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["code"] == "OK"
    assert "data" in data
    assert "llm_model" in data["data"]
    assert "embedding_model" in data["data"]


def test_ask_requires_auth_when_token_set(monkeypatch):
    server = _build_fresh_server(monkeypatch, api_token="secret-token")
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    resp = client.post("/api/ask", json={"question": "测试问题"})
    assert resp.status_code == 401

    resp = client.post("/api/ask", json={"question": "测试问题"}, headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 403

    resp = client.post("/api/ask", json={"question": "测试问题"}, headers={"Authorization": "Bearer secret-token"})
    assert resp.status_code == 200


def test_rate_limit_triggers(monkeypatch):
    server = _build_fresh_server(monkeypatch, api_token="", rate_window=60, rate_max=2)
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    for _ in range(2):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    resp = client.get("/api/health")
    assert resp.status_code == 429
    body = resp.json()
    assert body["code"] == "RATE_LIMIT_EXCEEDED"


def test_ready_and_version(monkeypatch):
    server = _build_fresh_server(monkeypatch)
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    resp = client.get("/api/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["code"] == "READY"
    assert "data" in data

    resp = client.get("/api/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["code"] == "OK"
    assert data["data"]["name"] == "issf-rag-assistant"


def test_index_html_served(monkeypatch):
    server = _build_fresh_server(monkeypatch)
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<!doctype html>" in response.text.lower()
    assert "issf" in response.text.lower()


def test_debug_paths(monkeypatch):
    server = _build_fresh_server(monkeypatch)
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    response = client.get("/debug/paths")
    assert response.status_code == 200
    data = response.json()
    assert "project_root" in data
    assert "paths" in data
    assert "exists" in data


def test_ask_stream_returns_sse(monkeypatch):
    server = _build_fresh_server(monkeypatch, api_token="secret-token")
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    resp = client.post("/api/ask", json={"question": "测试问题", "stream": True}, headers={"Authorization": "Bearer secret-token"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert "data:" in body
