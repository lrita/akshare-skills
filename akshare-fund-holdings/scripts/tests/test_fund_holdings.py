"""基金持仓分析测试"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from datetime import date
from unittest.mock import patch, MagicMock
import json
import fund_holdings


class TestQuarterInference:
    """可获取季度推断测试"""

    def test_quarters_for_june_2026(self):
        """2026年6月 → 应推断 [2026Q1, 2025Q4, 2025Q3, 2025Q2]"""
        quarters = fund_holdings.infer_target_quarters(
            today=date(2026, 6, 20)
        )
        assert quarters == [
            ("2026Q1", "2026"),
            ("2025Q4", "2025"),
            ("2025Q3", "2025"),
            ("2025Q2", "2025"),
        ]

    def test_quarters_for_jan_2026(self):
        """2026年1月 → Q4尚未披露，应推断 [2025Q3, 2025Q2, 2025Q1, 2024Q4]"""
        quarters = fund_holdings.infer_target_quarters(
            today=date(2026, 1, 20)
        )
        assert quarters == [
            ("2025Q3", "2025"),
            ("2025Q2", "2025"),
            ("2025Q1", "2025"),
            ("2024Q4", "2024"),
        ]

    def test_quarters_for_aug_2025(self):
        """2025年8月 → Q2刚披露，应推断 [2025Q2, 2025Q1, 2024Q4, 2024Q3]"""
        quarters = fund_holdings.infer_target_quarters(
            today=date(2025, 8, 10)
        )
        assert quarters == [
            ("2025Q2", "2025"),
            ("2025Q1", "2025"),
            ("2024Q4", "2024"),
            ("2024Q3", "2024"),
        ]

    def test_quarters_for_apr_2026(self):
        """2026年4月25日 → Q1刚披露，应推断 [2026Q1, 2025Q4, 2025Q3, 2025Q2]"""
        quarters = fund_holdings.infer_target_quarters(
            today=date(2026, 4, 25)
        )
        assert quarters == [
            ("2026Q1", "2026"),
            ("2025Q4", "2025"),
            ("2025Q3", "2025"),
            ("2025Q2", "2025"),
        ]

    def test_quarters_format(self):
        """验证返回格式: [(quarter_label, year), ...]"""
        quarters = fund_holdings.infer_target_quarters(
            today=date(2025, 12, 15)
        )
        assert len(quarters) == 4
        for q, y in quarters:
            assert q.startswith("202")  # 以年份开头
            assert q[4] == "Q"  # 第5个字符是 Q
            assert y in ("2024", "2025")


class TestCacheManagement:
    """缓存读写和过期测试"""

    def test_fund_list_cache_write_and_read(self, tmp_path):
        """写入基金列表缓存后能正确读取"""
        data = {
            "fetch_time": "2026-06-20 10:00:00",
            "funds": [{"基金代码": "510300", "总募集规模": 3296860.0}],
        }
        cache_path = tmp_path / "fund_list.json"
        fund_holdings.save_cache(cache_path, data)
        assert cache_path.exists()

        loaded = fund_holdings.load_cache(cache_path)
        assert loaded is not None
        assert loaded["funds"][0]["基金代码"] == "510300"

    def test_fund_list_cache_expired_7days(self, tmp_path):
        """缓存超过 7 天视为过期"""
        data = {"fetch_time": "2026-06-10 10:00:00", "funds": []}  # 10 天前
        cache_path = tmp_path / "fund_list.json"
        fund_holdings.save_cache(cache_path, data)

        # 模拟今天为 2026-06-20
        today = date(2026, 6, 20)
        assert not fund_holdings.is_cache_valid(cache_path, ttl_hours=168, today=today)

    def test_fund_list_cache_valid_within_7days(self, tmp_path):
        """缓存 3 天前仍有效"""
        data = {"fetch_time": "2026-06-17 10:00:00", "funds": []}
        cache_path = tmp_path / "fund_list.json"
        fund_holdings.save_cache(cache_path, data)

        today = date(2026, 6, 20)
        assert fund_holdings.is_cache_valid(cache_path, ttl_hours=168, today=today)

    def test_load_cache_missing_file(self, tmp_path):
        """缓存文件不存在返回 None"""
        cache_path = tmp_path / "nonexistent.json"
        assert fund_holdings.load_cache(cache_path) is None

    def test_load_cache_corrupted(self, tmp_path):
        """缓存文件损坏，删除并返回 None"""
        cache_path = tmp_path / "corrupt.json"
        cache_path.write_text("not valid json{{{")
        result = fund_holdings.load_cache(cache_path)
        assert result is None
        assert not cache_path.exists()  # 损坏文件应被删除

    def test_holdings_cache_not_expired_when_stale(self, tmp_path):
        """持仓缓存的智能过期：缓存有最新季度则不过期"""
        from datetime import datetime
        cache_path = tmp_path / "510300.json"
        data = {
            "fetch_time": "2026-04-30 10:00:00",
            "quarters": ["2026Q1", "2025Q4", "2025Q3", "2025Q2"],
            "holdings": [],
        }
        fund_holdings.save_cache(cache_path, data)
        today = date(2026, 6, 20)
        latest_available_quarter = "2026Q1"
        assert fund_holdings.is_holdings_cache_valid(
            cache_path, today, latest_available_quarter
        )

    def test_holdings_cache_expired_when_new_quarter_available(self, tmp_path):
        """持仓缓存缺少最新季度则过期"""
        cache_path = tmp_path / "510300.json"
        data = {
            "fetch_time": "2026-03-15 10:00:00",
            "quarters": ["2025Q3", "2025Q2", "2025Q1", "2024Q4"],
            "holdings": [],
        }
        fund_holdings.save_cache(cache_path, data)
        today = date(2026, 6, 20)
        latest_available_quarter = "2026Q1"
        assert not fund_holdings.is_holdings_cache_valid(
            cache_path, today, latest_available_quarter
        )

    def test_failures_cache_read_write(self, tmp_path):
        """失败记录写入并读取"""
        cache_path = tmp_path / "failures.json"
        failures = {"001234": {"fund_code": "001234", "error": "timeout"}}
        fund_holdings.save_cache(cache_path, failures)
        loaded = fund_holdings.load_cache(cache_path)
        assert loaded["001234"]["error"] == "timeout"
