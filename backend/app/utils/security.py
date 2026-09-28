"""
security.py - 安全工具函数
JWT 编解码、权限校验、密码哈希封装
"""

from __future__ import annotations

from jose import JWTError, jwt
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import SECURITY_CONFIG
from ..db.models import User, Role
from ..db.database import get_db

SECRET_KEY = SECURITY_CONFIG.API_TOKEN or "dev-secret-key-change-in-production"
ALGORITHM = "HS256"
bearer_scheme = HTTPBearer(auto_error=False)

# ===== 细粒度权限常量 =====
PERM_RULES_READ = "rules:read"
PERM_RULES_MANAGE = "rules:manage"
PERM_RULES_IMPORT = "rules:import"
PERM_USERS_MANAGE = "users:manage"
PERM_ROLES_MANAGE = "roles:manage"
PERM_INDEX_MANAGE = "index:manage"
PERM_STATS_VIEW = "stats:view"
PERM_ADMIN = "admin"

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
        ) from exc

async def get_current_user(
        request: Request,
        db: AsyncSession,
        credentials: HTTPAuthorizationCredentials | None = None,
) -> User:
    if credentials is None:
        credentials = await bearer_scheme(request)
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="缺失 Bearer Token")
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token 缺少用户标识")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user

def require_permission(permissions: list[str]):
    """返回一个 FastAPI 依赖函数，要求当前用户具备至少一个指定权限。
    admin 权限为超级位：若用户角色包含 'admin'，则自动通过所有权限检查。
    """
    async def _dependency(request: Request, db: AsyncSession = Depends(get_db)):
        user = await get_current_user(request, db)
        role_result = await db.execute(select(Role).where(Role.id == user.role_id))
        role = role_result.scalar_one_or_none()
        if not role:
            raise HTTPException(status_code=403, detail="角色不存在")
        role_perms = role.permissions or []
        if PERM_ADMIN in role_perms:
            return user
        if not set(permissions).intersection(set(role_perms)):
            raise HTTPException(status_code=403, detail="权限不足")
        return user
    return _dependency