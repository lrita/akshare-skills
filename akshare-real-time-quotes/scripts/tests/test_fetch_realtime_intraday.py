"""fetch_intraday_minute 单元测试 (mock HTTP)"""
import json
import sys
import os
import urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, Mock
import fetch_realtime


# 模拟腾讯分钟K线 API 返回的 JSON 数据
MOCK_INTRADAY_JSON = {
    "data": {
        "sh600183": {
            "data": {
                "date": "20260618",
                "data": [
                    "0930 178.50 13747 245383950.50",
                    "0931 178.80 8921 159423180.00",
                    "0932 179.00 12500 223750000.00",
                    "0933 178.65 9800 175077000.00",
                ]
            },
            "qt": {
                "sh600183": [
                    "1", "生益科技", "600183", "183.87", "180.15",
                ]
            },
            "mx_price": {"price": "", "mx": ""}
        }
    }
}

MOCK_INTRADAY_RAW = ("min_data=" + json.dumps(MOCK_INTRADAY_JSON)).encode("utf-8")


class TestFetchIntradayMinute:
    """fetch_intraday_minute 单元测试"""

    def test_returns_correct_structure(self):
        """验证返回结构包含股票代码、名称、交易日期、分钟K线"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_INTRADAY_RAW
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_intraday_minute("600183")

        assert "股票代码" in result
        assert result["股票代码"] == "600183"
        assert "股票名称" in result
        assert result["股票名称"] == "生益科技"
        assert "交易日期" in result
        assert result["交易日期"] == "20260618"
        assert "分钟K线" in result
        assert isinstance(result["分钟K线"], list)

    def test_parses_minute_data_correctly(self):
        """验证分钟数据解析——时间、价格、成交量、成交额类型正确"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_INTRADAY_RAW
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_intraday_minute("600183")

        minutes = result["分钟K线"]
        assert len(minutes) == 4

        first = minutes[0]
        assert first["时间"] == "0930"
        assert isinstance(first["时间"], str)
        assert first["价格(元)"] == 178.50
        assert isinstance(first["价格(元)"], float)
        assert first["成交量"] == 13747
        assert isinstance(first["成交量"], int)
        assert first["成交额(元)"] == 245383950.50
        assert isinstance(first["成交额(元)"], float)

        last = minutes[-1]
        assert last["时间"] == "0933"
        assert last["价格(元)"] == 178.65
        assert last["成交量"] == 9800

    def test_network_error_returns_empty_dict(self):
        """网络异常返回空 dict"""
        with patch.object(
            urllib.request, "urlopen", side_effect=OSError("timeout")
        ):
            result = fetch_realtime.fetch_intraday_minute("600183")
        assert result == {}

    def test_malformed_minute_string_skipped(self):
        """格式异常的分钟字符串被跳过"""
        bad_json = {
            "data": {
                "sh600183": {
                    "data": {
                        "date": "20260618",
                        "data": [
                            "0930 178.50 13747 245383950.50",   # 正常
                            "not-valid-data",                      # 格式错误
                            "0932 179.00 12500 223750000.00",   # 正常
                        ]
                    },
                    "qt": {"sh600183": ["1", "生益科技", "600183"]},
                    "mx_price": {"price": "", "mx": ""}
                }
            }
        }
        bad_raw = ("min_data=" + json.dumps(bad_json)).encode("utf-8")
        mock_resp = Mock()
        mock_resp.read.return_value = bad_raw
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_intraday_minute("600183")

        minutes = result["分钟K线"]
        assert len(minutes) == 2
        assert minutes[0]["时间"] == "0930"
        assert minutes[1]["时间"] == "0932"

    def test_empty_data_returns_empty_list(self):
        """无分钟数据时返回空列表"""
        empty_json = {
            "data": {
                "sh600183": {
                    "data": {"date": "20260618", "data": []},
                    "qt": {"sh600183": ["1", "生益科技", "600183"]},
                    "mx_price": {"price": "", "mx": ""}
                }
            }
        }
        empty_raw = ("min_data=" + json.dumps(empty_json)).encode("utf-8")
        mock_resp = Mock()
        mock_resp.read.return_value = empty_raw
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_intraday_minute("600183")

        assert result["分钟K线"] == []

    def test_prefixed_code_bj_for_8xx(self):
        """8 开头股票使用 bj 前缀"""
        bj_json = {
            "data": {
                "bj830799": {
                    "data": {"date": "20260618", "data": []},
                    "qt": {"bj830799": ["1", "艾融软件", "830799"]},
                    "mx_price": {"price": "", "mx": ""}
                }
            }
        }
        bj_raw = ("min_data=" + json.dumps(bj_json)).encode("utf-8")
        mock_resp = Mock()
        mock_resp.read.return_value = bj_raw
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_intraday_minute("830799")

        assert result["股票代码"] == "830799"
        assert result["股票名称"] == "艾融软件"

    def test_prefixed_code_sz_for_3xx(self):
        """3 开头股票使用 sz 前缀"""
        sz_json = {
            "data": {
                "sz300750": {
                    "data": {"date": "20260618", "data": [
                        "0930 210.00 5000 105000000.00",
                    ]},
                    "qt": {"sz300750": ["1", "宁德时代", "300750"]},
                    "mx_price": {"price": "", "mx": ""}
                }
            }
        }
        sz_raw = ("min_data=" + json.dumps(sz_json)).encode("utf-8")
        mock_resp = Mock()
        mock_resp.read.return_value = sz_raw
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_intraday_minute("300750")

        assert result["股票代码"] == "300750"
        assert result["股票名称"] == "宁德时代"
        assert len(result["分钟K线"]) == 1
        assert result["分钟K线"][0]["价格(元)"] == 210.00
