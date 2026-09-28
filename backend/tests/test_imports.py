"""
tests/test_imports.py - 模块导入冒烟测试
提升关键模块覆盖率，确保数据库、认证、路由、合规模块均可被导入。
"""

from __future__ import annotations

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_import_db_modules():
    import app.db.models  # noqa: F401
    import app.db.database  # noqa: F401


def test_import_auth_and_services():
    import app.services.auth_service  # noqa: F401
    import app.services.audit_service  # noqa: F401
    import app.services.moderation  # noqa: F401


def test_import_routers_and_routes():
    import app.routers.auth  # noqa: F401
    import app.routers.rules  # noqa: F401
    import app.routers.admin  # noqa: F401
    import app.routers.system  # noqa: F401
    import app.routes  # noqa: F401
