"""
services/stats_service.py - 统计服务
提供规则统计、问答统计等看板数据。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Rule, QAHistory, User
from ..utils.logger import setup_logging
from ..config import get_path_config

logger, _ = setup_logging(log_name="stats", project_root=get_path_config().PROJECT_ROOT)

async def get_dashboard_stats(db: AsyncSession) -> Dict[str, Any]:
    now = datetime.now(tz=timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    total_rules = (await db.execute(select(func.count(Rule.id)))).scalar() or 0
    total_qa = (await db.execute(select(func.count(QAHistory.id)))).scalar() or 0
    today_qa = (await db.execute(select(func.count(QAHistory.id)).where(QAHistory.created_at >= today_start))).scalar() or 0
    week_qa = (await db.execute(select(func.count(QAHistory.id)).where(QAHistory.created_at >= week_start))).scalar() or 0
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

    return {
        "total_rules": total_rules,
        "total_qa": total_qa,
        "today_qa": today_qa,
        "week_qa": week_qa,
        "total_users": total_users,
        "updated_at": now.isoformat(),
    }