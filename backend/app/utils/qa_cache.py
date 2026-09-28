"""
qa_cache.py - 问答缓存抽象层
支持 Redis（生产多 worker）与进程内 LRU（单机开发）两种后端，
未配置 REDIS_URL 时静默降级为 LRU。
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import os
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger("qa_cache")

class LRUCacheBackend:
    """进程内 LRU 缓存（单 worker 开发/测试用）"""

    def __init__(self, capacity: int = 128, ttl_seconds: int = 3600):
        self.capacity = capacity
        self.ttl = ttl_seconds
        self._cache: OrderedDict = OrderedDict()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _make_key(query: str) -> str:
        return hashlib.md5(query.strip().lower().encode("utf-8")).hexdigest()

    def get(self, query: str) -> Optional[dict]:
        key = self._make_key(query)
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp <= self.ttl:
                self._cache.move_to_end(key)
                self.hits += 1
                return value
            del self._cache[key]
        self.misses += 1
        return None

    def put(self, query: str, value: dict) -> None:
        key = self._make_key(query)
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, time.time())
        if len(self._cache) > self.capacity:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()
        self.hits = 0
        self.misses = 0

    def stats(self) -> dict:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "backend": "lru",
            "capacity": self.capacity,
            "size": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": round(hit_rate, 2),
            "ttl_seconds": self.ttl,
        }

class RedisCacheBackend:
    """Redis 缓存后端（多 worker 共享）"""

    def __init__(self, redis_url: str, ttl_seconds: int = 3600, prefix: str = "issf:qa:"):
        self.ttl = ttl_seconds
        self.prefix = prefix
        self._redis = None
        self._redis_url = redis_url
        self.hits = 0
        self.misses = 0
        self._connected = False

    def _ensure_connected(self):
        if self._redis is not None:
            return
        try:
            import redis as redis_lib
            self._redis = redis_lib.from_url(self._redis_url, decode_responses=True)
            self._redis.ping()
            self._connected = True
            logger.info("Redis 缓存连接成功: %s", self._redis_url)
        except Exception as e:
            logger.warning("Redis 连接失败 (%s)，降级为 LRU 内存缓存", e)
            self._connected = False

    @staticmethod
    def _make_key(query: str) -> str:
        return hashlib.md5(query.strip().lower().encode("utf-8")).hexdigest()

    def get(self, query: str) -> Optional[dict]:
        if not self._connected:
            self.misses += 1
            return None
        try:
            key = self.prefix + self._make_key(query)
            raw = self._redis.get(key)
            if raw is not None:
                self._redis.expire(key, self.ttl)
                self.hits += 1
                return json.loads(raw)
            self.misses += 1
            return None
        except Exception as e:
            logger.warning("Redis GET 失败: %s", e)
            self.misses += 1
            return None

    def put(self, query: str, value: dict) -> None:
        if not self._connected:
            return
        try:
            key = self.prefix + self._make_key(query)
            self._redis.setex(key, self.ttl, json.dumps(value, ensure_ascii=False))
        except Exception as e:
            logger.warning("Redis SET 失败: %s", e)

    def clear(self) -> None:
        if not self._connected:
            return
        try:
            pattern = self.prefix + "*"
            keys = self._redis.keys(pattern)
            if keys:
                self._redis.delete(*keys)
            self.hits = 0
            self.misses = 0
            logger.info("Redis 缓存已清空，共 %d 个键", len(keys))
        except Exception as e:
            logger.warning("Redis CLEAR 失败: %s", e)

    def stats(self) -> dict:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "backend": "redis",
            "connected": self._connected,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": round(hit_rate, 2),
            "ttl_seconds": self.ttl,
        }

def get_qa_cache(
        capacity: int = 128, ttl_seconds: int = 3600
) -> LRUCacheBackend | RedisCacheBackend:
    """
    获取缓存实例：
    - 若设置了 REDIS_URL 环境变量，返回 RedisCacheBackend
    - 否则返回 LRUCacheBackend（静默降级）
    """
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        backend = RedisCacheBackend(redis_url=redis_url, ttl_seconds=ttl_seconds)
        backend._ensure_connected()
        if backend._connected:
            return backend
        logger.info("Redis 不可用，降级为 LRU 内存缓存")

    return LRUCacheBackend(capacity=capacity, ttl_seconds=ttl_seconds)