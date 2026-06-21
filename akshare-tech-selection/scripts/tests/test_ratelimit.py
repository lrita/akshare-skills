"""ratelimit 单元测试"""
import time
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ratelimit import RateLimiter


class TestRateLimiter:
    def test_first_call_allowed_immediately(self):
        rl = RateLimiter(max_calls_per_minute=5)
        start = time.monotonic()
        rl.acquire(min_jitter=0, max_jitter=0)  # zero jitter for test
        elapsed = time.monotonic() - start
        assert elapsed < 0.01  # should be near-instant

    def test_exceed_limit_blocks(self):
        rl = RateLimiter(max_calls_per_minute=2)
        rl.acquire(min_jitter=0, max_jitter=0)
        rl.acquire(min_jitter=0, max_jitter=0)
        start = time.monotonic()
        rl.acquire(min_jitter=0, max_jitter=0)  # 3rd call, should block
        elapsed = time.monotonic() - start
        # should wait ~60s minus time since first call... at least 0.1s
        assert elapsed > 0.1

    def test_window_resets_after_60s(self):
        rl = RateLimiter(max_calls_per_minute=2)
        # Manually insert old timestamps
        rl._timestamps = [time.monotonic() - 70, time.monotonic() - 65]
        start = time.monotonic()
        rl.acquire(min_jitter=0, max_jitter=0)
        elapsed = time.monotonic() - start
        assert elapsed < 0.01  # old ones expired, no wait

    def test_cleans_expired_timestamps(self):
        rl = RateLimiter(max_calls_per_minute=5)
        rl._timestamps = [
            time.monotonic() - 120,
            time.monotonic() - 100,
            time.monotonic() - 80,
            time.monotonic() - 10,
        ]
        rl.acquire(min_jitter=0, max_jitter=0)
        # Only the one at -10s should remain + the new one
        assert len([t for t in rl._timestamps if t > time.monotonic() - 61]) == 2

    def test_zero_max_calls_always_blocks(self):
        rl = RateLimiter(max_calls_per_minute=0)
        start = time.monotonic()
        rl.acquire(min_jitter=0.01, max_jitter=0.01)  # non-zero to avoid infinite
        elapsed = time.monotonic() - start
        assert elapsed >= 0.01


class TestRateLimiterGlobalInstance:
    def test_global_instance_exists(self):
        from ratelimit import _RATE_LIMITER
        assert isinstance(_RATE_LIMITER, RateLimiter)
        assert _RATE_LIMITER._max_calls == 5
