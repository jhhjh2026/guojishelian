"""
server.py - FastAPI 应用入口
提供 /api/ask 与 /api/health 两个接口，便于前后端联调与部署。
启动：
  python -m backend.app.server
或：
  uvicorn backend.app.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import sys
import time
import json
import logging
import hashlib
import threading
import uuid
from typing import Optional, Dict, Tuple, AsyncGenerator
from contextlib import asynccontextmanager

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field

from .config import (
    MODEL_CONFIG,
    SECURITY_CONFIG,
    RUNTIME_CONFIG,
    get_path_config,
)
from .utils import setup_logging, Metrics
from .core.rag_service import RAGService, sanitize_answer
from .routes import api_router

_logger_inst, _ = setup_logging(
    log_name="server",
    project_root=_PROJECT_ROOT,
    level=getattr(logging, RUNTIME_CONFIG.LOG_LEVEL.upper(), logging.INFO),
)
logger = _logger_inst

app_metrics = Metrics()

# ===== lifespan 异步上下文管理器 =====

@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info(
        "服务启动: host=%s port=%s workers=%s",
        RUNTIME_CONFIG.HOST, RUNTIME_CONFIG.PORT, RUNTIME_CONFIG.WORKERS,
    )
    yield
    logger.info("服务关闭")

app = FastAPI(
    title=RUNTIME_CONFIG.APP_TITLE,
    description="基于 LangChain + RAG 的射击规则问答服务",
    version=RUNTIME_CONFIG.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_RATE_LIMIT_STATE: Dict[str, Tuple[float, int]] = {}
_RATE_LIMIT_LOCK = threading.Lock()

def _client_key(request: Request) -> str:
    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return "token:" + hashlib.sha256(token.encode("utf-8")).hexdigest()
    client = getattr(request, "client", None)
    if client is not None and hasattr(client, "host"):
        ip = client.host
    else:
        ip = "unknown"
    return "ip:" + ip

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    key = _client_key(request)
    now = time.time()
    with _RATE_LIMIT_LOCK:
        window_start, count = _RATE_LIMIT_STATE.get(key, (now, 0))
        if now - window_start >= SECURITY_CONFIG.RATE_LIMIT_WINDOW_SECONDS:
            window_start = now
            count = 0
        count += 1
        _RATE_LIMIT_STATE[key] = (window_start, count)
        if count > SECURITY_CONFIG.RATE_LIMIT_MAX_REQUESTS:
            retry_after = max(1, int(SECURITY_CONFIG.RATE_LIMIT_WINDOW_SECONDS - (now - window_start)))
            logger.warning("限流触发: %s, count=%s", key, count)
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"请求过于频繁，请 {retry_after} 秒后重试。",
                    "timestamp": int(now),
                    "data": None,
                },
                headers={"Retry-After": str(retry_after)},
            )
    return await call_next(request)

async def _optional_auth(_request: Request) -> None:
    api_token = (SECURITY_CONFIG.API_TOKEN or "").strip()
    if not api_token:
        return
    auth = _request.headers.get("authorization", "").strip()
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少鉴权信息")
    token = auth.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token 为空")
    if token != api_token:
        raise HTTPException(status_code=403, detail="Token 无效")

_FRONTEND_DIR = os.path.join(_PROJECT_ROOT, "frontend")

_service: Optional[RAGService] = None

class AskRequest(BaseModel):
    question: str = Field(..., description="用户问题")
    use_cache: bool = Field(True, description="是否使用缓存")
    show_sources: bool = Field(False, description="是否返回引用来源")
    stream: bool = Field(False, description="是否使用 SSE 流式返回")

class HealthResponse(BaseModel):
    success: bool
    code: str
    message: str
    timestamp: int
    data: dict

class ReadyResponse(BaseModel):
    success: bool
    code: str
    message: str
    timestamp: int
    data: dict

class VersionResponse(BaseModel):
    success: bool
    code: str
    message: str
    timestamp: int
    data: dict

def _get_service() -> RAGService:
    global _service
    if _service is None:
        svc = RAGService(project_root=_PROJECT_ROOT)
        init = svc.initialize()
        if not init.get("success"):
            raise RuntimeError(f"RAG 服务初始化失败: {init.get('message')}")
        _service = svc
    return _service

class _RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex}"
        request.state.request_id = request_id
        start = time.time()
        response = await call_next(request)
        latency_ms = int((time.time() - start) * 1000)
        if latency_ms > 3000:
            logger.warning(
                "slow request: method=%s path=%s status=%s latency_ms=%s request_id=%s",
                request.method, request.url.path, response.status_code,
                latency_ms, request_id,
            )
        app_metrics.record(response.status_code, latency_ms)
        return response

class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=()")
        return response

class _RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_size: int = 512 * 1024):
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit():
            if int(content_length) > self.max_size:
                return JSONResponse(
                    status_code=413,
                    content={
                        "success": False,
                        "code": "PAYLOAD_TOO_LARGE",
                        "message": f"请求体过大，超过 {self.max_size} 字节限制",
                        "timestamp": int(time.time()),
                        "data": None,
                    },
                )
        return await call_next(request)

app.add_middleware(_RequestIdMiddleware)
app.add_middleware(_SecurityHeadersMiddleware)
app.add_middleware(_RequestSizeLimitMiddleware)

app.include_router(api_router)

@app.get("/api/health", response_model=HealthResponse)
async def health():
    try:
        svc = _get_service()
        cache_stats = svc.cache.stats()
        return {
            "success": True,
            "code": "OK",
            "message": "服务正常",
            "timestamp": int(time.time()),
            "data": {
                "llm_model": MODEL_CONFIG.LLM_MODEL,
                "embedding_provider": getattr(MODEL_CONFIG, "EMBEDDING_PROVIDER", "dashscope"),
                "embedding_model": MODEL_CONFIG.EMBEDDING_MODEL,
                "rerank_enabled": MODEL_CONFIG.RERANK_ENABLED,
                "cache": cache_stats,
            },
        }
    except Exception as e:
        logger.warning("/api/health 降级返回: %s", e)
        return {
            "success": False,
            "code": "INIT_FAILED",
            "message": str(e),
            "timestamp": int(time.time()),
            "data": {
                "llm_model": MODEL_CONFIG.LLM_MODEL,
                "embedding_provider": getattr(MODEL_CONFIG, "EMBEDDING_PROVIDER", "dashscope"),
                "embedding_model": MODEL_CONFIG.EMBEDDING_MODEL,
                "rerank_enabled": MODEL_CONFIG.RERANK_ENABLED,
                "cache": {"capacity": 0, "size": 0, "hits": 0, "misses": 0, "hit_rate_pct": 0.0, "ttl_seconds": 0},
            },
        }

@app.get("/api/ready", response_model=ReadyResponse)
async def ready():
    try:
        svc = _get_service()
        cache_stats = svc.cache.stats()
        return {
            "success": True,
            "code": "READY",
            "message": "服务就绪",
            "timestamp": int(time.time()),
            "data": {
                "llm_model": MODEL_CONFIG.LLM_MODEL,
                "embedding_model": MODEL_CONFIG.EMBEDDING_MODEL,
                "rerank_enabled": MODEL_CONFIG.RERANK_ENABLED,
                "cache": cache_stats,
                "project_root": _PROJECT_ROOT,
                "frontend_indexed": os.path.isfile(os.path.join(_FRONTEND_DIR, "index.html")),
            },
        }
    except Exception as e:
        logger.error("/api/ready 失败: %s", e, exc_info=True)
        return {
            "success": False,
            "code": "NOT_READY",
            "message": str(e),
            "timestamp": int(time.time()),
            "data": None,
        }

@app.get("/api/version", response_model=VersionResponse)
async def version():
    return {
        "success": True,
        "code": "OK",
        "message": "版本信息",
        "timestamp": int(time.time()),
        "data": {
            "name": "issf-rag-assistant",
            "version": RUNTIME_CONFIG.APP_VERSION,
            "ui": "frontend/index.html",
        },
    }

@app.get("/api/metrics")
async def metrics():
    return {
        "success": True,
        "code": "OK",
        "message": "metrics",
        "timestamp": int(time.time()),
        "data": app_metrics.snapshot(),
    }

@app.get("/")
async def index():
    index_path = os.path.join(_FRONTEND_DIR, "index.html")
    return FileResponse(index_path, media_type="text/html")

@app.get("/debug/paths")
async def debug_paths():
    path_cfg = get_path_config(project_root=_PROJECT_ROOT)
    return {
        "project_root": _PROJECT_ROOT,
        "cwd": os.getcwd(),
        "server_file": os.path.abspath(__file__),
        "paths": {
            "PROJECT_ROOT": path_cfg.PROJECT_ROOT,
            "DATA_DIR": path_cfg.DATA_DIR,
            "RULES_DIR": path_cfg.RULES_DIR,
            "VECTOR_STORE_DIR": path_cfg.VECTOR_STORE_DIR,
            "PROMPTS_DIR": getattr(path_cfg, 'PROMPTS_DIR', None),
            "FRONTEND_DIR": _FRONTEND_DIR,
        },
        "exists": {
            "rules_dir": os.path.isdir(path_cfg.RULES_DIR),
            "vector_store_dir": os.path.isdir(path_cfg.VECTOR_STORE_DIR),
            "frontend_index_html": os.path.isfile(os.path.join(_FRONTEND_DIR, "index.html")),
        },
    }

async def _sse_ask(svc: RAGService, question: str, use_cache: bool, show_sources: bool) -> AsyncGenerator[bytes, None]:
    request_id = f"req_{int(time.time()*1000)}_{os.getpid()}"
    start_ts = time.time()
    try:
        result = svc.ask(question, use_cache=use_cache, show_sources=show_sources)
        if result.get("data") and isinstance(result["data"], dict) and result["data"].get("answer"):
            result["data"]["answer"] = sanitize_answer(result["data"]["answer"])
        latency = int((time.time() - start_ts) * 1000)
        payload = {
            "success": result.get("success"),
            "code": result.get("code"),
            "message": result.get("message"),
            "request_id": request_id,
            "timestamp": int(time.time()),
            "latency_ms": latency,
            "data": result.get("data"),
        }
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
    except Exception as e:
        logger.error(f"/api/ask 异常: {e}", exc_info=True)
        payload = {
            "success": False,
            "code": "ERR_INTERNAL",
            "message": str(e),
            "request_id": request_id,
            "timestamp": int(time.time()),
            "latency_ms": int((time.time() - start_ts) * 1000),
            "data": None,
        }
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

@app.post("/api/ask")
async def ask(req: AskRequest):
    svc = _get_service()
    request_id = f"req_{int(time.time()*1000)}_{os.getpid()}"
    t0 = time.time()
    try:
        moderation_enabled = os.getenv("CONTENT_MODERATION_ENABLED", "false").lower() == "true"
        if moderation_enabled:
            try:
                from .services.moderation import default_moderation
                hit = default_moderation.contains_sensitive(req.question)
                if hit:
                    return {
                        "success": False,
                        "code": "CONTENT_REJECTED",
                        "message": "问题包含敏感内容，请调整后重试",
                        "timestamp": int(time.time()),
                        "data": None,
                    }
            except ImportError:
                pass

        if req.stream:
            return StreamingResponse(
                _sse_ask(svc, req.question, req.use_cache, req.show_sources),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        result = svc.ask(req.question, use_cache=req.use_cache, show_sources=req.show_sources)
        latency = int((time.time() - t0) * 1000)
        payload = {
            "success": result.get("success"),
            "code": result.get("code"),
            "message": result.get("message"),
            "request_id": request_id,
            "timestamp": int(time.time()),
            "latency_ms": latency,
            "data": result.get("data"),
        }
        logger.info(f"/api/ask question={req.question[:30]} latency={latency}ms success={payload['success']}")
        return payload
    except Exception as e:
        logger.error(f"/api/ask 异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.server:app",
        host=RUNTIME_CONFIG.HOST,
        port=RUNTIME_CONFIG.PORT,
        workers=RUNTIME_CONFIG.WORKERS,
        reload=RUNTIME_CONFIG.RELOAD,
    )