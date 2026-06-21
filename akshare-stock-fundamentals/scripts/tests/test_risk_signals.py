"""测试 risk_signals 板块的4个数据源函数。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch
import pytest
import pandas as pd

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import (
    fetch_block_trades,
    fetch_restricted_release_em,
    fetch_restricted_release_sina,
    fetch_pledge,
)
sys.stdout = sys.__stdout__

SYMBOL = "600183"
DATE = "20260621"


class TestFetchBlockTrades:
    @patch('fetch_fundamentals.ak.stock_dzjy_mrmx')
    def test_filters_by_stock_code(self, mock_api):
        mock_api.return_value = pd.DataFrame([
            {"股票代码": "600183", "股票名称": "生益科技", "成交日期": "2026-06-18", "成交价": 182.00},
            {"股票代码": "000001", "股票名称": "平安银行", "成交日期": "2026-06-18", "成交价": 11.50},
        ])
        result = fetch_block_trades(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["股票名称"] == "生益科技"

    @patch('fetch_fundamentals.ak.stock_dzjy_mrmx')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_block_trades(SYMBOL, DATE)
        assert result == []


class TestFetchRestrictedRelease:
    @patch('fetch_fundamentals.ak.stock_restricted_release_queue_em')
    def test_em_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "解禁日期": ["2026-07-01"],
            "解禁数量": [1000000],
        })
        result = fetch_restricted_release_em(SYMBOL, DATE)
        assert isinstance(result, list)

    @patch('fetch_fundamentals.ak.stock_restricted_release_queue_em')
    def test_em_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_restricted_release_em(SYMBOL, DATE)
        assert result == []

    @patch('fetch_fundamentals.ak.stock_restricted_release_queue_sina')
    def test_sina_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({"解禁日期": ["2026-06-15"]})
        result = fetch_restricted_release_sina(SYMBOL, DATE)
        assert isinstance(result, list)

    @patch('fetch_fundamentals.ak.stock_restricted_release_queue_sina')
    def test_sina_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_restricted_release_sina(SYMBOL, DATE)
        assert result == []


class TestFetchPledge:
    @patch('fetch_fundamentals.ak.stock_gpzy_individual_pledge_ratio_detail_em')
    def test_filters_unreleased_only(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "质押状态": ["未解押", "已解押", "未解押"],
            "质押比例": [5.0, 2.0, 8.0],
        })
        result = fetch_pledge(SYMBOL)
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(r["质押状态"] == "未解押" for r in result)

    @patch('fetch_fundamentals.ak.stock_gpzy_individual_pledge_ratio_detail_em')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_pledge(SYMBOL)
        assert result == []
