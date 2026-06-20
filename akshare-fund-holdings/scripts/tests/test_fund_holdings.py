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


import pandas as pd
import argparse


class TestCLIAndMainLogic:
    """CLI 入口和主流程测试"""

    @patch("fund_holdings.fetch_fund_list")
    @patch("fund_holdings.fetch_fund_holdings")
    @patch("fund_holdings.is_cache_valid", return_value=False)
    @patch("fund_holdings.load_cache", return_value=None)
    def test_main_output_json_format(self, mock_load_cache, mock_is_cache_valid,
                                      mock_fetch_holdings, mock_fetch_list):
        """端到端测试：输出正确的 JSON 格式"""
        from io import StringIO

        mock_fetch_list.return_value = [
            {"基金代码": "510300", "基金简称": "沪深300ETF", "总募集规模": 3296860.0, "单位净值": 4.97},
            {"基金代码": "070011", "基金简称": "嘉实策略", "总募集规模": 4191700.0, "单位净值": 0.916},
        ]
        mock_fetch_holdings.return_value = {
            "600519": {
                "stock_name": "贵州茅台",
                "quarters": {"2026Q1": 1600000.0, "2025Q4": 1150000.0},
            },
        }

        args = argparse.Namespace(
            top_n=2,
            min_scale=10.0,
            fund_types="股票型基金,混合型基金",
            workers=2,
        )

        buf = StringIO()
        with patch("sys.stdout", buf):
            exit_code = fund_holdings.main_with_args(args)

        assert exit_code == 0
        output = json.loads(buf.getvalue())
        assert "meta" in output
        assert "top_stocks" in output
        assert "errors" in output
        assert output["meta"]["top_n"] == 2
        assert output["meta"]["total_funds_fetched"] == 2
        assert output["meta"]["success_funds"] == 2
        assert len(output["top_stocks"]) == 1

    @patch("fund_holdings.fetch_fund_list")
    def test_main_no_funds_exit_code_1(self, mock_fetch_list):
        """没有基金通过过滤时返回 exit code 1"""
        from io import StringIO

        mock_fetch_list.return_value = []

        args = argparse.Namespace(
            top_n=100,
            min_scale=1000.0,
            fund_types="股票型基金",
            workers=2,
        )

        buf = StringIO()
        err_buf = StringIO()
        with patch("sys.stdout", buf), patch("sys.stderr", err_buf):
            exit_code = fund_holdings.main_with_args(args)

        assert exit_code == 1

    @patch("fund_holdings.ak")
    @patch("fund_holdings.is_cache_valid", return_value=False)
    @patch("fund_holdings.load_cache", return_value=None)
    def test_full_pipeline_with_mock_apis(self, mock_load_cache, mock_is_cache_valid, mock_ak):
        """完整流程测试：从基金列表到 JSON 输出"""
        from io import StringIO

        df_list = pd.DataFrame([
            {"基金代码": "510300", "基金简称": "沪深300ETF", "总募集规模": 3296860.0, "单位净值": 4.97},
            {"基金代码": "070011", "基金简称": "嘉实策略", "总募集规模": 4191700.0, "单位净值": 0.916},
        ])
        mock_ak.fund_scale_open_sina.side_effect = lambda symbol: df_list.copy() if symbol == "股票型基金" else pd.DataFrame()

        df_holdings = pd.DataFrame([
            {"序号": 1, "股票代码": "600519", "股票名称": "贵州茅台",
             "占净值比例": 4.74, "持仓市值": 1606717.16,
             "季度": "2026年1季度股票投资明细"},
            {"序号": 2, "股票代码": "300750", "股票名称": "宁德时代",
             "占净值比例": 3.23, "持仓市值": 1092918.96,
             "季度": "2026年1季度股票投资明细"},
        ])
        mock_ak.fund_portfolio_hold_em.side_effect = lambda *args, **kwargs: df_holdings.copy()

        args = argparse.Namespace(
            top_n=2,
            min_scale=10.0,
            fund_types="股票型基金",
            workers=2,
        )

        buf = StringIO()
        with patch("sys.stdout", buf):
            exit_code = fund_holdings.main_with_args(args)

        assert exit_code == 0
        output = json.loads(buf.getvalue())
        assert output["meta"]["success_funds"] == 2
        assert len(output["top_stocks"]) == 2
        assert output["top_stocks"][0]["stock_code"] == "600519"


class TestFundListFetch:
    """基金列表拉取、去重和过滤测试"""

    @patch("fund_holdings.ak")
    def test_fetch_fund_list_merges_and_dedup(self, mock_ak):
        """两个基金类型合并后去重"""
        # 模拟股票型基金数据
        df_equity = pd.DataFrame([
            {"基金代码": "510300", "基金简称": "沪深300ETF", "总募集规模": 3296860.0},
            {"基金代码": "512960", "基金简称": "央企ETF", "总募集规模": 2522230.0},
            {"基金代码": "999999", "基金简称": "重复基金", "总募集规模": 100000.0},
        ])
        # 模拟混合型基金数据 (含重复的 999999)
        df_mixed = pd.DataFrame([
            {"基金代码": "070011", "基金简称": "嘉实策略", "总募集规模": 4191700.0},
            {"基金代码": "999999", "基金简称": "重复基金", "总募集规模": 100000.0},
        ])
        mock_ak.fund_scale_open_sina.side_effect = [df_equity, df_mixed]

        result = fund_holdings.fetch_fund_list(["股票型基金", "混合型基金"])
        assert len(result) == 4  # 5 - 1 重复
        codes = [f["基金代码"] for f in result]
        assert codes.count("999999") == 1  # 只出现一次

    @patch("fund_holdings.ak")
    def test_filter_by_min_scale(self, mock_ak):
        """按规模过滤，排除 NaN 和低于门槛的基金"""
        df_equity = pd.DataFrame([
            {"基金代码": "510300", "基金简称": "大基金", "总募集规模": 500000.0},    # 50 亿
            {"基金代码": "000001", "基金简称": "小基金", "总募集规模": 50000.0},     # 5 亿
            {"基金代码": "000002", "基金简称": "空规模基金", "总募集规模": None},    # NaN
        ])
        df_mixed = pd.DataFrame([])
        mock_ak.fund_scale_open_sina.side_effect = [df_equity, df_mixed]

        result = fund_holdings.fetch_fund_list(
            ["股票型基金"], min_scale_yi=10.0
        )
        assert len(result) == 1
        assert result[0]["基金代码"] == "510300"

    @patch("fund_holdings.ak")
    def test_exclude_zero_scale(self, mock_ak):
        """总募集规模为 0 的基金被排除"""
        df = pd.DataFrame([
            {"基金代码": "000001", "基金简称": "零规模", "总募集规模": 0.0},
            {"基金代码": "000002", "基金简称": "正规模", "总募集规模": 100000.0},
        ])
        mock_ak.fund_scale_open_sina.return_value = df

        result = fund_holdings.fetch_fund_list(["股票型基金"], min_scale_yi=5.0)
        codes = [f["基金代码"] for f in result]
        assert "000001" not in codes
        assert "000002" in codes


class TestHoldingsFetch:
    """持仓数据拉取测试"""

    @patch("fund_holdings.ak")
    def test_fetch_single_fund_holdings(self, mock_ak):
        """拉取单只基金持仓，返回按股票聚合的数据"""
        mock_df = pd.DataFrame([
            {"序号": 1, "股票代码": "600519", "股票名称": "贵州茅台",
             "占净值比例": 4.74, "持仓市值": 1606717.16,
             "季度": "2026年1季度股票投资明细"},
            {"序号": 1, "股票代码": "600519", "股票名称": "贵州茅台",
             "占净值比例": 5.89, "持仓市值": 1150782.02,
             "季度": "2025年4季度股票投资明细"},
        ])
        mock_ak.fund_portfolio_hold_em.side_effect = [mock_df, pd.DataFrame()]

        result = fund_holdings.fetch_fund_holdings(
            "510300",
            target_quarters=[("2026Q1", "2026"), ("2025Q4", "2025")],
        )
        assert "600519" in result
        holdings = result["600519"]
        assert len(holdings["quarters"]) >= 1
        assert holdings["stock_name"] == "贵州茅台"

    @patch("fund_holdings.ak")
    def test_fetch_holdings_with_api_failure(self, mock_ak):
        """API 调用失败返回 None"""
        mock_ak.fund_portfolio_hold_em.side_effect = Exception("Network error")

        result = fund_holdings.fetch_fund_holdings(
            "001234",
            target_quarters=[("2026Q1", "2026")],
        )
        assert result is None

    def test_parse_quarter_label(self):
        """解析季度标签"""
        assert fund_holdings.parse_quarter_label("2025年1季度股票投资明细") == "2025Q1"
        assert fund_holdings.parse_quarter_label("2025年4季度股票投资明细") == "2025Q4"
        assert fund_holdings.parse_quarter_label("2024年3季度股票投资明细") == "2024Q3"

    def test_aggregate_holdings_by_stock(self):
        """按股票聚合持仓：跨基金累加持仓市值"""
        holdings_data = {
            "510300": {
                "600519": {
                    "stock_name": "贵州茅台",
                    "quarters": {"2026Q1": 1600000.0},
                },
                "300750": {
                    "stock_name": "宁德时代",
                    "quarters": {"2026Q1": 1000000.0},
                },
            },
            "070011": {
                "600519": {
                    "stock_name": "贵州茅台",
                    "quarters": {"2026Q1": 500000.0},
                },
            },
        }

        top_stocks, trend = fund_holdings.aggregate_holdings(
            holdings_data, top_n=2
        )
        assert len(top_stocks) == 2
        # 贵州茅台应排第一：1600000 + 500000 = 2100000
        assert top_stocks[0]["stock_code"] == "600519"
        assert top_stocks[0]["total_holding_amount"] == 2100000.0
        assert top_stocks[0]["fund_count"] == 2
        # 宁德时代应排第二：1000000
        assert top_stocks[1]["stock_code"] == "300750"
        assert top_stocks[1]["fund_count"] == 1
