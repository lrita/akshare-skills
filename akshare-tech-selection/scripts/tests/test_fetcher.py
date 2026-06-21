"""fetcher 单元测试 (mock akshare API)"""
import os, sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fetcher


class TestNormalizeStockCode:
    def test_six_digit_code_unchanged(self):
        assert fetcher.normalize_stock_code("000001") == "000001"

    def test_sz_prefixed_code_stripped(self):
        assert fetcher.normalize_stock_code("SZ000001") == "000001"

    def test_sh_prefixed_code_stripped(self):
        assert fetcher.normalize_stock_code("SH600519") == "600519"

    def test_bj_prefixed_code_stripped(self):
        assert fetcher.normalize_stock_code("BJ830799") == "830799"

    def test_already_six_digit_string(self):
        assert fetcher.normalize_stock_code("300750") == "300750"

    def test_none_returns_none(self):
        assert fetcher.normalize_stock_code(None) is None

    def test_empty_string_returns_empty(self):
        assert fetcher.normalize_stock_code("") == ""

    def test_four_digit_converts_to_six(self):
        assert fetcher.normalize_stock_code("0001") == "000001"


class TestStandardizeOutput:
    def test_basic_dataframe(self):
        df = pd.DataFrame({
            "股票代码": ["000001", "600519"],
            "股票简称": ["平安银行", "贵州茅台"],
            "涨跌幅": [1.5, np.nan],
        })
        result = fetcher.standardize_output(
            df, code_col="股票代码", name_col="股票简称",
            indicator="fetch_test", category="测试指标",
            categories=["测试类"],
        )
        assert result["indicator"] == "fetch_test"
        assert result["category"] == "测试指标"
        assert result["categories"] == ["测试类"]
        assert result["count"] == 2
        assert len(result["data"]) == 2
        assert result["data"][0]["stock_code"] == "000001"
        assert result["data"][0]["stock_name"] == "平安银行"
        assert result["data"][0]["涨跌幅"] == 1.5
        assert result["data"][1]["涨跌幅"] is None  # NaN → null

    def test_empty_dataframe_returns_none(self):
        df = pd.DataFrame()
        result = fetcher.standardize_output(
            df, code_col="股票代码", name_col="股票简称",
            indicator="fetch_test", category="测试",
            categories=["测试类"],
        )
        assert result is None

    def test_none_dataframe_returns_none(self):
        result = fetcher.standardize_output(
            None, code_col="股票代码", name_col="股票简称",
            indicator="fetch_test", category="测试",
            categories=["测试类"],
        )
        assert result is None


class TestIndicatorRegistry:
    def test_registry_contains_all_20_indicators(self):
        assert len(fetcher.ALL_INDICATORS) == 20

    def test_each_indicator_has_required_keys(self):
        for ind in fetcher.ALL_INDICATORS:
            assert "name" in ind
            assert "api" in ind
            assert "category" in ind
            assert "code_col" in ind
            assert "name_col" in ind

    def test_no_duplicate_indicator_names(self):
        names = [ind["name"] for ind in fetcher.ALL_INDICATORS]
        assert len(names) == len(set(names))
