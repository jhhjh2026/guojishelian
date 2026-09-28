"""
backend/tests/test_integration.py - 集成测试
覆盖：/api/ask 完整链路（RAGService + Server + 请求/响应格式）
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
        q = (question or "").strip()
        if not q:
            return {
                "success": False,
                "code": "ERR_EMPTY_QUESTION",
                "message": "问题不能为空",
                "data": None,
            }
        return {
            "success": True,
            "code": "OK",
            "message": "success",
            "data": {
                "question": question,
                "expanded_query": question,
                "answer": "这是一个模拟答案。",
                "from_cache": False,
                "latency_ms": 123,
                "show_sources": show_sources,
                "sources": [],
                "cache_info": self.cache.stats(),
            },
        }


def _build_fresh_server(monkeypatch, api_token: str = "", rate_window: int = 60, rate_max: int = 30):
    monkeypatch.setenv("API_TOKEN", api_token)
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", str(rate_window))
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", str(rate_max))

    server = importlib.import_module("backend.app.server")
    importlib.reload(server)
    server._service = _FakeService()
    server.RATE_LIMIT_STATE.clear() if hasattr(server, "RATE_LIMIT_STATE") else None
    return server


def test_ask_endpoint_success(monkeypatch):
    server = _build_fresh_server(monkeypatch)
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    resp = client.post("/api/ask", json={"question": "测试问题", "use_cache": True, "show_sources": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["code"] == "OK"
    assert "data" in body
    assert "answer" in body["data"]
    assert "latency_ms" in body["data"]


def test_ask_endpoint_empty_question(monkeypatch):
    server = _build_fresh_server(monkeypatch)
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    resp = client.post("/api/ask", json={"question": "   ", "use_cache": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["code"] == "ERR_EMPTY_QUESTION"


def test_ask_stream_endpoint(monkeypatch):
    server = _build_fresh_server(monkeypatch)
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    resp = client.post("/api/ask", json={"question": "测试问题", "stream": True})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "data:" in resp.text


def test_health_ready_version_endpoints(monkeypatch):
    server = _build_fresh_server(monkeypatch)
    client = pytest.importorskip("fastapi.testclient").TestClient(server.app)

    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["code"] == "OK"

    resp = client.get("/api/ready")
    assert resp.status_code == 200
    assert resp.json()["code"] == "READY"

    resp = client.get("/api/version")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "issf-rag-assistant"

    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    assert "data" in resp.json()
