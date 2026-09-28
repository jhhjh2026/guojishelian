"""
schemas/auth.py - 认证相关 Pydantic 模型
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    user: dict


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., max_length=120)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str | None = None
    role_id: str | None = None


class UserUpdate(BaseModel):
    email: str | None = None
    display_name: str | None = None
    role_id: str | None = None
    is_active: bool | None = None

