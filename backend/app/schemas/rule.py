"""
schemas/rule.py - 规则相关 Pydantic 模型
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any


class RuleCreate(BaseModel):
    rule_id: str = Field(..., description="规则编号，如 RULE_2026_001")
    title: str = Field(..., max_length=255)
    category: str = Field(..., max_length=64)
    subcategory: Optional[str] = Field(default=None, max_length=64)
    content: str
    keywords: List[str] = Field(default_factory=list)
    related_rules: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    version: str = Field(..., max_length=20)
    source: Optional[str] = None
    is_published: bool = True


class RuleUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    content: Optional[str] = None
    keywords: Optional[List[str]] = None
    related_rules: Optional[List[str]] = None
    examples: Optional[List[str]] = None
    version: Optional[str] = None
    source: Optional[str] = None
    is_published: Optional[bool] = None


class RuleQuery(BaseModel):
    keyword: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = None
    page: int = 1
    page_size: int = 10


class RuleResponse(BaseModel):
    success: bool = True
    code: str = "OK"
    message: str = "success"
    timestamp: int
    data: Optional[Dict[str, Any]] = None
