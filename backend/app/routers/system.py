"""
routers/system.py - 系统健康与指标路由
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from ..config import RUNTIME_CONFIG, MODEL_CONFIG
from ..db.database import engine
from ..utils.logger import setup_logging
from ..config import get_path_config

logger, _ = setup_logging(log_name="system", project_root=get_path_config().PROJECT_ROOT)
router = APIRouter()

@router.get("/health")
async def health():
    return {
        "success": True,
        "code": "OK",
        "message": "服务正常",
        "timestamp": int(datetime.now(tz=timezone.utc).timestamp()),
        "data": {
            "app": RUNTIME_CONFIG.APP_TITLE,
            "version": RUNTIME_CONFIG.APP_VERSION,
            "python": sys.version,
            "platform": platform.platform(),
            "llm_model": MODEL_CONFIG.LLM_MODEL,
            "embedding_provider": getattr(MODEL_CONFIG, "EMBEDDING_PROVIDER", "dashscope"),
            "embedding_model": MODEL_CONFIG.EMBEDDING_MODEL,
        },
    }

@router.get("/ready")
async def ready():
    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        logger.warning("数据库就绪检查失败: %s", exc)
    ready = db_ok
    return {
        "success": ready,
        "code": "READY" if ready else "NOT_READY",
        "message": "服务就绪" if ready else "依赖未就绪",
        "timestamp": int(datetime.now(tz=timezone.utc).timestamp()),
        "data": {"database": db_ok},
    }

@router.get("/version")
async def version():
    return {
        "success": True,
        "code": "OK",
        "message": "版本信息",
        "timestamp": int(datetime.now(tz=timezone.utc).timestamp()),
        "data": {
            "name": "issf-rag-assistant",
            "version": RUNTIME_CONFIG.APP_VERSION,
        },
    }