"""测试 basic_info 板块的三个数据源函数。"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
import pytest
import pandas as pd

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import (
    fetch_tencent_quote,
    fetch_eastmoney_search,
    fetch_stock_add_stock,
)
sys.stdout = sys.__stdout__

SYMBOL = "600183"


def _make_mock_response(body_bytes):
    """Create a mock urlopen return value that supports .read() and acts as context manager."""
    mock = MagicMock()
    mock.read.return_value = body_bytes
    mock.__enter__.return_value = mock
    return mock


class TestFetchTencentQuote:
    """腾讯行情: HTTP GET qt.gtimg.cn, GBK 解码, 返回 dict。"""

    # GBK-encoded "生益科技"
    MOCK_BODY = (
        b'v_sh600183="1~\xc9\xfa\xd2\xe6\xbf\xc6\xbc\xbc~600183~183.87~180.15~178.50'
        b'~798770~419569~379201~183.87~1147~183.86~159~183.85~587~183.84~329~183.83~26'
        b'~183.88~165~183.89~46~183.90~77~183.91~32~183.92~30'
        b'~~20260618161425~3.72~2.06~187.35~176.73~183.87/798770/14605138345~798770~1460514'
        b'~3.34~113.69~~187.35~176.73~5.90~4402.77~4466.42~27.94~198.17~162.14~0.90~1898~182.85~96.41";\n'
    )

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_returns_dict_with_expected_keys(self, mock_urlopen):
        mock_urlopen.return_value = _make_mock_response(self.MOCK_BODY)
        result = fetch_tencent_quote("600183")
        assert isinstance(result, dict)
        assert result["name"] == "生益科技"
        assert result["price"] == 183.87
        assert result["pe_ttm"] == 113.69
        assert result["pe_dynamic"] == 96.41
        assert result["pb"] == 27.94
        assert result["total_mcap_yi"] == 4466.42
        assert result["float_mcap_yi"] == 4402.77
        assert "open" in result
        assert "high" in result
        assert "low" in result

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_adds_sh_prefix_for_6xxxxx(self, mock_urlopen):
        mock_urlopen.return_value = _make_mock_response(self.MOCK_BODY)
        fetch_tencent_quote("600183")
        # Check that the Request object URL contains sh600183
        call_req = mock_urlopen.call_args[0][0]
        assert "sh600183" in call_req.full_url

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_handles_empty_response(self, mock_urlopen):
        mock_urlopen.return_value = _make_mock_response(b"")
        result = fetch_tencent_quote("000001")
        assert result == {}


class TestFetchEastmoneySearch:
    """东财搜索: HTTP GET data.eastmoney.com/dataapi/search/company, 返回 dict。"""

    MOCK_RESP = {
        "result": {
            "companyInfo": [{
                "securityCode": "600183",
                "securityShortName": "生益科技",
                "listingDate": "1998-10-28 00:00:00",
                "totalCapital": "2429119230",
                "circulationCapital": "2394501544",
                "totalMarketValue": "446642152820",
                "circulationValue": "440276998895",
                "close": "183.87",
                "changePercent": "2.06",
                "pe": "96.41",
                "pb": "27.94",
                "companyProfile": "公司简介内容...",
                "mainBusiness": "设计、生产和销售覆铜板和粘结片",
                "mainBusinessOriginal": "设计、生产和销售覆铜板和粘结片、印制线路板",
                "businessScope": "经营范围...",
                "bk": "电子,元件,印制电路板,华为概念,HS300",
                "coreTheme": "【公司简介】广东生益科技股份有限公司创始于1985年...\r【所属板块】电子,元件\r【主营业务】设计、生产和销售\r【主营产品】主营产品：报告期：2025-12-31,覆铜板业务收入187.96亿，占比66.11%\r【经营范围】设计、生产和销售\r【公司沿革】广东生益科技股份有限公司原为东莞生益敷铜板股份有限公司..."
            }]
        }
    }

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_returns_dict_with_profile_fields(self, mock_urlopen):
        body = json.dumps(self.MOCK_RESP).encode('utf-8')
        mock_urlopen.return_value = _make_mock_response(body)
        result = fetch_eastmoney_search("600183")
        assert isinstance(result, dict)
        assert result["security_short_name"] == "生益科技"
        assert result["total_capital"] == 2429119230
        assert result["circulation_capital"] == 2394501544
        assert result["boards"] == ["电子", "元件", "印制电路板", "华为概念", "HS300"]
        assert len(result["business_products"]) > 0

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_parses_business_products_from_core_theme(self, mock_urlopen):
        body = json.dumps(self.MOCK_RESP).encode('utf-8')
        mock_urlopen.return_value = _make_mock_response(body)
        result = fetch_eastmoney_search("600183")
        assert len(result["business_products"]) > 0
        assert "product" in result["business_products"][0]
        assert "revenue_yi" in result["business_products"][0]

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_extracts_company_history(self, mock_urlopen):
        body = json.dumps(self.MOCK_RESP).encode('utf-8')
        mock_urlopen.return_value = _make_mock_response(body)
        result = fetch_eastmoney_search("600183")
        assert "company_history" in result
        assert "广东生益科技" in result["company_history"]

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_handles_no_results(self, mock_urlopen):
        empty_body = json.dumps({"result": {"companyInfo": []}}).encode('utf-8')
        mock_urlopen.return_value = _make_mock_response(empty_body)
        result = fetch_eastmoney_search("999999")
        assert result == {}


class TestFetchStockAddStock:
    """增发记录: stock_add_stock, 截取最近2年。"""

    @patch('fetch_fundamentals.ak.stock_add_stock')
    def test_returns_list_of_dicts(self, mock_api):
        mock_api.return_value = pd.DataFrame([
            {"发行方式": "定向增发", "发行价格": 12.50, "发行数量": 5000000, "上市日期": "2025-03-15"},
            {"发行方式": "公开增发", "发行价格": 10.00, "发行数量": 3000000, "上市日期": "2023-01-10"},
        ])
        result = fetch_stock_add_stock("600183", "20260621")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["发行方式"] == "定向增发"

    @patch('fetch_fundamentals.ak.stock_add_stock')
    def test_filters_by_two_years(self, mock_api):
        mock_api.return_value = pd.DataFrame([
            {"发行方式": "A", "发行价格": 1.0, "发行数量": 1, "上市日期": "2025-06-01"},
            {"发行方式": "B", "发行价格": 1.0, "发行数量": 1, "上市日期": "2021-01-01"},
        ])
        result = fetch_stock_add_stock("600183", "20260621")
        assert len(result) == 1

    @patch('fetch_fundamentals.ak.stock_add_stock')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_stock_add_stock("600183", "20260621")
        assert result == []
