"""
routers/admin.py - 管理后台路由（规则管理/用户管理/看板）
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Rule, User
from ..db.database import get_db
from ..schemas.rule import RuleCreate, RuleUpdate
from ..schemas.auth import UserCreate, UserUpdate
from ..services.stats_service import get_dashboard_stats
from ..utils.security import (
    require_permission,
    PERM_RULES_READ,
    PERM_RULES_MANAGE,
    PERM_USERS_MANAGE,
    PERM_STATS_VIEW,
)
from ..utils.logger import setup_logging
from ..config import get_path_config
from ..services.auth_service import hash_password

logger, _ = setup_logging(log_name="admin", project_root=get_path_config().PROJECT_ROOT)
router = APIRouter()

def _now_ts() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())

@router.get("/rules")
async def admin_list_rules(
        db: AsyncSession = Depends(get_db),
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        version: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        _current_user: User = Depends(require_permission([PERM_RULES_READ])),
):
    """规则列表"""
    stmt = select(Rule)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Rule.title.ilike(like), Rule.content.ilike(like)))
    if category:
        stmt = stmt.where(Rule.category == category)
    if version:
        stmt = stmt.where(Rule.version == version)
    result_total = await db.execute(select(func.count()).select_from(Rule))
    total = result_total.scalar() or 0
    stmt = stmt.order_by(Rule.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items_result = await db.execute(stmt)
    items = items_result.scalars().all()
    return {
        "success": True, "code": "OK", "message": "success",
        "timestamp": _now_ts(),
        "data": {
            "items": [{
                "id": item.id, "rule_id": item.rule_id, "title": item.title,
                "category": item.category, "subcategory": item.subcategory,
                "content": item.content, "keywords": item.keywords,
                "related_rules": item.related_rules, "examples": item.examples,
                "version": item.version, "source": item.source,
                "is_published": item.is_published,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            } for item in items],
            "pagination": {"total": total, "page": page, "page_size": page_size},
        },
    }

@router.get("/dashboard")
async def admin_dashboard(
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_permission([PERM_STATS_VIEW])),
):
    stats = await get_dashboard_stats(db)
    return {
        "success": True, "code": "OK", "message": "success",
        "timestamp": _now_ts(), "data": stats,
    }

@router.post("/rules")
async def admin_create_rule(
        body: RuleCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_permission([PERM_RULES_MANAGE])),
):
    exists = (await db.execute(select(Rule).where(Rule.rule_id == body.rule_id))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="规则编号已存在")
    rule = Rule(**body.model_dump(), created_by=current_user.id, updated_by=current_user.id)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    logger.info("规则创建: rule_id=%s operator=%s", rule.rule_id, current_user.username)
    return {
        "success": True, "code": "OK", "message": "创建成功",
        "timestamp": _now_ts(), "data": {"id": rule.id},
    }

@router.put("/rules/{rule_id}")
async def admin_update_rule(
        rule_id: str,
        body: RuleUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_permission([PERM_RULES_MANAGE])),
):
    rule = (await db.execute(select(Rule).where(Rule.rule_id == rule_id))).scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="规则不存在")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    rule.updated_by = current_user.id
    await db.commit()
    await db.refresh(rule)
    logger.info("规则更新: rule_id=%s operator=%s", rule.rule_id, current_user.username)
    return {
        "success": True, "code": "OK", "message": "更新成功",
        "timestamp": _now_ts(), "data": {"id": rule.id},
    }

@router.delete("/rules/{rule_id}")
async def admin_delete_rule(
        rule_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_permission([PERM_RULES_MANAGE])),
):
    rule = (await db.execute(select(Rule).where(Rule.rule_id == rule_id))).scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="规则不存在")
    rule.is_published = False
    rule.updated_by = current_user.id
    await db.commit()
    logger.info("规则删除: rule_id=%s operator=%s", rule.rule_id, current_user.username)
    return {
        "success": True, "code": "OK", "message": "删除成功",
        "timestamp": _now_ts(), "data": None,
    }

@router.get("/users")
async def admin_list_users(
        db: AsyncSession = Depends(get_db),
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        _current_user: User = Depends(require_permission([PERM_USERS_MANAGE])),
):
    stmt = select(User)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(User.username.ilike(like), User.email.ilike(like)))
    result_total = await db.execute(select(func.count()).select_from(User))
    total = result_total.scalar() or 0
    stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items_result = await db.execute(stmt)
    items = items_result.scalars().all()
    return {
        "success": True, "code": "OK", "message": "success",
        "timestamp": _now_ts(),
        "data": {
            "items": [{
                "id": item.id, "username": item.username, "email": item.email,
                "display_name": item.display_name, "role_id": item.role_id,
                "is_active": item.is_active,
                "created_at": item.created_at.isoformat(),
            } for item in items],
            "pagination": {"total": total, "page": page, "page_size": page_size},
        },
    }

@router.put("/users/{user_id}")
async def admin_update_user(
        user_id: str,
        body: UserUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_permission([PERM_USERS_MANAGE])),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.email is not None:
        user.email = body.email
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.role_id is not None:
        user.role_id = body.role_id
    if body.is_active is not None:
        user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    logger.info("用户更新: user_id=%s operator=%s", user.id, current_user.username)
    return {
        "success": True, "code": "OK", "message": "更新成功",
        "timestamp": _now_ts(), "data": {"id": user.id},
    }

@router.post("/users")
async def admin_create_user(
        body: UserCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_permission([PERM_USERS_MANAGE])),
):
    exists = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=body.username, email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name or body.username,
        role_id=body.role_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("用户创建: username=%s operator=%s", user.username, current_user.username)
    return {
        "success": True, "code": "OK", "message": "创建成功",
        "timestamp": _now_ts(), "data": {"id": user.id},
    }