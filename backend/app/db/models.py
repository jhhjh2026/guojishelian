"""
models.py - SQLAlchemy ORM 模型
包含：用户、角色、规则、问答记录、审计日志等
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(64), nullable=True)
    avatar_url = Column(String(255), nullable=True)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(tz=timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc), nullable=False)

    role = relationship("Role", back_populates="users")
    qa_history = relationship("QAHistory", back_populates="user")

class Role(Base):
    """角色表（RBAC）"""
    __tablename__ = "roles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(64), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    permissions = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(tz=timezone.utc), nullable=False)

    users = relationship("User", back_populates="role")

class Rule(Base):
    """规则表"""
    __tablename__ = "rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    category = Column(String(64), nullable=False, index=True)
    subcategory = Column(String(64), nullable=True)
    content = Column(Text, nullable=False)
    keywords = Column(JSON, default=list, nullable=False)
    related_rules = Column(JSON, default=list, nullable=False)
    examples = Column(JSON, default=list, nullable=False)
    version = Column(String(20), nullable=False, index=True)
    source = Column(String(255), nullable=True)
    is_published = Column(Boolean, default=True, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(tz=timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc), nullable=False)

    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

class QAHistory(Base):
    """问答记录表"""
    __tablename__ = "qa_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    rule_ids = Column(JSON, default=list, nullable=False)
    score = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)
    is_satisfied = Column(Boolean, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(tz=timezone.utc), nullable=False)

    user = relationship("User", back_populates="qa_history")

class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(36), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    request_id = Column(String(64), nullable=True)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(tz=timezone.utc), nullable=False)

    user = relationship("User")