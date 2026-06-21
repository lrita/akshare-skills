"""fetch_tencent_quote_verbose 单元测试 (mock HTTP)"""
import json
import sys
import os
import urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, Mock
import pytest
import fetch_realtime


# 模拟腾讯行情 API 返回的原始数据 (gbk 编码)
# 字段顺序: 0:市场 1:名称 2:代码 3:现价 4:昨收 5:今开 6:成交量 7:外盘 8:内盘
# 9-18:买一~买五(价量对) 19-28:卖一~卖五(价量对) 29:空 30:时间
# 31:涨跌额 32:涨跌幅 33:最高 34:最低 35:价/量/额 36:成交量 37:成交额(万)
# 38:换手率 39:PE(TTM) 40:空 41:最高 42:最低 43:振幅 44:流通市值(亿)
# 45:总市值(亿) 46:PB 47:涨停价 48:跌停价 49:量比 50:委差 51:日内均价 52:动态PE
MOCK_QUOTE_FIELDS = [
    "1", "生益科技", "600183", "183.87", "180.15", "178.50", "798770",
    "419569", "379201",
    "183.87", "1147", "183.86", "159", "183.85", "587", "183.84", "329", "183.83", "26",
    "183.88", "165", "183.89", "46", "183.90", "77", "183.91", "32", "183.92", "30",
    "", "20260618161425", "3.72", "2.06", "187.35", "176.73",
    "183.87/798770/14605138345", "798770", "1460514", "3.34", "113.69",
    "", "", "", "5.90", "4402.77", "4466.42", "27.94", "198.17", "162.14",
    "0.90", "1898", "182.85", "96.41",
]

MOCK_QUOTE_RAW = (
    'v_sh600183="' + "~".join(MOCK_QUOTE_FIELDS) + '";\n'
)


class TestFetchTencentQuoteVerbose:
    """fetch_tencent_quote_verbose 单元测试"""

    def test_returns_grouped_structure(self):
        """验证返回结构包含4个分组和根级字段"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW.encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")

        assert "股票代码" in result
        assert result["股票代码"] == "600183"
        assert "股票名称" in result
        assert result["股票名称"] == "生益科技"
        assert "行情更新时间" in result
        assert result["行情更新时间"] == "20260618161425"
        assert "行情数据" in result
        assert "成交数据" in result
        assert "盘口数据" in result
        assert "估值数据" in result

    def test_quote_data_fields(self):
        """验证行情数据分组字段值和类型"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW.encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")

        q = result["行情数据"]
        assert q["当前价格(元)"] == 183.87
        assert isinstance(q["当前价格(元)"], float)
        assert q["昨收价(元)"] == 180.15
        assert q["今开价(元)"] == 178.50
        assert q["最高价(元)"] == 187.35
        assert q["最低价(元)"] == 176.73
        assert q["涨跌额(元)"] == 3.72
        assert q["涨跌幅(%)"] == 2.06
        assert q["振幅(%)"] == 5.90
        assert q["日内均价(元)"] == 182.85

    def test_trade_data_fields(self):
        """验证成交数据分组字段值和类型"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW.encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")

        t = result["成交数据"]
        assert t["成交量(手)"] == 798770
        assert isinstance(t["成交量(手)"], int)
        assert t["成交额(万元)"] == 1460514
        assert isinstance(t["成交额(万元)"], float)
        assert t["换手率(%)"] == 3.34
        assert t["量比"] == 0.90
        assert t["外盘(手)"] == 419569
        assert t["内盘(手)"] == 379201

    def test_order_book_fields(self):
        """验证盘口数据分组——买五卖五和委差"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW.encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")

        b = result["盘口数据"]
        assert b["买一价(元)"] == 183.87
        assert b["买一量(手)"] == 1147
        assert isinstance(b["买一量(手)"], int)
        assert b["买五价(元)"] == 183.83
        assert b["买五量(手)"] == 26
        assert b["卖一价(元)"] == 183.88
        assert b["卖一量(手)"] == 165
        assert b["卖五价(元)"] == 183.92
        assert b["卖五量(手)"] == 30
        assert b["委差"] == 1898
        assert isinstance(b["委差"], int)

        # 验证中间档位也被正确解析
        assert b["买二价(元)"] == 183.86
        assert b["买二量(手)"] == 159
        assert b["买三价(元)"] == 183.85
        assert b["买三量(手)"] == 587
        assert b["买四价(元)"] == 183.84
        assert b["买四量(手)"] == 329
        assert b["卖二价(元)"] == 183.89
        assert b["卖二量(手)"] == 46
        assert b["卖三价(元)"] == 183.90
        assert b["卖三量(手)"] == 77
        assert b["卖四价(元)"] == 183.91
        assert b["卖四量(手)"] == 32

    def test_valuation_fields(self):
        """验证估值数据分组字段值和类型"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW.encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")

        v = result["估值数据"]
        assert v["滚动市盈率"] == 113.69
        assert isinstance(v["滚动市盈率"], float)
        assert v["动态市盈率"] == 96.41
        assert v["市净率"] == 27.94
        assert v["流通市值(亿)"] == 4402.77
        assert v["总市值(亿)"] == 4466.42
        assert v["涨停价(元)"] == 198.17
        assert v["跌停价(元)"] == 162.14

    def test_network_error_returns_empty_dict(self):
        """网络异常返回空 dict"""
        with patch.object(
            urllib.request, "urlopen", side_effect=OSError("network")
        ):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")
        assert result == {}

    def test_short_fields_returns_empty_dict(self):
        """字段数量不足返回空 dict"""
        mock_resp = Mock()
        mock_resp.read.return_value = b'v_sh600183="1~2~3";\n'
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")
        assert result == {}

    def test_prefixed_code_sz_for_0xx(self):
        """0 开头股票使用 sz 前缀"""
        mock_resp = Mock()
        mock_resp.read.return_value = (
            'v_sz000001="' + "~".join(["1", "平安银行", "000001"] + ["0"] * 50) + '";\n'
        ).encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("000001")
        assert result["股票代码"] == "000001"
        assert result["股票名称"] == "平安银行"
