"""测试基础设施：模块导入、RateLimiter 类定义、常量验证。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
sys.stdout = open(os.devnull, 'w')  # suppress any print during import
from fetch_fundamentals import RateLimiter, SECTIONS, SECTION_DEPENDENCIES
sys.stdout = sys.__stdout__


class TestRateLimiter:
    """RateLimiter: 滑动窗口速率限制器，max_calls=10, window_seconds=60。"""

    def test_rate_limiter_creates(self):
        limiter = RateLimiter(max_calls=10, window_seconds=60)
        assert limiter.max_calls == 10
        assert limiter.window_seconds == 60

    def test_rate_limiter_allows_up_to_max(self):
        import time
        limiter = RateLimiter(max_calls=3, window_seconds=60)
        for _ in range(3):
            limiter.acquire()

    def test_wait_blocks_beyond_max(self):
        import time
        limiter = RateLimiter(max_calls=2, window_seconds=60)
        limiter.acquire()
        limiter.acquire()
        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start
        assert elapsed > 0.3

    def test_rate_limiter_max_calls_10(self):
        limiter = RateLimiter(max_calls=10, window_seconds=60)
        assert limiter.max_calls == 10


class TestConstants:
    """验证 SECTIONS 和 SECTION_DEPENDENCIES 常量。"""

    def test_sections_contains_all_five(self):
        assert set(SECTIONS) == {"basic_info", "fundamentals", "risk_signals", "events", "institutional"}

    def test_section_dependencies_has_all_keys(self):
        assert set(SECTION_DEPENDENCIES.keys()) == set(SECTIONS)
