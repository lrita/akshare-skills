"""测试 institutional 板块的数据源函数。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch
import pytest
import pandas as pd

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import fetch_research_visits
sys.stdout = sys.__stdout__

SYMBOL = "600183"
DATE = "20260621"


class TestFetchResearchVisits:
    @patch('fetch_fundamentals.ak.stock_jgdy_tj_em')
    def test_filters_by_stock_code(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "股票代码": ["600183", "600184"],
            "股票名称": ["生益科技", "光电股份"],
        })
        result = fetch_research_visits(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["股票代码"] == "600183"

    @patch('fetch_fundamentals.ak.stock_jgdy_tj_em')
    def test_handles_api_error_gracefully(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_research_visits(SYMBOL, DATE)
        assert result == []
