"""测试 fundamentals 板块的数据源函数。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
import pytest
import pandas as pd
import math

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import (
    fetch_financial_abstract,
    fetch_financial_profit,
    fetch_financial_debt,
    fetch_financial_cashflow,
    fetch_profit_forecast_eps,
    fetch_profit_forecast_net,
    fetch_profit_forecast_inst,
    fetch_profit_forecast_detail,
    fetch_revenue_structure,
)
sys.stdout = sys.__stdout__

SYMBOL = "600183"
DATE = "20260621"


class TestFetchFinancialAbstract:
    # THS API 实际返回的列名
    @patch('fetch_fundamentals.ak.stock_financial_abstract_new_ths')
    def test_by_report_returns_list_of_dicts(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "report_date": ["2025-12-31", "2024-12-31"],
            "metric_name": ["净利润", "营业收入"],
            "value": [52.3, 45.1],
        })
        result = fetch_financial_abstract(SYMBOL, "按报告期")
        assert isinstance(result, list)
        assert len(result) == 2

    @patch('fetch_fundamentals.ak.stock_financial_abstract_new_ths')
    def test_trims_to_five_years(self, mock_api):
        years = [f"{y}-12-31" for y in range(2026, 2015, -1)]
        mock_api.return_value = pd.DataFrame({
            "report_date": years,
            "metric_name": ["X"] * len(years),
            "value": [1.0] * len(years),
        })
        result = fetch_financial_abstract(SYMBOL, "按报告期", DATE)
        assert len(result) <= 6  # ~5 years

    @patch('fetch_fundamentals.ak.stock_financial_abstract_new_ths')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_financial_abstract(SYMBOL, "按报告期")
        assert result == []


class TestFetchFinancialProfit:
    @patch('fetch_fundamentals.ak.stock_financial_benefit_new_ths')
    def test_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "report_date": ["2025-12-31"],
            "metric_name": ["营业总收入"],
            "value": [100.0],
        })
        result = fetch_financial_profit(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) > 0
        # 验证列名被映射
        assert "报告期" in result[0]

    @patch('fetch_fundamentals.ak.stock_financial_benefit_new_ths')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_financial_profit(SYMBOL, DATE)
        assert result == []


class TestFetchFinancialDebt:
    @patch('fetch_fundamentals.ak.stock_financial_debt_new_ths')
    def test_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "report_date": ["2025-12-31"],
            "metric_name": ["资产总计"],
            "value": [500.0],
        })
        result = fetch_financial_debt(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) > 0

    @patch('fetch_fundamentals.ak.stock_financial_debt_new_ths')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_financial_debt(SYMBOL, DATE)
        assert result == []


class TestFetchFinancialCashflow:
    @patch('fetch_fundamentals.ak.stock_financial_cash_new_ths')
    def test_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "report_date": ["2025-12-31"],
            "metric_name": ["经营现金流"],
            "value": [20.0],
        })
        result = fetch_financial_cashflow(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) > 0

    @patch('fetch_fundamentals.ak.stock_financial_cash_new_ths')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_financial_cashflow(SYMBOL, DATE)
        assert result == []


class TestFetchProfitForecasts:
    @patch('fetch_fundamentals.ak.stock_profit_forecast_ths')
    def test_eps_forecast_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({"预测年度": [2026], "机构名称": ["中信"], "每股收益": [2.15]})
        result = fetch_profit_forecast_eps(SYMBOL)
        assert isinstance(result, list)
        assert len(result) > 0

    @patch('fetch_fundamentals.ak.stock_profit_forecast_ths')
    def test_net_profit_forecast_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({"预测年度": [2026], "机构名称": ["中信"], "净利润": [52.3]})
        result = fetch_profit_forecast_net(SYMBOL)
        assert isinstance(result, list)
        assert len(result) > 0

    @patch('fetch_fundamentals.ak.stock_profit_forecast_ths')
    def test_institution_detail_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({"机构名称": ["中信"], "评级": ["买入"]})
        result = fetch_profit_forecast_inst(SYMBOL)
        assert isinstance(result, list)

    @patch('fetch_fundamentals.ak.stock_profit_forecast_ths')
    def test_indicator_detail_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({"预测年度": [2026], "每股收益": [2.15]})
        result = fetch_profit_forecast_detail(SYMBOL)
        assert isinstance(result, list)

    @patch('fetch_fundamentals.ak.stock_profit_forecast_ths')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_profit_forecast_eps(SYMBOL)
        assert result == []


class TestFetchRevenueStructure:
    @patch('fetch_fundamentals.ak.stock_zygc_em')
    def test_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "报告日期": ["2025-12-31", "2024-12-31"],
            "主营收入": [284.4, 250.0],
        })
        result = fetch_revenue_structure(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) == 2

    @patch('fetch_fundamentals.ak.stock_zygc_em')
    def test_trims_to_three_years(self, mock_api):
        years = [f"{y}-12-31" for y in range(2025, 2014, -1)]
        mock_api.return_value = pd.DataFrame({
            "报告日期": years,
            "主营收入": [1.0] * len(years),
        })
        result = fetch_revenue_structure(SYMBOL, DATE)
        assert len(result) <= 4

    @patch('fetch_fundamentals.ak.stock_zygc_em')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_revenue_structure(SYMBOL, DATE)
        assert result == []

    @patch('fetch_fundamentals.ak.stock_zygc_em')
    def test_nan_is_replaced_with_none(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "报告日期": ["2025-12-31"],
            "主营收入": [float('nan')],
        })
        result = fetch_revenue_structure(SYMBOL, DATE)
        assert result[0]["主营收入"] is None
