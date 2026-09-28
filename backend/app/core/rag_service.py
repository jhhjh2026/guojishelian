"""
backend/app/core/rag_service.py - ISSF 2026 RAG 核心业务逻辑（领域层）
职责：RAGService / LRUCache / API Adapter 核心实现
"""

import os
import re
import time
import json
import hashlib
import logging
from collections import OrderedDict
from typing import Optional

from ..config import (
    MODEL_CONFIG,
    CACHE_CONFIG,
    RETRY_CONFIG,
    get_path_config,
)
from ..utils import (
    expand_query_synonyms,
    get_or_create_vector_store,
    rebuild_vector_store,
    delete_vector_store,
    retry_call,
    rerank_documents,
)
from langchain_community.chat_models import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    _HAS_HF_EMBEDDINGS = True
except Exception:
    _HAS_HF_EMBEDDINGS = False

logger = logging.getLogger("rag_service")

class LRUCache:
    """固定大小的 LRU 缓存，内存版，保持兼容"""

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

class RAGService:
    """
    ISSF 2026 RAG 问答核心服务（含 qwen3-vl-rerank 两阶段重排）
    链路：用户query → 同义词扩展 → 向量粗召回 → qwen3-vl-rerank 精排 → LLM 生成
    说明：Prompt 模板已从代码中抽离至 backend/app/prompts/qa_prompt.txt
    """

    GREETING_KEYWORDS = [
        "你好", "您好", "hi", "hello", "hey", "在吗", "在不在", "嗨", "哈喽",
        "你好呀", "您好呀", "你好吗", "早上好", "下午好", "晚上好", "大家好",
        "你是谁", "你叫什么", "介绍一下你自己", "自我介绍", "你是干嘛的",
        "你是什么", "请问你是谁", "你能做什么", "你有什么用",
        "谢谢", "感谢", "多谢", "谢谢你", "感谢你", "非常感谢", "十分感谢",
        "谢谢啦", "thanks", "thank you", "thx", "3q", "ty",
        "再见", "拜拜", "bye", "goodbye", "bye bye", "回见", "下次见", "再会",
        "先这样", "走了", "撤了",
        "好的", "好滴", "好", "ok", "okay", "收到", "了解", "明白了", "知道了",
        "不错", "很棒", "厉害", "赞", "牛", "666", "点赞",
        "对不起", "抱歉", "不好意思", "打扰了", "麻烦了", "sorry", "apologize",
    ]

    MEANINGLESS_INPUTS = ["", " ", "嗯", "啊", "哦", "噢", "呃", "额", "唔", "嘿嘿", "哈哈",
                          "???", "？？？", "!!!", "！！！"]

    def __init__(self, project_root: str = None, cache_capacity: int = None, cache_ttl: int = None):
        self._path_cfg = get_path_config(project_root)
        self.project_root = self._path_cfg.PROJECT_ROOT
        self.data_dir = self._path_cfg.RULES_DIR
        self.persist_directory = self._path_cfg.VECTOR_STORE_DIR

        cap = cache_capacity if cache_capacity is not None else CACHE_CONFIG.CACHE_CAPACITY
        ttl = cache_ttl if cache_ttl is not None else CACHE_CONFIG.CACHE_TTL_SECONDS
        self.cache = LRUCache(capacity=cap, ttl_seconds=ttl)

        self._api_key = None
        self._embeddings = None
        self._vector_store = None
        self._llm = None
        self._qa_prompt = None
        self._output_parser = StrOutputParser()
        self._initialized = False

    def initialize(self) -> dict:
        try:
            self._api_key = MODEL_CONFIG.DASHSCOPE_API_KEY
            if not MODEL_CONFIG.validate_api_key():
                return {"success": False, "message": "未配置 DASHSCOPE_API_KEY 或无效", "code": "ERR_NO_API_KEY"}

            provider = getattr(MODEL_CONFIG, "EMBEDDING_PROVIDER", "dashscope").lower()
            if provider == "huggingface":
                if not _HAS_HF_EMBEDDINGS:
                    return {
                        "success": False,
                        "message": "未安装 HuggingFaceEmbeddings 依赖",
                        "code": "ERR_NO_HF_EMBEDDINGS",
                    }
                hf_model = MODEL_CONFIG.EMBEDDING_HF_MODEL
                hf_device = getattr(MODEL_CONFIG, "EMBEDDING_HF_DEVICE", "cpu")
                hf_mirror = getattr(MODEL_CONFIG, "EMBEDDING_HF_MIRROR", None)
                hf_local_dir = getattr(MODEL_CONFIG, "EMBEDDING_HF_LOCAL_DIR", None)
                hf_kwargs = {"device": hf_device}
                if hf_mirror:
                    os.environ.setdefault("HF_ENDPOINT", hf_mirror)
                effective_model = hf_local_dir if hf_local_dir and os.path.isdir(hf_local_dir) else hf_model
                self._embeddings = HuggingFaceEmbeddings(model_name=effective_model, model_kwargs=hf_kwargs)
                logger.info(f"HuggingFace Embedding 初始化完成: provider=huggingface model={effective_model} device={hf_device} mirror={hf_mirror or 'default'} local={bool(hf_local_dir and os.path.isdir(hf_local_dir))}")
            else:
                self._embeddings = DashScopeEmbeddings(
                    model=MODEL_CONFIG.EMBEDDING_MODEL,
                    dashscope_api_key=self._api_key,
                )
                logger.info(f"DashScope Embedding 初始化完成: model={MODEL_CONFIG.EMBEDDING_MODEL}")

            self._vector_store = get_or_create_vector_store(
                persist_directory=self.persist_directory,
                rules_dir=self.data_dir,
                embeddings=self._embeddings
            )
            if self._vector_store is None:
                return {"success": False, "message": "向量存储加载/构建失败", "code": "ERR_VECTOR_STORE"}

            vector_count = self._vector_store._collection.count()
            logger.info(f"向量存储加载完成，共 {vector_count} 个向量")

            self._llm = ChatTongyi(
                model=MODEL_CONFIG.LLM_MODEL,
                dashscope_api_key=self._api_key,
                temperature=MODEL_CONFIG.LLM_TEMPERATURE,
            )
            prompt_path = os.path.join(self._path_cfg.PROMPTS_DIR, "qa_prompt.txt")
            if not os.path.exists(prompt_path):
                raise FileNotFoundError(f"Prompt 模板文件不存在: {prompt_path}")
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_text = f.read()
            self._qa_prompt = ChatPromptTemplate.from_messages([
                ("system", prompt_text),
                ("human", "{question}\n\n【规则依据】\n{context}"),
            ])

            logger.info(
                f"QA 链路构建完成 (LLM={MODEL_CONFIG.LLM_MODEL}, "
                f"粗召回TopK={MODEL_CONFIG.RETRIEVER_TOP_K}, "
                f"重排={MODEL_CONFIG.RERANK_ENABLED}({MODEL_CONFIG.RERANK_MODEL})"
                f"→精排TopN={MODEL_CONFIG.RERANK_TOP_N})"
            )

            self._initialized = True
            return {
                "success": True,
                "message": "RAG 服务初始化成功",
                "code": "OK",
                "details": {
                    "project_root": self.project_root,
                    "rules_dir": self.data_dir,
                    "vector_store_dir": self.persist_directory,
                    "vector_count": vector_count,
                    "cache_capacity": self.cache.capacity,
                    "cache_ttl_seconds": self.cache.ttl,
                    "llm_model": MODEL_CONFIG.LLM_MODEL,
                    "embedding_model": MODEL_CONFIG.EMBEDDING_MODEL,
                    "retriever_top_k": MODEL_CONFIG.RETRIEVER_TOP_K,
                    "prompt_path": prompt_path,
                }
            }
        except Exception as e:
            logger.error(f"RAGService 初始化失败: {e}", exc_info=True)
            return {"success": False, "message": f"初始化异常: {str(e)}", "code": "ERR_INIT_EXCEPTION"}

    def force_rebuild_vector_store(self) -> bool:
        if self._embeddings is None:
            logger.error("Embedding 模型未初始化，无法重建向量库")
            return False
        delete_vector_store(self.persist_directory)
        self._vector_store = rebuild_vector_store(
            persist_directory=self.persist_directory,
            rules_dir=self.data_dir,
            embeddings=self._embeddings
        )
        return self._vector_store is not None

    def _expand_query_synonyms(self, query: str) -> str:
        return expand_query_synonyms(query, max_expanded_terms=5)

    def _is_greeting_query(self, query: str) -> bool:
        q = query.strip()
        if q in self.MEANINGLESS_INPUTS:
            return True
        if len(q) > 20:
            return False
        ql = q.lower()
        return any(kw.lower() in ql for kw in self.GREETING_KEYWORDS)

    def _make_data(self, question: str, expanded_query: str, answer: str,
                   from_cache: bool, latency_ms: int, show_sources: bool = False,
                   sources: list = None) -> dict:
        return {
            "question": question,
            "expanded_query": expanded_query,
            "answer": answer,
            "from_cache": from_cache,
            "latency_ms": latency_ms,
            "show_sources": show_sources,
            "sources": sources or [],
            "cache_info": self.cache.stats()
        }

    def _make_error(self, code: str, message: str, question: str,
                    expanded_query: str, latency_ms: int) -> dict:
        return {
            "success": False,
            "code": code,
            "message": message,
            "data": self._make_data(question, expanded_query, "", False, latency_ms)
        }

    def _make_success(self, question: str, expanded_query: str, answer: str,
                      latency_ms: int, show_sources: bool = False, sources: list = None) -> dict:
        return {
            "success": True,
            "code": "OK",
            "message": "success",
            "data": self._make_data(question, expanded_query, answer, False, latency_ms,
                                    show_sources=show_sources, sources=sources)
        }

    def ask(self, question: str, use_cache: bool = True, show_sources: bool = False) -> dict:
        start_ts = time.time()

        if not self._initialized:
            return {
                "success": False,
                "code": "ERR_NOT_INIT",
                "message": "RAG 服务未初始化，请先调用 initialize()",
                "data": None
            }

        question = (question or "").strip()
        if not question:
            return self._make_error("ERR_EMPTY_QUESTION", "问题不能为空", "", "", 0)

        if self._is_greeting_query(question):
            latency_ms = int((time.time() - start_ts) * 1000)
            return self._make_success(
                question, question,
                "您好！我是 ISSF 2026 射击规则问答助手，请问有什么射击规则相关的问题需要解答？",
                latency_ms
            )

        if use_cache:
            cached = self.cache.get(question)
            if cached is not None:
                latency_ms = int((time.time() - start_ts) * 1000)
                logger.info(f"[缓存命中] 问题: {question[:30]}... 耗时 {latency_ms}ms")
                cached["data"]["from_cache"] = True
                cached["data"]["latency_ms"] = latency_ms
                cached["data"]["cache_info"] = self.cache.stats()
                return cached

        expanded_query = self._expand_query_synonyms(question)

        t0 = time.time()
        try:
            raw_retrieved = retry_call(
                self._vector_store.similarity_search,
                expanded_query,
                k=MODEL_CONFIG.RETRIEVER_TOP_K,
                max_retries=RETRY_CONFIG.MAX_RETRIES,
                retry_delay=RETRY_CONFIG.RETRY_DELAY_SECONDS,
                backoff_factor=2.0,
            )
        except Exception as e:
            latency_ms = int((time.time() - start_ts) * 1000)
            logger.error(f"向量库检索失败: {e}", exc_info=True)
            return self._make_error("ERR_VECTOR_SEARCH", f"向量库检索异常: {str(e)}",
                                    question, expanded_query, latency_ms)
        t_retrieval = int((time.time() - t0) * 1000)

        t1 = time.time()
        if MODEL_CONFIG.RERANK_ENABLED and raw_retrieved:
            reranked_docs = rerank_documents(
                query=question,
                documents=raw_retrieved,
                api_key=self._api_key,
                model=MODEL_CONFIG.RERANK_MODEL,
                top_n=MODEL_CONFIG.RERANK_TOP_N,
                return_documents=MODEL_CONFIG.RERANK_RETURN_DOCUMENTS,
                max_retries=RETRY_CONFIG.MAX_RETRIES,
                retry_delay=RETRY_CONFIG.RETRY_DELAY_SECONDS,
            )
            final_docs = reranked_docs
            rerank_tag = "✅重排"
        else:
            final_docs = raw_retrieved[:MODEL_CONFIG.RERANK_TOP_N]
            rerank_tag = "无重排"
        t_rerank = int((time.time() - t1) * 1000)

        logger.info(
            f"[检索链路] 粗召回={len(raw_retrieved)} -> {rerank_tag}后={len(final_docs)} "
            f"(top_n={MODEL_CONFIG.RERANK_TOP_N})"
        )

        context_str = "\n\n---\n\n".join(doc.page_content for doc in final_docs)

        t2 = time.time()
        try:
            messages = self._qa_prompt.format_messages(
                context=context_str,
                question=question,
            )
            llm_result = retry_call(
                self._llm.invoke,
                messages,
                max_retries=RETRY_CONFIG.MAX_RETRIES,
                retry_delay=RETRY_CONFIG.RETRY_DELAY_SECONDS,
                backoff_factor=2.0,
            )
            answer = self._output_parser.invoke(llm_result).strip()
            answer = sanitize_answer(answer)
            t_llm = int((time.time() - t2) * 1000)
        except Exception as e:
            latency_ms = int((time.time() - start_ts) * 1000)
            logger.error(f"LLM 生成答案失败: {e}", exc_info=True)
            return self._make_error("ERR_RAG_EXCEPTION", f"RAG 调用异常: {str(e)}",
                                    question, expanded_query, latency_ms)

        sources = []
        if show_sources:
            for doc in final_docs:
                source_file = doc.metadata.get("source_file") or doc.metadata.get("file_name") or doc.metadata.get("source", "")
                snippet = (doc.page_content or "").strip().replace("\n", " ")[:140]
                score = doc.metadata.get("rerank_score")
                score_str = f"{score:.4f}" if isinstance(score, (int, float)) else "n/a"
                sources.append({
                    "source_file": source_file,
                    "snippet": snippet,
                    "rerank_score": score_str,
                })

        latency_ms = int((time.time() - start_ts) * 1000)
        response = self._make_success(
            question, expanded_query, answer, latency_ms,
            show_sources=show_sources,
            sources=sources,
        )

        if use_cache and answer:
            self.cache.put(question, response)

        logger.info(
            f"[⏱️ 耗时] 检索={t_retrieval}ms | 重排={t_rerank}ms | LLM={t_llm}ms | "
            f"总计={latency_ms}ms | Q: {question[:30]}..."
        )
        return response

    def cache_stats(self) -> dict:
        return self.cache.stats()

    def clear_cache(self) -> None:
        self.cache.cache.clear()
        self.cache.hits = 0
        self.cache.misses = 0
        logger.info("缓存已清空")

_FORBIDDEN_REF_PATTERNS: list[str] = [
    "文档1", "文档2", "文档3", "文档4", "文档5",
    "参考文档", "上下文", "依据上述", "根据以上",
    "根据文档", "根据上述", "以上内容", "上述内容",
    "资料来源", "参考资料",
]

_EMOJI_PATTERN: re.Pattern = re.compile(
    "["
    "\U0001F300-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\u2600-\u27BF"
    "\u2B50"
    "]+",
    re.UNICODE,
)

def sanitize_answer(text: str) -> str:
    """对 LLM 输出进行后处理：剔除追溯性表述、emoji"""
    if not text:
        return text
    for phrase in _FORBIDDEN_REF_PATTERNS:
        if phrase in text:
            logger.warning("sanitize: 删除含 '%s' 的回答片段", phrase)
            idx = text.find(phrase)
            end = text.find("。", idx) if text.find("。", idx) != -1 else len(text)
            sentence_start = text.rfind("。", 0, idx)
            sentence_start = sentence_start + 1 if sentence_start != -1 else 0
            text = text[:sentence_start] + text[end:]
    text = _EMOJI_PATTERN.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

class RAGApiAdapter:
    @staticmethod
    def _gen_request_id() -> str:
        return f"req_{int(time.time()*1000)}_{os.getpid()}"

    @staticmethod
    def handle_ask(service: RAGService, payload) -> str:
        timestamp = int(time.time())
        request_id = RAGApiAdapter._gen_request_id()

        try:
            if isinstance(payload, str):
                payload = json.loads(payload)
            if not isinstance(payload, dict):
                raise ValueError("payload 必须是 dict 或 JSON 字符串")
        except json.JSONDecodeError as e:
            return json.dumps({
                "success": False,
                "code": "ERR_INVALID_JSON",
                "message": f"JSON 解析失败: {str(e)}",
                "request_id": request_id,
                "timestamp": timestamp,
                "data": None
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({
                "success": False,
                "code": "ERR_INVALID_PAYLOAD",
                "message": str(e),
                "request_id": request_id,
                "timestamp": timestamp,
                "data": None
            }, ensure_ascii=False, indent=2)

        question = payload.get("question", "").strip()
        use_cache = payload.get("use_cache", True)
        show_sources = payload.get("show_sources", False)

        if not question:
            return json.dumps({
                "success": False,
                "code": "ERR_EMPTY_QUESTION",
                "message": "问题不能为空",
                "request_id": request_id,
                "timestamp": timestamp,
                "data": None
            }, ensure_ascii=False, indent=2)

        result = service.ask(question=question, use_cache=use_cache, show_sources=show_sources)
        result["request_id"] = request_id
        result["timestamp"] = timestamp
        return json.dumps(result, ensure_ascii=False, indent=2)