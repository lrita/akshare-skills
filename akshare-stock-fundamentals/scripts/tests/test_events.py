"""测试 events 板块的数据源函数。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch
import pytest
import pandas as pd

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import fetch_notices
sys.stdout = sys.__stdout__

SYMBOL = "600183"
DATE = "20260621"


class TestFetchNotices:
    @patch('fetch_fundamentals.ak.stock_individual_notice_report')
    def test_returns_list_of_dicts(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "公告日期": ["2026-06-18", "2026-05-15"],
            "公告标题": ["年度股东大会决议公告", "2025年报"],
        })
        result = fetch_notices(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) == 2

    @patch('fetch_fundamentals.ak.stock_individual_notice_report')
    def test_calls_with_correct_params(self, mock_api):
        mock_api.return_value = pd.DataFrame()
        fetch_notices(SYMBOL, DATE)
        call_args = mock_api.call_args
        assert call_args[1]["security"] == SYMBOL
        assert call_args[1]["symbol"] == "全部"

    @patch('fetch_fundamentals.ak.stock_individual_notice_report')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_notices(SYMBOL, DATE)
        assert result == []
