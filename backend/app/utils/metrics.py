"""
metrics.py - 轻量内存 Metrics 收集器
用于服务内部统计（QPS、延迟、错误率），之后可对接 Prometheus。
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Tuple


class Metrics:
    """线程安全的轻量指标收集器"""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start = time.time()
        self.requests: int = 0
        self.errors: int = 0
        self.latency_ms_sum: float = 0.0
        self.latency_ms_max: float = 0.0
        self._status_counts: Dict[str, int] = {}

    def record(self, status_code: int, latency_ms: int) -> None:
        with self._lock:
            self.requests += 1
            self.latency_ms_sum += latency_ms
            if latency_ms > self.latency_ms_max:
                self.latency_ms_max = latency_ms
            if status_code >= 400:
                self.errors += 1
            key = str(status_code)
            self._status_counts[key] = self._status_counts.get(key, 0) + 1

    def snapshot(self) -> dict:
        with self._lock:
            uptime = max(0.0, time.time() - self._start)
            qps = self.requests / uptime if uptime > 0 else 0.0
            avg_latency = self.latency_ms_sum / self.requests if self.requests else 0.0
            error_rate = self.errors / self.requests if self.requests else 0.0
            return {
                "uptime_seconds": round(uptime, 2),
                "requests": self.requests,
                "errors": self.errors,
                "error_rate_pct": round(error_rate * 100, 2),
                "qps": round(qps, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "max_latency_ms": round(self.latency_ms_max, 2),
                "status_counts": dict(self._status_counts),
            }
