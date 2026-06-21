#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全局速率限制器 — 滑动窗口算法，每分钟最多 5 次 API 调用
"""
import time
import random


class RateLimiter:
    """滑动窗口限流器：每分钟最多 max_calls_per_minute 次调用"""

    def __init__(self, max_calls_per_minute: int = 5):
        self._max_calls = max_calls_per_minute
        self._timestamps: list[float] = []

    def acquire(self, min_jitter: float = 0.5, max_jitter: float = 2.0) -> None:
        """
        阻塞直到可以发起新调用。
        1. 清理 60 秒之前的记录
        2. 如果窗口内已有 _max_calls 次 → sleep(剩余时间 + 随机 jitter)
        3. 否则直接放行 + 记录当前时间戳
        """
        now = time.monotonic()
        # 清理过期记录
        cutoff = now - 60.0
        self._timestamps = [t for t in self._timestamps if t > cutoff]

        if self._max_calls <= 0:
            time.sleep(random.uniform(min_jitter, max_jitter))
            self._timestamps.append(time.monotonic())
            return

        if len(self._timestamps) >= self._max_calls:
            # 窗口已满，需要等待最老的记录过期
            oldest = min(self._timestamps)
            wait = 60.0 - (now - oldest)
            if wait > 0:
                jitter = random.uniform(min_jitter, max_jitter)
                time.sleep(wait + jitter)

        self._timestamps.append(time.monotonic())


# 全局单例，所有 API 调用共享
_RATE_LIMITER = RateLimiter(max_calls_per_minute=5)
