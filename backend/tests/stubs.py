"""
tests/stubs.py - 为未安装的重型依赖提供最小桩，避免 ImportError
自动安装在 sys.modules，供测试文件导入前执行。
"""

import sys
import types


def _ensure_stub(name: str):
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


def install():
    # ---------- langchain_chroma ----------
    lc_chroma = _ensure_stub("langchain_chroma")

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

    lc_chroma.Chroma = _ChromaDummy

    # ---------- langchain_community ----------
    lc_community = _ensure_stub("langchain_community")
    lc_community.__path__ = []

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

    lc_community_doc_loaders = _ensure_stub("langchain_community.document_loaders")
    lc_community_doc_loaders.TextLoader = _TextLoaderDummy
    lc_community_doc_loaders.DirectoryLoader = _DirectoryLoaderDummy

    class _ChatTongyiDummy:
        def __init__(self, *args, **kwargs):
            pass

        def invoke(self, *args, **kwargs):
            class _Msg:
                content = "ok"

            return _Msg()

    lc_community_chat_models = _ensure_stub("langchain_community.chat_models")
    lc_community_chat_models.ChatTongyi = _ChatTongyiDummy

    class _DashScopeEmbeddingsDummy:
        def __init__(self, *args, **kwargs):
            pass

        def embed_documents(self, texts):
            return [[0.0] * 8 for _ in texts]

        def embed_query(self, text):
            return [0.0] * 8

    lc_community_embeddings = _ensure_stub("langchain_community.embeddings")
    lc_community_embeddings.DashScopeEmbeddings = _DashScopeEmbeddingsDummy

    # ---------- langchain_core ----------
    lc_core = _ensure_stub("langchain_core")
    lc_core.__path__ = []

    lc_core_prompts = _ensure_stub("langchain_core.prompts")
    lc_core_prompts.ChatPromptTemplate = type("ChatPromptTemplate", (), {
        "from_messages": classmethod(lambda cls, *a, **k: None),
        "from_file": classmethod(lambda cls, *a, **k: None),
    })

    lc_core_output_parsers = _ensure_stub("langchain_core.output_parsers")
    lc_core_output_parsers.StrOutputParser = type("StrOutputParser", (), {
        "invoke": lambda self, x: "",
    })

    lc_core_documents = _ensure_stub("langchain_core.documents")
    lc_core_documents.Document = type("Document", (), {"__init__": lambda self, *a, **k: None})

    lc_core_embeddings = _ensure_stub("langchain_core.embeddings")
    lc_core_embeddings.Embeddings = object

    # ---------- dashscope ----------
    dashscope = _ensure_stub("dashscope")
    dashscope.api_key = None

    class _TextReRankDummy:
        @staticmethod
        def call(*args, **kwargs):
            class _Resp:
                output = {"results": []}

            return _Resp()

    dashscope.TextReRank = _TextReRankDummy
    dashscope.TextRanking = _TextReRankDummy


install()
