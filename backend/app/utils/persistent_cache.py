"""
persistent_cache.py - 可持久化的 LRU 缓存
支持将缓存写入本地 JSON 文件，实现进程重启后的缓存恢复，减少重复 API 调用。
兼容原有 LRUCache 接口（get / put / stats / clear）。
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

logger = logging.getLogger("persistent_cache")


class PersistentLRUCache:
    """带本地持久化的 LRU 缓存"""

    def __init__(self, capacity: int = 128, ttl_seconds: int = 3600, cache_file: str = None):
        self.capacity = max(1, int(capacity))
        self.ttl = max(0, int(ttl_seconds))
        self.cache_file = cache_file
        self.cache: OrderedDict = OrderedDict()
        self.hits = 0
        self.misses = 0
        self._load()

    def _make_key(self, query: str) -> str:
        normalized = query.strip().lower()
        return str(hash(normalized))

    def _now(self) -> float:
        return time.time()

    def _load(self) -> None:
        """从本地文件加载缓存（若存在）"""
        if not self.cache_file:
            return
        try:
            if not os.path.exists(self.cache_file):
                return
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            loaded = 0
            for key, value in data.items():
                try:
                    ts = float(value.get("ts", 0))
                except (TypeError, ValueError):
                    continue
                if self.ttl > 0 and (self._now() - ts) > self.ttl:
                    continue
                self.cache[key] = (value.get("value"), ts)
                loaded += 1
            logger.info("持久化缓存已加载: %s", self.cache_file)
        except Exception as e:
            logger.warning("加载持久化缓存失败: %s", e)

    def _save(self) -> None:
        """将当前缓存写入本地文件（尽力而为，不阻断主流程）"""
        if not self.cache_file:
            return
        try:
            # 清理过期项后再写入，控制文件体积
            self._expire()
            payload = {}
            for key, (value, ts) in self.cache.items():
                payload[key] = {"value": value, "ts": ts}
            os.makedirs(os.path.dirname(self.cache_file) or ".", exist_ok=True)
            tmp = f"{self.cache_file}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, default=str)
            os.replace(tmp, self.cache_file)
        except Exception as e:
            logger.warning("写入持久化缓存失败: %s", e)

    def _expire(self) -> None:
        """清理过期项"""
        if self.ttl <= 0:
            return
        now = self._now()
        expired = [k for k, (_, ts) in self.cache.items() if now - ts > self.ttl]
        for k in expired:
            del self.cache[k]

    def get(self, query: str) -> Any | None:
        key = self._make_key(query)
        if key in self.cache:
            value, ts = self.cache[key]
            if self.ttl > 0 and (self._now() - ts) > self.ttl:
                del self.cache[key]
                self.misses += 1
                return None
            self.cache.move_to_end(key)
            self.hits += 1
            return value
        self.misses += 1
        return None

    def put(self, query: str, value) -> None:
        key = self._make_key(query)
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = (value, self._now())
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
        self._save()

    def stats(self) -> dict:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "capacity": self.capacity,
            "size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": round(hit_rate, 2),
            "ttl_seconds": self.ttl,
            "persistent_file": self.cache_file or "",
        }

    def clear(self) -> None:
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        if self.cache_file and os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
            except Exception as e:
                logger.warning("删除持久化缓存文件失败: %s", e)


__all__ = [
    "PersistentLRUCache",
]
