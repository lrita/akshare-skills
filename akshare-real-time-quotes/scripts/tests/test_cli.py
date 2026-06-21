"""CLI 参数解析和子命令调度单元测试"""
import json
import sys
import os
import io
import urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, Mock
import pytest
import fetch_realtime


# 复刻任务 2 中的 mock 数据
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
).encode("gbk")


class TestCLI:
    """CLI 集成测试（mock 网络）"""

    def test_quote_subcommand_outputs_json(self):
        """quote 子命令输出有效 JSON"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            with patch.object(sys, "argv", ["fetch_realtime.py", "quote", "--symbol", "600183"]):
                stdout = io.StringIO()
                with patch.object(sys, "stdout", stdout):
                    fetch_realtime.main()

        output = json.loads(stdout.getvalue())
        assert output["股票代码"] == "600183"
        assert "股票名称" in output
        assert "行情数据" in output
        assert "成交数据" in output
        assert "盘口数据" in output
        assert "估值数据" in output

    def test_quote_with_output_file(self, tmp_path):
        """--output 参数将 JSON 写入文件"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        out_file = tmp_path / "quote.json"
        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            test_args = [
                "fetch_realtime.py", "quote", "--symbol", "600183",
                "--output", str(out_file),
            ]
            with patch.object(sys, "argv", test_args):
                fetch_realtime.main()

        assert out_file.exists()
        content = json.loads(out_file.read_text(encoding="utf-8"))
        assert content["股票代码"] == "600183"

    def test_invalid_symbol_exits_2(self):
        """非法股票代码 exit 2"""
        with patch.object(sys, "argv", ["fetch_realtime.py", "quote", "--symbol", "123"]):
            with pytest.raises(SystemExit) as exc_info:
                fetch_realtime.main()
        assert exc_info.value.code == 2

    def test_non_numeric_symbol_exits_2(self):
        """非数字股票代码 exit 2"""
        with patch.object(sys, "argv", ["fetch_realtime.py", "quote", "--symbol", "abcdef"]):
            with pytest.raises(SystemExit) as exc_info:
                fetch_realtime.main()
        assert exc_info.value.code == 2

    def test_intraday_subcommand_outputs_json(self):
        """intraday 子命令输出有效 JSON"""
        mock_json = {
            "data": {
                "sh600183": {
                    "data": {
                        "date": "20260618",
                        "data": ["0930 178.50 13747 245383950.50"],
                    },
                    "qt": {"sh600183": ["1", "生益科技", "600183"]},
                    "mx_price": {"price": "", "mx": ""}
                }
            }
        }
        mock_raw = ("min_data=" + json.dumps(mock_json)).encode("utf-8")
        mock_resp = Mock()
        mock_resp.read.return_value = mock_raw
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            test_args = ["fetch_realtime.py", "intraday", "--symbol", "600183"]
            with patch.object(sys, "argv", test_args):
                stdout = io.StringIO()
                with patch.object(sys, "stdout", stdout):
                    fetch_realtime.main()

        output = json.loads(stdout.getvalue())
        assert output["股票代码"] == "600183"
        assert output["交易日期"] == "20260618"
        assert len(output["分钟K线"]) == 1
        assert output["分钟K线"][0]["时间"] == "0930"

    def test_missing_symbol_arg_errors(self):
        """缺少 --symbol 参数时报错"""
        with patch.object(sys, "argv", ["fetch_realtime.py", "quote"]):
            with pytest.raises(SystemExit) as exc_info:
                fetch_realtime.main()
        assert exc_info.value.code != 0

    def test_quote_api_failure_returns_empty(self):
        """API 完全失败时输出空结构但不崩溃"""
        with patch.object(urllib.request, "urlopen", side_effect=OSError("down")):
            test_args = ["fetch_realtime.py", "quote", "--symbol", "600183"]
            with patch.object(sys, "argv", test_args):
                stdout = io.StringIO()
                with patch.object(sys, "stdout", stdout):
                    fetch_realtime.main()

        output = json.loads(stdout.getvalue())
        assert output["股票代码"] == "600183"
        # API 失败返回空字段
