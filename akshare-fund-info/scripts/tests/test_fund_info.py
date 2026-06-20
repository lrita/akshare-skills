"""公募基金综合信息单元测试 (mock 全部 akshare API)"""
import os, sys, json, io
from datetime import date, datetime
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fund_info as fi


# ---- Mock 数据工厂 ----

def make_mock_overview_df():
    return pd.DataFrame([{
        "基金全称": "测试基金混合型证券投资基金",
        "基金简称": "测试基金混合A",
        "基金代码": "000001（前端）",
        "基金类型": "混合型",
        "发行日期": "2020-01-01",
        "成立日期/规模": "2020-03-15 / 5.00亿份",
        "净资产规模": "10.00亿元（截止至：2026年03月31日）",
        "份额规模": "8.00亿份（截止至：2026年03月31日）",
        "基金管理人": "测试基金公司",
        "基金托管人": "测试银行",
        "基金经理人": "张三",
        "成立来分红": "每份累计0.50元（3次）",
        "管理费率": "1.50%（每年）",
        "托管费率": "0.25%（每年）",
        "销售服务费率": "0.00%（每年）",
        "最高认购费率": "1.50%（前端）",
        "业绩比较基准": "沪深300指数*80%+中债综合指数*20%",
        "跟踪标的": "该基金无跟踪标的",
    }])


def make_mock_nav_df():
    return pd.DataFrame({
        "净值日期": [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 4)],
        "单位净值": [1.5000, 1.5100, 1.5050],
        "日增长率": [0.0, 0.67, -0.33],
    })


def make_mock_risk_df():
    return pd.DataFrame({
        "周期": ["近1年", "近3年", "近5年"],
        "较同类风险收益比": [73, 76, 53],
        "较同类抗风险波动": [39, 55, 52],
        "年化波动率": [26.71, 22.08, 20.71],
        "年化夏普比率": [2.79, 0.70, 0.01],
        "最大回撤": [15.89, 29.90, 52.93],
    })


def make_mock_profit_df():
    return pd.DataFrame({
        "持有时长": ["满6个月", "满1年", "满2年", "满3年"],
        "盈利概率": [55.0, 60.0, 63.0, 71.0],
        "平均收益": [6.15, 13.81, 29.13, 43.54],
    })


def make_mock_asset_alloc_df():
    return pd.DataFrame({
        "资产类型": ["股票", "现金", "其他"],
        "仓位占比": [51.95, 19.51, 29.09],
    })


def make_mock_fee_status_df():
    return pd.DataFrame({
        0: ["申购状态", "普通回活期宝", "极速回活期宝"],
        1: ["开放申购", "支持", "支持"],
        2: ["赎回状态", "定投状态", "超级转换"],
        3: ["开放赎回", "支持", "支持"],
    })


def make_mock_fee_op_cost_df():
    return pd.DataFrame({
        0: ["管理费率", "托管费率", "销售服务费率"],
        1: ["1.50%（每年）", "0.25%（每年）", "0.00%（每年）"],
    })


def make_mock_fee_redemption_df():
    return pd.DataFrame({
        "适用期限": ["小于7天", "大于等于7天，小于30天", "大于等于730天"],
        "赎回费率": ["1.50%", "0.75%", "0.00%"],
    })


def make_mock_trade_rules_df():
    return pd.DataFrame({
        "费用类型": ["买入规则", "买入规则", "卖出规则", "卖出规则", "其他费用", "其他费用"],
        "条件或名称": [
            "0.0万<买入金额<100.0万", "100.0万<=买入金额<500.0万",
            "0.0天<持有期限<7.0天", "7.0天<=持有期限",
            "基金管理费", "基金托管费",
        ],
        "费用": ["1.5", "1.2", "1.5", "0.5", "1.2", "0.2"],
    })


def make_mock_stock_holding_df():
    return pd.DataFrame({
        "序号": [1, 2, 3],
        "股票代码": ["002025", "600862", "600941"],
        "股票名称": ["航天电器", "中航高科", "中国移动"],
        "占净值比例": [3.46, 3.24, 2.86],
        "持股数": [209.92, 380.43, 62.11],
        "持仓市值": [7947.67, 7441.16, 6568.75],
        "季度": ["2024年1季度股票投资明细"] * 3,
    })


def make_mock_bond_holding_df():
    return pd.DataFrame({
        "序号": [1, 2],
        "债券代码": ["230304", "101564021"],
        "债券名称": ["23进出04", "15华能集MTN002"],
        "占净值比例": [4.59, 4.29],
        "持仓市值": [11114.27, 10379.44],
        "季度": ["2023年4季度债券投资明细"] * 2,
    })


def make_mock_industry_df():
    return pd.DataFrame({
        "序号": [1, 2],
        "行业类别": ["制造业", "信息技术"],
        "占净值比例": [56.58, 5.72],
        "市值": [136966.39, 13849.95],
        "截止时间": ["2023-12-31", "2023-12-31"],
    })


# ---- 代码校验 ----

class TestValidateCode:
    def test_valid_6_digit(self):
        fi.validate_code("000001")
        fi.validate_code("015641")

    def test_too_short_raises_valueerror(self):
        with pytest.raises(ValueError):
            fi.validate_code("12345")

    def test_too_long_raises_valueerror(self):
        with pytest.raises(ValueError):
            fi.validate_code("1234567")

    def test_non_digit_raises_valueerror(self):
        with pytest.raises(ValueError):
            fi.validate_code("abc123")


# ---- 年份推断 ----

class TestDeterminePortfolioYear:
    def test_after_q1_disclosure_cutoff(self):
        assert fi.determine_portfolio_year(date(2026, 6, 20)) == 2025

    def test_before_q1_disclosure_cutoff(self):
        assert fi.determine_portfolio_year(date(2026, 3, 1)) == 2024

    def test_on_cutoff_day(self):
        assert fi.determine_portfolio_year(date(2026, 4, 22)) == 2025

    def test_january(self):
        assert fi.determine_portfolio_year(date(2026, 1, 15)) == 2024


class TestDetermineHoldDate:
    def test_mid_year_returns_last_year_q4(self):
        assert fi.determine_hold_date(date(2026, 6, 20)) == "20251231"

    def test_early_year_returns_two_years_ago_q4(self):
        assert fi.determine_hold_date(date(2026, 1, 15)) == "20241231"

    def test_december(self):
        assert fi.determine_hold_date(date(2026, 12, 1)) == "20251231"


# ---- API 响应处理器 ----

class TestParseOverview:
    def test_parses_all_fields(self):
        df = make_mock_overview_df()
        result = fi.parse_overview(df)
        assert result["fund_full_name"] == "测试基金混合型证券投资基金"
        assert result["fund_name"] == "测试基金混合A"
        assert result["fund_type"] == "混合型"
        assert result["fund_manager"] == "测试基金公司"
        assert "management_fee_rate" in result
        assert "benchmark" in result

    def test_empty_df_returns_none(self):
        assert fi.parse_overview(pd.DataFrame()) is None


class TestParseNavHistory:
    def test_converts_all_records(self):
        df = make_mock_nav_df()
        result = fi.parse_nav_history(df)
        assert len(result) == 3
        assert result[0]["date"] == "2025-01-02"
        assert result[0]["unit_net_value"] == pytest.approx(1.5)
        assert result[0]["daily_return"] == pytest.approx(0.0)

    def test_empty_df_returns_none(self):
        assert fi.parse_nav_history(pd.DataFrame()) is None


class TestParseRiskAnalysis:
    def test_converts_all_records(self):
        df = make_mock_risk_df()
        result = fi.parse_risk_analysis(df)
        assert len(result) == 3
        assert result[0]["period"] == "近1年"
        assert result[0]["risk_return_rank"] == 73
        assert result[0]["annualized_volatility"] == pytest.approx(26.71)

    def test_empty_df_returns_none(self):
        assert fi.parse_risk_analysis(pd.DataFrame()) is None


class TestParseProfitProbability:
    def test_converts_all_records(self):
        df = make_mock_profit_df()
        result = fi.parse_profit_probability(df)
        assert len(result) == 4
        assert result[0]["holding_period"] == "满6个月"
        assert result[0]["profit_probability"] == pytest.approx(55.0)

    def test_empty_df_returns_none(self):
        assert fi.parse_profit_probability(pd.DataFrame()) is None


class TestParseAssetAllocation:
    def test_converts_all_records(self):
        df = make_mock_asset_alloc_df()
        result = fi.parse_asset_allocation(df)
        assert len(result) == 3
        assert result[0]["asset_type"] == "股票"
        assert result[0]["allocation_ratio"] == pytest.approx(51.95)

    def test_empty_df_returns_none(self):
        assert fi.parse_asset_allocation(pd.DataFrame()) is None


class TestParseFeeAndRules:
    def test_parses_all_fields(self):
        result = fi.parse_fee_and_rules(
            make_mock_fee_status_df(),
            make_mock_fee_op_cost_df(),
            make_mock_fee_redemption_df(),
            make_mock_trade_rules_df(),
        )
        assert result["purchase_status"] == "开放申购"
        assert result["redemption_status"] == "开放赎回"
        assert result["auto_invest_status"] == "支持"
        assert result["management_fee_rate"] == "1.50%（每年）"
        assert result["custodian_fee_rate"] == "0.25%（每年）"
        assert len(result["redemption_fee_table"]) == 3
        assert len(result["purchase_rules"]) == 2
        assert len(result["redemption_rules"]) == 2
        assert len(result["other_fees"]) == 2

    def test_empty_dfs_returns_none(self):
        empty = pd.DataFrame()
        result = fi.parse_fee_and_rules(empty, empty, empty, empty)
        assert result is None


class TestParseStockHoldings:
    def test_converts_all_records(self):
        df = make_mock_stock_holding_df()
        result = fi.parse_stock_holdings(df)
        assert len(result) == 3
        assert result[0]["stock_code"] == "002025"
        assert result[0]["net_value_ratio"] == pytest.approx(3.46)

    def test_empty_df_returns_none(self):
        assert fi.parse_stock_holdings(pd.DataFrame()) is None


class TestParseBondHoldings:
    def test_converts_all_records(self):
        df = make_mock_bond_holding_df()
        result = fi.parse_bond_holdings(df)
        assert len(result) == 2
        assert result[0]["bond_code"] == "230304"

    def test_empty_df_returns_none(self):
        assert fi.parse_bond_holdings(pd.DataFrame()) is None


class TestParseIndustryAllocation:
    def test_converts_all_records(self):
        df = make_mock_industry_df()
        result = fi.parse_industry_allocation(df)
        assert len(result) == 2
        assert result[0]["industry_name"] == "制造业"
        assert result[0]["net_value_ratio"] == pytest.approx(56.58)

    def test_empty_df_returns_none(self):
        assert fi.parse_industry_allocation(pd.DataFrame()) is None


# ---- NaN 处理 ----

class TestNaNHandling:
    def test_nan_in_dataframe_becomes_none_in_output(self):
        df = pd.DataFrame({
            "净值日期": [date(2025, 1, 2)],
            "单位净值": [np.nan],
            "日增长率": [0.0],
        })
        result = fi.parse_nav_history(df)
        assert result[0]["unit_net_value"] is None


# ---- 聚合 ----

class TestAggregateResult:
    def test_all_sections_present(self):
        aggregated = fi.aggregate_result(
            code="000001",
            overview={"fund_name": "test"},
            nav=[{"date": "2025-01-01"}],
            risk=[{"period": "近1年"}],
            profit=[{"holding_period": "满1年"}],
            asset_alloc=[{"asset_type": "股票"}],
            fee={"purchase_status": "开放申购"},
            stock_holdings=[{"stock_code": "000001"}],
            bond_holdings=[{"bond_code": "000001"}],
            industry=[{"industry_name": "制造业"}],
            errors=[],
        )
        assert "meta" in aggregated
        assert aggregated["meta"]["fund_code"] == "000001"
        assert aggregated["overview"] is not None
        assert aggregated["nav_history"] is not None
        assert aggregated["risk_analysis"] is not None
        assert aggregated["profit_probability"] is not None
        assert aggregated["asset_allocation"] is not None
        assert aggregated["fee_and_rules"] is not None
        assert aggregated["stock_holdings"] is not None
        assert aggregated["bond_holdings"] is not None
        assert aggregated["industry_allocation"] is not None
        assert aggregated["errors"] == []

    def test_failed_section_is_null_with_error(self):
        aggregated = fi.aggregate_result(
            code="000001",
            overview={"fund_name": "test"},
            nav=None,
            risk=[{"period": "近1年"}],
            profit=[{"holding_period": "满1年"}],
            asset_alloc=[{"asset_type": "股票"}],
            fee={"purchase_status": "开放申购"},
            stock_holdings=[{"stock_code": "000001"}],
            bond_holdings=None,
            industry=[{"industry_name": "制造业"}],
            errors=[
                {"section": "nav_history", "error": "timeout", "api": "fund_open_fund_info_em"},
                {"section": "bond_holdings", "error": "no data", "api": "fund_portfolio_bond_hold_em"},
            ],
        )
        assert aggregated["nav_history"] is None
        assert aggregated["bond_holdings"] is None
        assert len(aggregated["errors"]) == 2
        assert aggregated["errors"][0]["section"] == "nav_history"
