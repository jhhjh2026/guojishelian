"""
services/auth_service.py - 认证服务
职责：注册、登录、Token 生成与校验、密码哈希
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import SECURITY_CONFIG, RUNTIME_CONFIG
from ..db.models import User, Role
from ..schemas.auth import UserCreate, TokenResponse

SECRET_KEY = SECURITY_CONFIG.API_TOKEN or "dev-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24h

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(tz=timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

async def get_default_role_id(db: AsyncSession) -> str:
    result = await db.execute(select(Role).where(Role.name == "user"))
    role = result.scalar_one_or_none()
    if role:
        return role.id
    role = Role(id=str(uuid.uuid4()), name="user", description="普通用户", permissions=["ask"])
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role.id

async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    role_id = user_in.role_id
    if not role_id:
        role_id = await get_default_role_id(db)
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        display_name=user_in.display_name or user_in.username,
        role_id=role_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def build_token_response(user: User) -> TokenResponse:
    token = create_access_token({"sub": str(user.id), "username": user.username, "role_id": user.role_id})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "role_id": user.role_id,
            "is_active": user.is_active,
        },
    )