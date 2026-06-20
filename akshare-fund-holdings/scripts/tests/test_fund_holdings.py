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
