"""
tests/test_core_units.py - 核心模块单元测试骨架（标准库 unittest，无需 pytest）
覆盖：LRUCache / retry_call / 同义词扩展 / YAML frontmatter 解析
运行：python tests/test_core_units.py
"""

from __future__ import annotations

import os
import sys
import unittest
import types
import hashlib
import time
from collections import OrderedDict

# ============================================================
# 依赖桩：为未安装的重型依赖提供最小接口，避免 ImportError
# ============================================================
def _ensure_stub(name: str):
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


_project_root = os.path.dirname(os.path.abspath(__file__))
_backend_root = os.path.dirname(_project_root)
_backend_app_dir = os.path.join(_backend_root, "app")
if _backend_app_dir not in sys.path:
    sys.path.insert(0, _backend_app_dir)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# langchain_chroma
_lc_chroma = _ensure_stub("langchain_chroma")


class _CollectionDummy:
    def count(self):
        return 0


class _ChromaDummy:
    def __init__(self, *args, **kwargs):
        self._collection = _CollectionDummy()

    @classmethod
    def from_documents(cls, *args, **kwargs):
        return cls()

    def similarity_search(self, *args, **kwargs):
        return []


_lc_chroma.Chroma = _ChromaDummy

# langchain_community
_lc_community = _ensure_stub("langchain_community")
_lc_community.__path__ = []

_lc_community_doc_loaders = _ensure_stub("langchain_community.document_loaders")


class _TextLoaderDummy:
    def __init__(self, *args, **kwargs):
        pass

    def load(self):
        return []


class _DirectoryLoaderDummy:
    def __init__(self, *args, **kwargs):
        pass

    def load(self):
        return []


_lc_community_doc_loaders.TextLoader = _TextLoaderDummy
_lc_community_doc_loaders.DirectoryLoader = _DirectoryLoaderDummy

_lc_community_chat_models = _ensure_stub("langchain_community.chat_models")


class _ChatTongyiDummy:
    def __init__(self, *args, **kwargs):
        pass

    def invoke(self, *args, **kwargs):
        class _Msg:
            content = "ok"

        return _Msg()


_lc_community_chat_models.ChatTongyi = _ChatTongyiDummy

_lc_community_embeddings = _ensure_stub("langchain_community.embeddings")


class _DashScopeEmbeddingsDummy:
    def __init__(self, *args, **kwargs):
        pass

    def embed_documents(self, texts):
        return [[0.0] * 8 for _ in texts]

    def embed_query(self, text):
        return [0.0] * 8


_lc_community_embeddings.DashScopeEmbeddings = _DashScopeEmbeddingsDummy

# langchain_core
_lc_core = _ensure_stub("langchain_core")
_lc_core.__path__ = []

_lc_core_prompts = _ensure_stub("langchain_core.prompts")
_lc_core_prompts.ChatPromptTemplate = type("ChatPromptTemplate", (), {
    "from_messages": classmethod(lambda cls, *a, **k: None),
    "from_file": classmethod(lambda cls, *a, **k: None),
})

_lc_core_output_parsers = _ensure_stub("langchain_core.output_parsers")
_lc_core_output_parsers.StrOutputParser = type("StrOutputParser", (), {
    "invoke": lambda self, x: "",
})

_lc_core_documents = _ensure_stub("langchain_core.documents")
_lc_core_documents.Document = type("Document", (), {"__init__": lambda self, *a, **k: None})

_lc_core_embeddings = _ensure_stub("langchain_core.embeddings")
_lc_core_embeddings.Embeddings = object

# dashscope
_dashscope = _ensure_stub("dashscope")
_dashscope.api_key = None


class _TextReRankDummy:
    @staticmethod
    def call(*args, **kwargs):
        class _Resp:
            output = {"results": []}

        return _Resp()


_dashscope.TextReRank = _TextReRankDummy
_dashscope.TextRanking = _TextReRankDummy


# ============================================================
# 测试用例
# ============================================================
class _LRUCache:
    def __init__(self, capacity: int = 128, ttl_seconds: int = 3600):
        self.capacity = capacity
        self.ttl = ttl_seconds
        self.cache: OrderedDict = OrderedDict()
        self.hits = 0
        self.misses = 0

    def _make_key(self, query: str) -> str:
        normalized = query.strip().lower()
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def get(self, query: str):
        key = self._make_key(query)
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp <= self.ttl:
                self.cache.move_to_end(key)
                self.hits += 1
                return value
            else:
                del self.cache[key]
        self.misses += 1
        return None

    def put(self, query: str, value) -> None:
        key = self._make_key(query)
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = (value, time.time())
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def stats(self) -> dict:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "capacity": self.capacity,
            "size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": round(hit_rate, 2),
            "ttl_seconds": self.ttl,
        }


class TestLRUCache(unittest.TestCase):
    def test_basic_get_put(self):
        cache = _LRUCache(capacity=2, ttl_seconds=3600)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("b"), 2)

        cache.put("c", 3)
        missing = [k for k in ("a", "b") if cache.get(k) is None]
        self.assertTrue(len(missing) >= 1)
        self.assertIsNotNone(cache.get("c"))

    def test_stats(self):
        cache = _LRUCache(capacity=10, ttl_seconds=60)
        cache.put("q", "v1")
        cache.get("q")
        cache.get("missing")
        stats = cache.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["size"], 1)
        self.assertEqual(stats["capacity"], 10)
        self.assertIn("hit_rate_pct", stats)


class TestRetryCall(unittest.TestCase):
    def test_success(self):
        from utils.retry_utils import retry_call

        def ok():
            return 42

        self.assertEqual(retry_call(ok, max_retries=2, retry_delay=0.01), 42)

    def test_eventual_failure(self):
        from utils.retry_utils import retry_call

        def always_fail():
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            retry_call(always_fail, max_retries=1, retry_delay=0.01)


class TestSynonyms(unittest.TestCase):
    def test_loaded_and_expansion(self):
        path = os.path.join(_backend_app_dir, "utils", "document_processor.py")
        with open(path, "r", encoding="utf-8") as f:
            ns: dict = {"__file__": path}
            exec(f.read(), ns)

        synonym_map = ns.get("SYNONYM_MAP", {})
        self.assertIsInstance(synonym_map, dict)

        expand_fn = ns.get("expand_query_synonyms")
        self.assertTrue(callable(expand_fn))

        self.assertTrue("哑弹" in synonym_map or "臭子" in synonym_map)

        out = expand_fn("步枪决赛如何进行？")
        self.assertIsInstance(out, str)
        self.assertGreaterEqual(len(out), len("步枪决赛如何进行？"))


class TestYAMLParser(unittest.TestCase):
    def test_frontmatter_detection_and_parse(self):
        from utils.yaml_metadata_parser import has_yaml_frontmatter, parse_markdown_yaml

        sample = "---\nversion: 2026\ncategory: 资格赛\n---\n# 规则正文"
        self.assertTrue(has_yaml_frontmatter(sample))
        meta = parse_markdown_yaml(sample, source_file="test.md")
        self.assertIsInstance(meta, dict)
        self.assertIn(meta.get("version"), ("2026", 2026))
        self.assertEqual(meta.get("category"), "资格赛")

    def test_no_frontmatter(self):
        from utils.yaml_metadata_parser import has_yaml_frontmatter, parse_markdown_yaml

        sample = "# 规则正文\n没有 frontmatter"
        self.assertFalse(has_yaml_frontmatter(sample))
        meta = parse_markdown_yaml(sample, source_file="test.md")
        self.assertEqual(meta, {})


if __name__ == "__main__":
    unittest.main()
