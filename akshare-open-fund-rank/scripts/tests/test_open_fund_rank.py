"""开放基金排行单元测试 (mock akshare API)"""
import os, sys, json, io, re
from datetime import date
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 我们将逐步实现以下模块，测试先写
import open_fund_rank as ofr


# ---- Mock 数据 ----

def make_mock_df():
    """构造模拟 API 返回的 DataFrame，包含混合正常值和 NaN"""
    return pd.DataFrame({
        "序号": [1, 2, 3, 4, 5],
        "基金代码": ["000001", "000002", "000003", "000004", "000005"],
        "基金简称": ["基金A", "基金B", "基金C", "基金D", "基金E"],
        "日期": [date(2026, 6, 18)] * 5,
        "单位净值": [1.2345, 2.0, np.nan, 1.0, 5.6789],
        "累计净值": [3.4567, 1.5, 2.0, np.nan, 8.9],
        "日增长率": [1.5, -0.5, 0.0, np.nan, 2.3],
        "近1周": [5.0, -2.0, np.nan, 1.0, 10.0],
        "近1月": [10.0, 5.0, -3.0, np.nan, 8.0],
        "近3月": [20.0, np.nan, 15.0, 5.0, 30.0],
        "近6月": [30.0, 10.0, np.nan, 20.0, 50.0],
        "近1年": [100.0, 30.0, 50.0, np.nan, 80.0],
        "近2年": [80.0, np.nan, 40.0, 20.0, 60.0],
        "近3年": [np.nan, 20.0, 30.0, 10.0, 50.0],
        "今年来": [15.0, 8.0, np.nan, 3.0, 12.0],
        "成立来": [200.0, 100.0, 150.0, 50.0, np.nan],
        "自定义": [np.nan] * 5,
        "手续费": ["0.15%", "0.10%", "0.00%", "1.50%", "0.08%"],
    })


# ---- 列名映射 ----

class TestColumnMapping:
    """列名映射测试"""

    def test_rename_columns_keeps_only_16(self):
        df = make_mock_df()
        result = ofr.rename_columns(df)
        assert list(result.columns) == [
            "fund_code", "fund_name", "date",
            "unit_net_value", "cumulative_net_value",
            "daily_return", "1w_return", "1m_return",
            "3m_return", "6m_return", "1y_return",
            "2y_return", "3y_return", "ytd_return",
            "since_inception_return", "fee",
        ]

    def test_column_values_preserved(self):
        df = make_mock_df()
        result = ofr.rename_columns(df)
        assert result.iloc[0]["fund_code"] == "000001"
        assert result.iloc[0]["fund_name"] == "基金A"
        assert result.iloc[0]["unit_net_value"] == pytest.approx(1.2345)
        assert result.iloc[0]["daily_return"] == pytest.approx(1.5)
        assert result.iloc[0]["fee"] == "0.15%"


# ---- 过滤表达式解析 ----

class TestParseFilter:
    """parse_filter 函数测试"""

    def test_parse_gt(self):
        col, op, val = ofr.parse_filter("近1月>10")
        assert col == "近1月"
        assert op == ">"
        assert val == pytest.approx(10.0)

    def test_parse_gte(self):
        col, op, val = ofr.parse_filter("近1年>=30.5")
        assert col == "近1年"
        assert op == ">="
        assert val == pytest.approx(30.5)

    def test_parse_lt(self):
        col, op, val = ofr.parse_filter("单位净值<2")
        assert col == "单位净值"
        assert op == "<"
        assert val == pytest.approx(2.0)

    def test_parse_lte(self):
        col, op, val = ofr.parse_filter("累计净值<=5.0")
        assert col == "累计净值"
        assert op == "<="
        assert val == pytest.approx(5.0)

    def test_parse_eq(self):
        col, op, val = ofr.parse_filter("日增长率=0")
        assert col == "日增长率"
        assert op == "="
        assert val == pytest.approx(0.0)

    def test_parse_invalid_format_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.parse_filter("invalid")

    def test_parse_invalid_operator_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.parse_filter("近1月!=10")

    def test_parse_unknown_column_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.parse_filter("未知列>5")


# ---- 过滤应用 ----

class TestApplyFilters:
    """apply_filters 函数测试"""

    def test_single_filter_gt(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        filters = [("近1月", ">", 6.0)]
        result = ofr.apply_filters(df, filters)
        assert len(result) == 2  # 基金A (10.0), 基金E (8.0)
        assert set(result["fund_code"]) == {"000001", "000005"}

    def test_single_filter_lt(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        filters = [("近1月", "<", 0)]
        result = ofr.apply_filters(df, filters)
        assert len(result) == 1  # 基金C (-3.0)
        assert result.iloc[0]["fund_code"] == "000003"

    def test_single_filter_eq(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        filters = [("日增长率", "=", 0.0)]
        result = ofr.apply_filters(df, filters)
        assert len(result) == 1
        assert result.iloc[0]["fund_code"] == "000003"

    def test_multiple_filters_and(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        filters = [("近1月", ">", 5.0), ("近1年", ">", 50.0)]
        result = ofr.apply_filters(df, filters)
        assert len(result) == 1  # 只有基金A
        assert result.iloc[0]["fund_code"] == "000001"

    def test_nan_excluded_by_filter(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        filters = [("近1月", ">", 0)]
        result = ofr.apply_filters(df, filters)
        codes = set(result["fund_code"])
        # 基金D 近1月为 NaN，不应出现在结果中
        assert "000004" not in codes

    def test_filter_clears_nan_before_comparison(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        filters = [("近3年", ">", 0)]
        result = ofr.apply_filters(df, filters)
        codes = set(result["fund_code"])
        # 基金A 近3年为 NaN，不应出现
        assert "000001" not in codes
        # 基金B (20), 基金C (30), 基金D (10), 基金E (50) 应出现
        assert codes == {"000002", "000003", "000004", "000005"}

    def test_no_filters_returns_all(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        result = ofr.apply_filters(df, [])
        assert len(result) == 5


# ---- 排序 ----

class TestSorting:
    """排序逻辑测试"""

    def test_sort_desc(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        result = ofr.sort_dataframe(df, "1y_return", "desc")
        # NaN 排最后，然后降序: 100, 80, 50, 30, NaN
        assert result.iloc[0]["fund_code"] == "000001"  # 100
        assert result.iloc[1]["fund_code"] == "000005"  # 80
        assert result.iloc[2]["fund_code"] == "000003"  # 50
        assert result.iloc[3]["fund_code"] == "000002"  # 30

    def test_sort_asc(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        result = ofr.sort_dataframe(df, "1y_return", "asc")
        # NaN 排最后，升序: 30, 50, 80, 100, NaN
        assert result.iloc[0]["fund_code"] == "000002"  # 30
        assert result.iloc[1]["fund_code"] == "000003"  # 50
        assert result.iloc[2]["fund_code"] == "000005"  # 80
        assert result.iloc[3]["fund_code"] == "000001"  # 100


# ---- Top-N ----

class TestTopN:
    """top_n 截取测试"""

    def test_top_n_less_than_total(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        result = ofr.apply_top_n(df, 3)
        assert len(result) == 3

    def test_top_n_none_returns_all(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        result = ofr.apply_top_n(df, None)
        assert len(result) == 5

    def test_top_n_exceeds_total_returns_all(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        result = ofr.apply_top_n(df, 100)
        assert len(result) == 5


# ---- NaN 转 null ----

class TestNaNToNull:
    """nan_to_none 测试"""

    def test_nan_converted_to_none(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        records = ofr.dataframe_to_records(df)
        # 基金D 近1月为 NaN → None
        row_d = next(r for r in records if r["fund_code"] == "000004")
        assert row_d["1m_return"] is None

    def test_float_values_preserved(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        records = ofr.dataframe_to_records(df)
        row_a = next(r for r in records if r["fund_code"] == "000001")
        assert row_a["1m_return"] == pytest.approx(10.0)
        assert row_a["unit_net_value"] == pytest.approx(1.2345)


# ---- 日期格式化 ----

class TestDateFormat:
    """日期列输出测试"""

    def test_date_converted_to_string(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        records = ofr.dataframe_to_records(df)
        row = records[0]
        assert isinstance(row["date"], str)
        assert row["date"] == "2026-06-18"


# ---- 输出格式 ----

class TestOutputJSONL:
    """jsonl 输出测试"""

    def test_output_jsonl(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        buf = io.StringIO()
        ofr.output_jsonl(df, buf)
        lines = buf.getvalue().strip().split("\n")
        assert len(lines) == 5
        for line in lines:
            obj = json.loads(line)
            assert "fund_code" in obj


class TestOutputJSON:
    """json 输出测试"""

    def test_output_json(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        buf = io.StringIO()
        ofr.output_json(df, buf)
        data = json.loads(buf.getvalue())
        assert isinstance(data, list)
        assert len(data) == 5


# ---- 参数校验 ----

class TestValidateSymbol:
    """symbol 参数校验"""

    def test_valid_symbols(self):
        for s in ["全部", "股票型", "混合型", "债券型", "指数型", "QDII", "FOF"]:
            ofr.validate_symbol(s)  # 不应抛出

    def test_invalid_symbol_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_symbol("期货型")


class TestValidateSortBy:
    """sort-by 参数校验"""

    def test_valid_sort_fields(self):
        valid = ["日增长率", "近1周", "近1月", "近3月", "近6月",
                 "近1年", "近2年", "近3年", "今年来", "成立来",
                 "单位净值", "累计净值"]
        for f in valid:
            ofr.validate_sort_by(f)  # 不应抛出

    def test_invalid_sort_field_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_sort_by("手续费")


class TestValidateOrder:
    """order 参数校验"""

    def test_valid_orders(self):
        ofr.validate_order("desc")
        ofr.validate_order("asc")

    def test_invalid_order_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_order("ASCENDING")


class TestValidateTopN:
    """top-n 参数校验"""

    def test_positive_integer_passes(self):
        assert ofr.validate_top_n("10") == 10

    def test_zero_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_top_n("0")

    def test_negative_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_top_n("-5")

    def test_non_integer_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_top_n("abc")


class TestValidateOutput:
    """output 参数校验"""

    def test_valid_outputs(self):
        ofr.validate_output("jsonl")
        ofr.validate_output("json")

    def test_invalid_output_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_output("csv")
