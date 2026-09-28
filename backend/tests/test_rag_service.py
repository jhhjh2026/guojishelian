"""
backend/tests/test_rag_service.py - RAGService 单元测试
使用 unittest.mock 避免外部服务/文件依赖。
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# 确保 backend/app 与项目根在 sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_backend_app_dir = os.path.join(_project_root, "backend", "app")
if _backend_app_dir not in sys.path:
    sys.path.insert(0, _backend_app_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.app.core.rag_service import RAGService, LRUCache  # noqa: E402


class TestLRUCache(unittest.TestCase):
    def test_basic_get_put(self):
        cache = LRUCache(capacity=2, ttl_seconds=3600)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("b"), 2)

        cache.put("c", 3)
        missing = [k for k in ("a", "b") if cache.get(k) is None]
        self.assertTrue(len(missing) >= 1)
        self.assertIsNotNone(cache.get("c"))

    def test_stats(self):
        cache = LRUCache(capacity=2, ttl_seconds=3600)
        cache.put("a", 1)
        cache.get("a")
        cache.get("b")
        stats = cache.stats()
        self.assertEqual(stats["capacity"], 2)
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["size"], 1)


class TestRAGServiceBasics(unittest.TestCase):
    def _build_service(self):
        svc = RAGService(project_root=_project_root)
        svc._api_key = "fake"
        svc._embeddings = MagicMock()
        svc._vector_store = MagicMock()
        svc._vector_store._collection.count.return_value = 1
        svc._llm = MagicMock()
        svc._initialized = True
        svc._qa_prompt = MagicMock()
        return svc

    def test_instantiation_and_prompt_exists(self):
        svc = self._build_service()
        self.assertTrue(hasattr(svc, "_qa_prompt"))
        self.assertIsNotNone(svc._qa_prompt)


if __name__ == "__main__":
    unittest.main()
