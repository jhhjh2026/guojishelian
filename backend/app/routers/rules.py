"""
routers/rules.py - 规则库查询/管理路由
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Rule
from ..db.database import get_db
from ..schemas.rule import RuleResponse
from ..utils.logger import setup_logging
from ..config import get_path_config

logger, _ = setup_logging(log_name="rules", project_root=get_path_config().PROJECT_ROOT)
router = APIRouter(prefix="/api/rules", tags=["rules"])

@router.get("", response_model=RuleResponse)
async def list_rules(
        db: AsyncSession = Depends(get_db),
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        version: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
):
    """分页查询规则（所有人可见）"""
    stmt = select(Rule).where(Rule.is_published.is_(True))
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Rule.title.ilike(like), Rule.content.ilike(like)))
    if category:
        stmt = stmt.where(Rule.category == category)
    if version:
        stmt = stmt.where(Rule.version == version)
    total = (await db.execute(select(Rule).where(Rule.is_published.is_(True)))).scalars().all()
    total = len(total)
    stmt = stmt.order_by(Rule.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()
    return {
        "success": True,
        "code": "OK",
        "message": "success",
        "timestamp": int(datetime.now(tz=timezone.utc).timestamp()),
        "data": {
            "items": [
                {
                    "id": item.id,
                    "rule_id": item.rule_id,
                    "title": item.title,
                    "category": item.category,
                    "subcategory": item.subcategory,
                    "content": item.content,
                    "keywords": item.keywords,
                    "related_rules": item.related_rules,
                    "examples": item.examples,
                    "version": item.version,
                    "source": item.source,
                    "created_at": item.created_at.isoformat(),
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in items
            ],
            "pagination": {"total": total, "page": page, "page_size": page_size},
        },
    }

@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(Rule).where(Rule.rule_id == rule_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {
        "success": True,
        "code": "OK",
        "message": "success",
        "timestamp": int(datetime.now(tz=timezone.utc).timestamp()),
        "data": {
            "id": item.id,
            "rule_id": item.rule_id,
            "title": item.title,
            "category": item.category,
            "subcategory": item.subcategory,
            "content": item.content,
            "keywords": item.keywords,
            "related_rules": item.related_rules,
            "examples": item.examples,
            "version": item.version,
            "source": item.source,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
        },
    }