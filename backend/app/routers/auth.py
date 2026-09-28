"""
routes/auth.py - 认证相关路由
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import SECURITY_CONFIG
from ..db.models import User
from ..db.database import get_db
from ..schemas.auth import LoginRequest, TokenResponse, UserCreate
from ..services.auth_service import (
    authenticate_user,
    build_token_response,
    create_user,
)
from ..utils.logger import setup_logging
from ..config import get_path_config

logger, _ = setup_logging(log_name="auth", project_root=get_path_config().PROJECT_ROOT)

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, body.username, body.password)
    if not user:
        client = getattr(request, "client", None)
        ip = client.host if client is not None and hasattr(client, "host") else "unknown"
        logger.warning("登录失败: username=%s ip=%s", body.username, ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = build_token_response(user)
    logger.info("登录成功: username=%s user_id=%s", user.username, user.id)
    return {
        "success": True,
        "code": "OK",
        "message": "登录成功",
        "timestamp": int(datetime.now(tz=timezone.utc).timestamp()),
        "data": {
            "access_token": token.access_token,
            "token_type": token.token_type,
            "expires_in": token.expires_in,
            "user": token.user,
        },
    }

@router.post("/register")
async def register(body: UserCreate, _request: Request, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="邮箱已存在")
    user = await create_user(db, body)
    token = build_token_response(user)
    logger.info("注册成功: username=%s user_id=%s", user.username, user.id)
    return {
        "success": True,
        "code": "OK",
        "message": "注册成功",
        "timestamp": int(datetime.now(tz=timezone.utc).timestamp()),
        "data": {
            "access_token": token.access_token,
            "token_type": token.token_type,
            "expires_in": token.expires_in,
            "user": token.user,
        },
    }