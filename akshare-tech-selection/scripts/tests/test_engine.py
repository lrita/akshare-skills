"""engine 单元测试 (mock fetcher)"""
import os, sys, json
from datetime import date, datetime
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import engine


# ---- Mock fetcher 工厂 ----

def make_mock_fetcher(name, category, data_rows=None):
    """创建一个模拟的 fetcher 函数"""
    def mock_fetcher(symbol=None, date=None):
        if data_rows is None:
            return None
        records = []
        for i, row in enumerate(data_rows):
            record = {
                "stock_code": row.get("code", f"00000{i}"),
                "stock_name": row.get("name", f"测试{i}"),
                "extra_field": row.get("extra", 0),
            }
            # 加法原始列
            for k, v in row.items():
                if k not in ("code", "name", "extra"):
                    record[k] = v
            records.append(record)
        return {
            "indicator": name,
            "category": category,
            "categories": [category],
            "count": len(records),
            "data": records,
        }
    return mock_fetcher


class TestRunSingle:
    def test_returns_expected_structure(self, monkeypatch):
        mock = make_mock_fetcher("fetch_test", "测试", [
            {"code": "000001", "name": "平安银行", "close": 10.5},
            {"code": "600519", "name": "贵州茅台", "close": 1800.0},
        ])
        result = engine.run_single("fetch_test", _fetcher_callable=mock, symbol=None, date=None)
        assert result["mode"] == "single"
        assert result["indicator"] == "fetch_test"
        assert result["count"] == 2
        assert len(result["data"]) == 2
        assert "fetch_time" in result
        assert result["errors"] == []

    def test_fetcher_returns_none_produces_null_data(self, monkeypatch):
        mock = make_mock_fetcher("fetch_empty", "空", None)
        result = engine.run_single("fetch_empty", _fetcher_callable=mock)
        assert result["mode"] == "single"
        assert result["count"] == 0
        assert result["data"] == []
        assert len(result["errors"]) == 1
        assert "null" in result["errors"][0]["error"].lower() or "empty" in result["errors"][0]["error"].lower()

    def test_data_items_contain_stock_code_and_stock_name(self, monkeypatch):
        mock = make_mock_fetcher("fetch_test", "测试", [
            {"code": "000001", "name": "平安银行"},
        ])
        result = engine.run_single("fetch_test", _fetcher_callable=mock)
        item = result["data"][0]
        assert item["stock_code"] == "000001"
        assert item["stock_name"] == "平安银行"


class TestRunIntersect:
    def test_two_indicators_with_overlap(self, monkeypatch):
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 3,
                "data": [
                    {"stock_code": "000001", "stock_name": "平安银行", "val": 1},
                    {"stock_code": "600519", "stock_name": "贵州茅台", "val": 2},
                    {"stock_code": "300750", "stock_name": "宁德时代", "val": 3},
                ],
            }
        def mock_b(symbol=None, date=None):
            return {
                "indicator": "fetch_b", "category": "B类", "categories": ["B"],
                "count": 2,
                "data": [
                    {"stock_code": "600519", "stock_name": "贵州茅台", "val": 5},
                    {"stock_code": "000001", "stock_name": "平安银行", "val": 6},
                ],
            }
        import fetcher
        monkeypatch.setattr(fetcher, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(fetcher, "fetch_b", mock_b, raising=False)
        result = engine.run_intersect(["fetch_a", "fetch_b"], max_workers=1)
        assert result["intersect_count"] == 2
        codes = [d["stock_code"] for d in result["data"]]
        assert "000001" in codes
        assert "600519" in codes
        assert result["succeeded_indicators"] == 2

    def test_no_overlap_returns_empty(self, monkeypatch):
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 1,
                "data": [{"stock_code": "000001", "stock_name": "平安"}],
            }
        def mock_b(symbol=None, date=None):
            return {
                "indicator": "fetch_b", "category": "B类", "categories": ["B"],
                "count": 1,
                "data": [{"stock_code": "600519", "stock_name": "茅台"}],
            }
        import fetcher
        monkeypatch.setattr(fetcher, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(fetcher, "fetch_b", mock_b, raising=False)
        result = engine.run_intersect(["fetch_a", "fetch_b"], max_workers=1)
        assert result["intersect_count"] == 0
        assert result["data"] == []

    def test_one_fetcher_returns_none(self, monkeypatch):
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 1,
                "data": [{"stock_code": "000001", "stock_name": "平安"}],
            }
        def mock_b(symbol=None, date=None):
            return None
        import fetcher
        monkeypatch.setattr(fetcher, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(fetcher, "fetch_b", mock_b, raising=False)
        result = engine.run_intersect(["fetch_a", "fetch_b"], max_workers=1)
        assert result["intersect_count"] == 0
        assert result["indicator_counts"]["fetch_b"] == 0
        assert len(result["errors"]) >= 1

    def test_each_result_has_matched_indicators_and_details(self, monkeypatch):
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 1,
                "data": [{"stock_code": "000001", "stock_name": "平安", "score": 90}],
            }
        import fetcher
        monkeypatch.setattr(fetcher, "fetch_a", mock_a, raising=False)
        result = engine.run_intersect(["fetch_a"], max_workers=1)
        assert result["intersect_count"] == 1
        item = result["data"][0]
        assert "fetch_a" in item["matched_indicators"]
        assert "fetch_a" in item["indicator_details"]
        assert item["indicator_details"]["fetch_a"]["score"] == 90


class TestRunScan:
    def test_aggregates_signals_by_stock(self, monkeypatch):
        """同一只股票在多个指标命中，应聚合为一个条目"""
        import fetcher as ft

        test_indicators = [
            {"name": "fetch_a", "api": "mock", "category": "A类", "categories": ["A"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False},
            {"name": "fetch_b", "api": "mock", "category": "B类", "categories": ["B"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False},
        ]
        monkeypatch.setattr(ft, "ALL_INDICATORS", test_indicators)

        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 2,
                "data": [
                    {"stock_code": "000001", "stock_name": "平安银行", "val": 1},
                    {"stock_code": "600519", "stock_name": "贵州茅台", "val": 2},
                ],
            }
        def mock_b(symbol=None, date=None):
            return {
                "indicator": "fetch_b", "category": "B类", "categories": ["B"],
                "count": 2,
                "data": [
                    {"stock_code": "000001", "stock_name": "平安银行", "val": 5},
                    {"stock_code": "300750", "stock_name": "宁德时代", "val": 6},
                ],
            }
        monkeypatch.setattr(ft, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(ft, "fetch_b", mock_b, raising=False)

        result = engine.run_scan(max_workers=1)

        # 000001 在 2 个指标中都出现
        pingan = [d for d in result["data"] if d["stock_code"] == "000001"][0]
        assert pingan["signal_count"] == 2
        assert len(pingan["signals"]) == 2
        signal_inds = [s["indicator"] for s in pingan["signals"]]
        assert "fetch_a" in signal_inds
        assert "fetch_b" in signal_inds

    def test_signal_threshold_filters(self, monkeypatch):
        import fetcher as ft
        test_indicators = [
            {"name": "fetch_a", "api": "mock", "category": "A类", "categories": ["A"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False},
            {"name": "fetch_b", "api": "mock", "category": "B类", "categories": ["B"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False},
        ]
        monkeypatch.setattr(ft, "ALL_INDICATORS", test_indicators)

        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 1,
                "data": [{"stock_code": "000001", "stock_name": "平安银行", "val": 1}],
            }
        def mock_b(symbol=None, date=None):
            return {
                "indicator": "fetch_b", "category": "B类", "categories": ["B"],
                "count": 1,
                "data": [{"stock_code": "600519", "stock_name": "贵州茅台", "val": 2}],
            }
        monkeypatch.setattr(ft, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(ft, "fetch_b", mock_b, raising=False)

        # threshold=2: 只有同时在 2 个指标的股票才出现（即无股票满足）
        result = engine.run_scan(max_workers=1, signal_threshold=2)
        assert len(result["data"]) == 0

    def test_top_n_limits_results(self, monkeypatch):
        import fetcher as ft
        test_indicators = [
            {"name": "fetch_a", "api": "mock", "category": "A类", "categories": ["A"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False},
        ]
        monkeypatch.setattr(ft, "ALL_INDICATORS", test_indicators)

        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 5,
                "data": [
                    {"stock_code": f"00000{i}", "stock_name": f"股票{i}", "val": i}
                    for i in range(1, 6)
                ],
            }
        monkeypatch.setattr(ft, "fetch_a", mock_a, raising=False)

        result = engine.run_scan(max_workers=1, top_n=3)
        assert len(result["data"]) == 3

    def test_signal_summary_contains_top_signals(self, monkeypatch):
        import fetcher as ft
        test_indicators = [
            {"name": "fetch_a", "api": "mock", "category": "A类", "categories": ["A"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False},
            {"name": "fetch_b", "api": "mock", "category": "B类", "categories": ["B"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False},
        ]
        monkeypatch.setattr(ft, "ALL_INDICATORS", test_indicators)

        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 10,
                "data": [{"stock_code": f"0000{i:02d}", "stock_name": f"s{i}"} for i in range(10)],
            }
        def mock_b(symbol=None, date=None):
            return {
                "indicator": "fetch_b", "category": "B类", "categories": ["B"],
                "count": 3,
                "data": [{"stock_code": f"1000{i:02d}", "stock_name": f"t{i}"} for i in range(3)],
            }
        monkeypatch.setattr(ft, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(ft, "fetch_b", mock_b, raising=False)

        result = engine.run_scan(max_workers=1)
        summary = result["signal_summary"]
        assert summary["total_stocks_with_signals"] == 13  # 10 + 3, no overlap
        assert len(summary["top_signals"]) == 2


class TestRunFull:
    def test_has_detailed_signal_summary(self, monkeypatch):
        import fetcher as ft
        test_indicators = [
            {"name": "fetch_a", "api": "mock", "category": "A类", "categories": ["A"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False},
            {"name": "fetch_b", "api": "mock", "category": "B类", "categories": ["B"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False},
        ]
        monkeypatch.setattr(ft, "ALL_INDICATORS", test_indicators)

        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 5,
                "data": [{"stock_code": f"0000{i:02d}", "stock_name": f"s{i}"} for i in range(5)],
            }
        def mock_b(symbol=None, date=None):
            return None  # this one fails
        monkeypatch.setattr(ft, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(ft, "fetch_b", mock_b, raising=False)

        result = engine.run_full(max_workers=1)

        assert result["mode"] == "full"
        assert result["total_indicators"] == 2
        assert result["succeeded_indicators"] == 1

        # signal_summary 详细版有 indicators 数组
        summary = result["signal_summary"]
        assert "indicators" in summary
        assert "total_stocks_with_signals" in summary
        assert len(summary["indicators"]) == 2

        # fetch_a 应该是 success
        a_info = [i for i in summary["indicators"] if i["indicator"] == "fetch_a"][0]
        assert a_info["status"] == "success"
        assert a_info["total_rows"] == 5

        # fetch_b 应该有 error status
        b_info = [i for i in summary["indicators"] if i["indicator"] == "fetch_b"][0]
        assert b_info["status"] == "error"
        assert b_info["total_rows"] == 0

    def test_data_structure_same_as_scan(self, monkeypatch):
        import fetcher as ft
        test_indicators = [
            {"name": "fetch_a", "api": "mock", "category": "A类", "categories": ["A"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False},
        ]
        monkeypatch.setattr(ft, "ALL_INDICATORS", test_indicators)

        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 1,
                "data": [{"stock_code": "000001", "stock_name": "平安", "val": 1}],
            }
        monkeypatch.setattr(ft, "fetch_a", mock_a, raising=False)

        result = engine.run_full()
        assert "data" in result
        assert len(result["data"]) == 1
        assert result["data"][0]["stock_code"] == "000001"
        assert result["data"][0]["signal_count"] == 1
        assert "signals" in result["data"][0]
