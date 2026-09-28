"""
routers - API 路由聚合
"""

from .auth import router as auth_router
from .rules import router as rules_router
from .admin import router as admin_router
from .system import router as system_router

__all__ = ["auth_router", "rules_router", "admin_router", "system_router"]
