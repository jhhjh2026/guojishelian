"""
routes.py - 统一路由聚合

路由前缀约定：
- auth / rules / system 路由在各自 router 自身维护 /api/... 前缀
- admin 路由统一挂载在 /api/admin 前缀下
"""

from __future__ import annotations

from fastapi import APIRouter

from .routers import auth
from .routers import rules
from .routers import admin
from .routers import system

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(rules.router)
api_router.include_router(admin.router, prefix="/api/admin", tags=["admin"])
api_router.include_router(system.router, prefix="/api", tags=["system"])
