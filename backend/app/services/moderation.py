"""
services/moderation.py - 内容安全服务
提供敏感词过滤与合规检查。
"""

from __future__ import annotations

import re
from typing import List, Optional


class ModerationService:
    """基于规则的内容安全服务"""

    def __init__(self, sensitive_words: Optional[List[str]] = None):
        self.sensitive_words = set(word.strip() for word in sensitive_words or [] if word.strip())
        self._pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in self.sensitive_words) + r")\b") if self.sensitive_words else None

    def contains_sensitive(self, text: str) -> bool:
        if not text or not self._pattern:
            return False
        return bool(self._pattern.search(text))

    def filter(self, text: str, replacement: str = "***") -> str:
        if not text or not self._pattern:
            return text
        return self._pattern.sub(replacement, text)


default_moderation = ModerationService()
