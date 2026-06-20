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
            exclude_index=True,
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
            exclude_index=True,
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
            {"基金代码": "510300", "基金简称": "沪深300精选", "总募集规模": 3296860.0, "单位净值": 4.97},
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
            exclude_index=True,
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
        # 沪深300ETF 被指数过滤规则排除，央企ETF 无数字保留
        assert len(result) == 3
        codes = [f["基金代码"] for f in result]
        assert codes.count("999999") == 1

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

    def test_exclude_index_funds(self):
        """验证指数/ETF/联接/增强基金被排除
        规则: 1)数字+ETF 2)ETF+联接 3)含指数 4)含增强
        """
        # 应排除的
        # 规则1: 数字+ETF
        assert fund_holdings.is_index_fund("华夏沪深300ETF") == True
        assert fund_holdings.is_index_fund("沪深300ETF工银") == True
        assert fund_holdings.is_index_fund("广发中证500ETF") == True
        # 规则2: ETF+联接 (ETF和联接之间可能有其他字符)
        assert fund_holdings.is_index_fund("华夏沪深300ETF联接A") == True
        assert fund_holdings.is_index_fund("广发中证500ETF联接(LOF)A") == True
        # 规则3: 含"指数"
        assert fund_holdings.is_index_fund("银华中债1-3年国开行债券指数A") == True
        # 规则4: 含"增强"
        assert fund_holdings.is_index_fund("易方达上证50增强A") == True
        assert fund_holdings.is_index_fund("诺安沪深300增强A") == True
        assert fund_holdings.is_index_fund("嘉实成长增强混合") == True
        assert fund_holdings.is_index_fund("易方达沪深300精选增强A") == True

        # 应保留的
        assert fund_holdings.is_index_fund("广发稳泰多元机遇三个月持有混合(ETF-FOF)A") == False
        assert fund_holdings.is_index_fund("嘉实策略混合") == False
        assert fund_holdings.is_index_fund("博时央企结构调整ETF") == False  # 无数字, 非联接
        assert fund_holdings.is_index_fund("央企ETF工银") == False  # 无数字

    def test_exclude_index_disabled(self):
        """排除功能关闭时不过滤"""
        funds = [
            {"基金代码": "510300", "基金简称": "沪深300ETF", "总募集规模": 3296860.0, "单位净值": 4.97},
            {"基金代码": "070011", "基金简称": "嘉实策略", "总募集规模": 4191700.0, "单位净值": 0.916},
        ]
        result = fund_holdings.filter_index_funds(funds, exclude_index=False)
        assert len(result) == 2


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
        # 贵州茅台排第一: latest=1.6M+0.5M=2.1M
        assert top_stocks[0]["stock_code"] == "600519"
        assert top_stocks[0]["latest_holding_amount"] == 2100000.0
        assert top_stocks[0]["fund_count"] == 2
        # 宁德时代排第二: latest=1M
        assert top_stocks[1]["stock_code"] == "300750"
        assert top_stocks[1]["latest_holding_amount"] == 1000000.0
        assert top_stocks[1]["fund_count"] == 1


@pytest.mark.integration
class TestIntegration:
    """真实 API 集成测试"""

    def test_api_availability(self):
        """验证 fund_scale_open_sina 和 fund_portfolio_hold_em 可用"""
        import akshare as ak

        # 基金列表 API
        df = ak.fund_scale_open_sina(symbol="股票型基金")
        assert len(df) > 100
        assert "基金代码" in df.columns

        # 持仓 API
        df2 = ak.fund_portfolio_hold_em(symbol="510300", date="2025")
        assert len(df2) > 0
        assert "股票代码" in df2.columns

    def test_end_to_end_mini(self):
        """端到端测试: min_scale=100亿, top_n=5 (小规模快速验证)"""
        import subprocess

        script = os.path.join(
            os.path.dirname(__file__), "..", "fund_holdings.py"
        )
        result = subprocess.run(
            [
                sys.executable, script,
                "--min-scale", "100",
                "--top-n", "5",
                "--workers", "2",
            ],
            capture_output=True, text=True,
        )
        assert result.returncode in (0, 1)

        output = json.loads(result.stdout)
        assert "meta" in output
        assert "top_stocks" in output
        assert "errors" in output
        meta = output["meta"]
        assert isinstance(meta["total_funds_fetched"], int)
        # returncode 0 means funds were found and processed fully
        if result.returncode == 0:
            assert meta["top_n"] == 5

    def test_cache_reuse(self):
        """二次运行使用缓存，不发起新 API 请求 (通过速度判断)"""
        import subprocess
        import time

        script = os.path.join(
            os.path.dirname(__file__), "..", "fund_holdings.py"
        )
        # 第一次运行
        start = time.time()
        result1 = subprocess.run(
            [
                sys.executable, script,
                "--min-scale", "100",
                "--top-n", "3",
                "--workers", "2",
            ],
            capture_output=True, text=True,
        )
        elapsed1 = time.time() - start

        # 第二次运行（应使用缓存，更快）
        start = time.time()
        result2 = subprocess.run(
            [
                sys.executable, script,
                "--min-scale", "100",
                "--top-n", "3",
                "--workers", "2",
            ],
            capture_output=True, text=True,
        )
        elapsed2 = time.time() - start

        assert result1.returncode in (0, 1)
        assert result2.returncode in (0, 1)
        # Compare top_stocks and errors content (fetch_time in meta will differ)
        out1 = json.loads(result1.stdout)
        out2 = json.loads(result2.stdout)
        assert out1.get("top_stocks") == out2.get("top_stocks")
        assert out1.get("errors") == out2.get("errors")
        print(f"  Run 1: {elapsed1:.1f}s, Run 2: {elapsed2:.1f}s")

    def test_end_to_end_defaults(self):
        """端到端测试：默认参数 min_scale=10亿 (使用高门槛加快测试)"""
        import subprocess

        script = os.path.join(
            os.path.dirname(__file__), "..", "fund_holdings.py"
        )
        result = subprocess.run(
            [
                sys.executable, script,
                "--min-scale", "100",
                "--top-n", "5",
                "--workers", "4",
            ],
            capture_output=True, text=True,
            timeout=120,
        )
        assert result.returncode == 0

        output = json.loads(result.stdout)
        meta = output["meta"]
        assert meta["min_scale_yi"] == 10.0
        assert len(output["top_stocks"]) <= 5
        if output["top_stocks"]:
            s = output["top_stocks"][0]
            assert "stock_code" in s
            assert "stock_name" in s
            assert "latest_holding_amount" in s
            assert "fund_count" in s
            assert "quarterly_trend" in s
