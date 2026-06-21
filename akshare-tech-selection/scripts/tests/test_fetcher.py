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


class TestStockCodeCompatibility:
    """验证不同 API 的代码列能正确标准化"""

    def make_df(self, code_col, codes):
        return pd.DataFrame({
            code_col: codes,
            "名称": ["股票A", "股票B", "股票C"],
        })

    def test_ths_rank_code_column(self):
        """同花顺 rank 指标用 股票代码 列，6位格式"""
        df = self.make_df("股票代码", ["000001", "600519", "300750"])
        result = fetcher.standardize_output(
            df, "股票代码", "名称",
            "fetch_test", "测试", ["测试"],
        )
        assert result["data"][0]["stock_code"] == "000001"
        assert result["data"][1]["stock_code"] == "600519"

    def test_zt_pool_code_column(self):
        """涨停板用 代码 列，6位格式"""
        df = self.make_df("代码", ["000811", "600519", "300750"])
        result = fetcher.standardize_output(
            df, "代码", "名称",
            "fetch_test", "测试", ["测试"],
        )
        assert result["data"][1]["stock_code"] == "600519"

    def test_changes_em_code_column(self):
        """个股异动用 代码 列，6位格式"""
        df = self.make_df("代码", ["920161", "603177", "001296"])
        result = fetcher.standardize_output(
            df, "代码", "名称",
            "fetch_test", "测试", ["测试"],
        )
        assert result["data"][0]["stock_code"] == "920161"

    def test_forecast_cninfo_code_column(self):
        """机构评级用 证券代码 列，6位格式"""
        df = self.make_df("证券代码", ["000552", "600519", "688981"])
        result = fetcher.standardize_output(
            df, "证券代码", "证券简称",
            "fetch_test", "测试", ["测试"],
        )
        assert result["data"][2]["stock_code"] == "688981"

    def test_board_change_code_column(self):
        """板块异动用长列名，6位格式"""
        df = self.make_df("板块异动最频繁个股及所属类型-股票代码", ["301669", "001218", "688333"])
        result = fetcher.standardize_output(
            df, "板块异动最频繁个股及所属类型-股票代码",
            "板块异动最频繁个股及所属类型-股票名称",
            "fetch_test", "测试", ["测试"],
        )
        assert result["data"][0]["stock_code"] == "301669"

class TestAntiCrawlCheck:
    """测试 _check_thx_blocked 反爬检测"""

    def test_http_403_triggers_exit(self, monkeypatch):
        """HTTP 403 应触发 os._exit(1)"""
        import fetcher as ft

        class MockResponse:
            status_code = 403
            text = ""

        monkeypatch.setattr("os._exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
        with pytest.raises(SystemExit) as excinfo:
            ft._check_thx_blocked(MockResponse(), "test_api")
        assert excinfo.value.code == 1

    def test_captcha_page_triggers_exit(self, monkeypatch):
        """验证页面应触发 os._exit(1)"""
        import fetcher as ft

        class MockResponse:
            status_code = 200
            text = "请在下方输入验证码"

        monkeypatch.setattr("os._exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
        with pytest.raises(SystemExit) as excinfo:
            ft._check_thx_blocked(MockResponse(), "test_api")
        assert excinfo.value.code == 1

    def test_short_response_triggers_exit(self, monkeypatch):
        """短响应（<200字符）应被视为异常页面"""
        import fetcher as ft

        class MockResponse:
            status_code = 200
            text = "short"

        monkeypatch.setattr("os._exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
        with pytest.raises(SystemExit) as excinfo:
            ft._check_thx_blocked(MockResponse(), "test_api")
        assert excinfo.value.code == 1

    def test_normal_response_passes_through(self):
        """正常 HTML 页面不应触发 exit"""
        import fetcher as ft

        class MockResponse:
            status_code = 200
            text = "<html><body>" + "x" * 200 + "</body></html>"

        # 不应该抛出异常
        ft._check_thx_blocked(MockResponse(), "test_api")
