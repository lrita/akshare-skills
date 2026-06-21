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
