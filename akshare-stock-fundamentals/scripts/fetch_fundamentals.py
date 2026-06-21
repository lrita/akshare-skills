"""个股基本面数据获取工具。

用法:
    uv run python scripts/fetch_fundamentals.py --symbol 600183 [--date 20260621] [--output result.json]

输出结构化 JSON 到 stdout，包含 5 个板块的个股基本面数据。
"""
import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta

# 板块列表
SECTIONS = ["basic_info", "fundamentals", "risk_signals", "events", "institutional"]

# 每个板块依赖的数据源 (section -> list of source names)
SECTION_DEPENDENCIES = {
    "basic_info":    ["tencent_quote", "eastmoney_search", "stock_add_stock"],
    "fundamentals":  ["financial_abstract_by_report", "financial_abstract_by_year",
                      "financial_benefit", "financial_debt", "financial_cash",
                      "profit_forecast_eps", "profit_forecast_net", "profit_forecast_inst",
                      "profit_forecast_detail", "revenue_structure"],
    "risk_signals":  ["block_trades", "restricted_release_em", "restricted_release_sina", "pledge"],
    "events":        ["notices"],
    "institutional": ["research_visits"],
}


class RateLimiter:
    """滑动窗口速率限制器。"""

    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._call_times: list[float] = []

    def acquire(self):
        """等待直到可以发起下一次调用。"""
        now = time.time()
        self._call_times = [t for t in self._call_times if now - t < self.window_seconds]
        if len(self._call_times) >= self.max_calls:
            wait = self._call_times[0] + self.window_seconds - now + 0.1
            if wait > 0:
                time.sleep(wait)
            self._call_times = [t for t in self._call_times if time.time() - t < self.window_seconds]
        time.sleep(random.uniform(0.3, 1.0))
        self._call_times.append(time.time())
