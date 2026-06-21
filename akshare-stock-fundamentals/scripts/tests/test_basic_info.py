"""测试 basic_info 板块的数据源函数。"""
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
import pytest
import pandas as pd

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import (
    fetch_tencent_quote,
    fetch_eastmoney_boards,
    fetch_eastmoney_profile,
    fetch_stock_add_stock,
)
sys.stdout = sys.__stdout__

SYMBOL = "600183"


def _make_mock_response(body_bytes):
    mock = MagicMock()
    mock.read.return_value = body_bytes
    mock.__enter__.return_value = mock
    return mock


class TestFetchTencentQuote:
    """腾讯行情: HTTP GET qt.gtimg.cn, GBK 解码, 返回 dict 含中文 key。"""

    MOCK_BODY = (
        b'v_sh600183="1~\xc9\xfa\xd2\xe6\xbf\xc6\xbc\xbc~600183~183.87~180.15~178.50'
        b'~798770~419569~379201~183.87~1147~183.86~159~183.85~587~183.84~329~183.83~26'
        b'~183.88~165~183.89~46~183.90~77~183.91~32~183.92~30'
        b'~~20260618161425~3.72~2.06~187.35~176.73~183.87/798770/14605138345~798770~1460514'
        b'~3.34~113.69~~187.35~176.73~5.90~4402.77~4466.42~27.94~198.17~162.14~0.90~1898~182.85~96.41";\n'
    )

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_returns_dict_with_chinese_keys(self, mock_urlopen):
        mock_urlopen.return_value = _make_mock_response(self.MOCK_BODY)
        result = fetch_tencent_quote("600183")
        assert isinstance(result, dict)
        assert result["股票名称"] == "生益科技"
        assert result["当前价格(元)"] == 183.87
        assert result["滚动市盈率"] == 113.69
        assert result["动态市盈率"] == 96.41
        assert result["市净率"] == 27.94
        assert result["总市值(亿)"] == 4466.42
        assert result["流通市值(亿)"] == 4402.77

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_adds_sh_prefix_for_6xxxxx(self, mock_urlopen):
        mock_urlopen.return_value = _make_mock_response(self.MOCK_BODY)
        fetch_tencent_quote("600183")
        call_req = mock_urlopen.call_args[0][0]
        assert "sh600183" in call_req.full_url

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_handles_empty_response(self, mock_urlopen):
        mock_urlopen.return_value = _make_mock_response(b"")
        result = fetch_tencent_quote("000001")
        assert result == {}


class TestFetchEastmoneyBoards:
    """东财板块 API: RPT_F10_CORETHEME_BOARDTYPE。"""

    MOCK_RESP = {
        "result": {
            "count": 4,
            "data": [
                {"SECUCODE": "600183.SH", "SECURITY_CODE": "600183",
                 "SECURITY_NAME_ABBR": "生益科技",
                 "NEW_BOARD_CODE": "BK1137", "BOARD_NAME": "存储芯片",
                 "SELECTED_BOARD_REASON": "封装用覆铜板技术...", "IS_PRECISE": "1",
                 "BOARD_RANK": 25, "BOARD_YIELD": 1.3},
                {"SECUCODE": "600183.SH", "SECURITY_CODE": "600183",
                 "SECURITY_NAME_ABBR": "生益科技",
                 "NEW_BOARD_CODE": "BK0877", "BOARD_NAME": "PCB",
                 "SELECTED_BOARD_REASON": "生产覆铜板和粘结片...", "IS_PRECISE": "1",
                 "BOARD_RANK": 26, "BOARD_YIELD": 1.86},
            ]
        }
    }

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_returns_list_of_boards(self, mock_urlopen):
        body = json.dumps(self.MOCK_RESP).encode('utf-8')
        mock_urlopen.return_value = _make_mock_response(body)
        result = fetch_eastmoney_boards("600183")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["板块名称"] == "存储芯片"
        assert "入选理由" in result[0]

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_correct_secucode_format(self, mock_urlopen):
        body = json.dumps(self.MOCK_RESP).encode('utf-8')
        mock_urlopen.return_value = _make_mock_response(body)
        fetch_eastmoney_boards("600183")
        # urlopen is called with (Request, timeout=10)
        req = mock_urlopen.call_args[0][0]
        assert "600183.SH" in req.full_url

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_handles_empty_response(self, mock_urlopen):
        empty = json.dumps({"result": {"data": []}}).encode('utf-8')
        mock_urlopen.return_value = _make_mock_response(empty)
        result = fetch_eastmoney_boards("999999")
        assert result == []


class TestFetchEastmoneyProfile:
    """东财档案 API: RPT_F10_CORETHEME_CONTENT。"""

    MOCK_RESP = {
        "result": {
            "data": [
                {"SECUCODE": "600183.SH", "SECURITY_CODE": "600183",
                 "SECURITY_NAME_ABBR": "生益科技",
                 "KEYWORD": "经营范围", "MAINPOINT_CONTENT": "设计、生产和销售覆铜板和粘结片...",
                 "KEY_CLASSIF": "经营范围", "KEY_CLASSIF_CODE": "002", "IS_POINT": "0"},
                {"SECUCODE": "600183.SH", "SECURITY_CODE": "600183",
                 "SECURITY_NAME_ABBR": "生益科技",
                 "KEYWORD": "设计、生产和销售覆铜板和粘结片",
                 "MAINPOINT_CONTENT": "公司从事的主要业务为...",
                 "KEY_CLASSIF": "主营业务", "KEY_CLASSIF_CODE": "003", "IS_POINT": "0"},
                {"SECUCODE": "600183.SH", "SECURITY_CODE": "600183",
                 "SECURITY_NAME_ABBR": "生益科技",
                 "KEYWORD": "电子行业",
                 "MAINPOINT_CONTENT": "电子行业掀起AI驱动的增长浪潮...",
                 "KEY_CLASSIF": "行业背景", "KEY_CLASSIF_CODE": "004", "IS_POINT": "1"},
                {"SECUCODE": "600183.SH", "SECURITY_CODE": "600183",
                 "SECURITY_NAME_ABBR": "生益科技",
                 "KEYWORD": "品牌优势",
                 "MAINPOINT_CONTENT": "公司获得多项认证...",
                 "KEY_CLASSIF": "核心竞争力", "KEY_CLASSIF_CODE": "005", "IS_POINT": "1"},
            ]
        }
    }

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_returns_dict_with_chinese_keys(self, mock_urlopen):
        body = json.dumps(self.MOCK_RESP).encode('utf-8')
        mock_urlopen.return_value = _make_mock_response(body)
        result = fetch_eastmoney_profile("600183")
        assert isinstance(result, dict)
        assert result["股票简称"] == "生益科技"
        assert "经营范围" in result
        assert "主营业务" in result

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_extracts_scope_and_business(self, mock_urlopen):
        body = json.dumps(self.MOCK_RESP).encode('utf-8')
        mock_urlopen.return_value = _make_mock_response(body)
        result = fetch_eastmoney_profile("600183")
        assert "设计、生产和销售" in result["经营范围"]
        assert "公司从事" in result["主营业务"]

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_extracts_industry_background(self, mock_urlopen):
        body = json.dumps(self.MOCK_RESP).encode('utf-8')
        mock_urlopen.return_value = _make_mock_response(body)
        result = fetch_eastmoney_profile("600183")
        assert "AI驱动" in result["行业背景"]

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_handles_empty_response(self, mock_urlopen):
        empty = json.dumps({"result": {"data": []}}).encode('utf-8')
        mock_urlopen.return_value = _make_mock_response(empty)
        result = fetch_eastmoney_profile("999999")
        assert result == {}


class TestFetchStockAddStock:
    """增发记录: stock_add_stock，截取最近2年。"""

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
