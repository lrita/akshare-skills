import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
import pytest

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import parse_args, build_output, fetch_all_sections, main
sys.stdout = sys.__stdout__


class TestParseArgs:
    def test_parses_symbol_required(self):
        test_args = ["--symbol", "600183"]
        with patch('sys.argv', ['fetch_fundamentals.py'] + test_args):
            args = parse_args()
            assert args.symbol == "600183"

    def test_date_defaults_to_today(self):
        test_args = ["--symbol", "600183"]
        with patch('sys.argv', ['fetch_fundamentals.py'] + test_args):
            args = parse_args()
            assert args.date is not None
            assert len(args.date) == 8

    def test_symbol_validation_rejects_non_numeric(self):
        test_args = ["--symbol", "ABC123"]
        with patch('sys.argv', ['fetch_fundamentals.py'] + test_args):
            with pytest.raises(SystemExit):
                parse_args()


class TestBuildOutput:
    def test_builds_correct_top_level_structure(self):
        sections = {"基础信息": None, "财务基本面": None, "风险信号": None,
                    "重大事件": None, "机构动向": None}
        errors = [{"板块": "基础信息", "数据源": "tencent_quote", "错误": "timeout"}]
        result = build_output("600183", sections, errors, "20260621")
        assert result["股票代码"] == "600183"
        assert "数据获取时间" in result
        assert "板块数据" in result
        assert "错误信息" in result

    def test_stock_name_extracted_from_basic_info(self):
        sections = {
            "基础信息": {"公司档案": {"股票简称": "生益科技"}},
            "财务基本面": {"财务报表": {}},
            "风险信号": None, "重大事件": None, "机构动向": None,
        }
        result = build_output("600183", sections, [], "20260621")
        assert result["股票名称"] == "生益科技"

    def test_stock_name_fallback_to_symbol(self):
        sections = {"基础信息": None, "财务基本面": {"财务报表": {}},
                    "风险信号": None, "重大事件": None, "机构动向": None}
        result = build_output("600183", sections, [], "20260621")
        assert result["股票名称"] == "600183"


class TestFetchAllSections:
    @patch('fetch_fundamentals.fetch_tencent_quote', return_value={"股票名称": "test"})
    @patch('fetch_fundamentals.fetch_eastmoney_boards', return_value=[])
    @patch('fetch_fundamentals.fetch_eastmoney_profile', return_value={"股票简称": "test"})
    @patch('fetch_fundamentals.fetch_stock_add_stock', return_value=[])
    @patch('fetch_fundamentals.fetch_financial_abstract', return_value=[])
    @patch('fetch_fundamentals.fetch_financial_profit', return_value=[])
    @patch('fetch_fundamentals.fetch_financial_debt', return_value=[])
    @patch('fetch_fundamentals.fetch_financial_cashflow', return_value=[])
    @patch('fetch_fundamentals.fetch_profit_forecast_eps', return_value=[])
    @patch('fetch_fundamentals.fetch_profit_forecast_net', return_value=[])
    @patch('fetch_fundamentals.fetch_profit_forecast_inst', return_value=[])
    @patch('fetch_fundamentals.fetch_profit_forecast_detail', return_value=[])
    @patch('fetch_fundamentals.fetch_revenue_structure', return_value=[])
    @patch('fetch_fundamentals.fetch_block_trades', return_value=[])
    @patch('fetch_fundamentals.fetch_restricted_release_em', return_value=[])
    @patch('fetch_fundamentals.fetch_restricted_release_sina', return_value=[])
    @patch('fetch_fundamentals.fetch_pledge', return_value=[])
    @patch('fetch_fundamentals.fetch_notices', return_value=[])
    @patch('fetch_fundamentals.fetch_research_visits', return_value=[])
    @patch('fetch_fundamentals.RateLimiter')
    def test_returns_all_five_sections(self, mock_limiter, *mocks):
        mock_limiter_instance = MagicMock()
        mock_limiter.return_value = mock_limiter_instance
        sections, errors = fetch_all_sections("600183", "20260621", mock_limiter_instance)
        assert set(sections.keys()) == {"基础信息", "财务基本面", "风险信号", "重大事件", "机构动向"}


class TestMain:
    @patch('fetch_fundamentals.fetch_all_sections')
    def test_exit_code_0_on_success(self, mock_fetch):
        mock_fetch.return_value = (
            {"基础信息": {"公司档案": {"股票简称": "test"}},
             "财务基本面": {"财务报表": {}}, "风险信号": {},
             "重大事件": {}, "机构动向": {}},
            []
        )
        test_args = ["fetch_fundamentals.py", "--symbol", "600183"]
        with patch('sys.argv', test_args):
            with patch('sys.stdout.write'):
                exit_code = main()
                assert exit_code == 0

    @patch('fetch_fundamentals.fetch_all_sections')
    def test_exit_code_1_when_all_sections_none(self, mock_fetch):
        mock_fetch.return_value = (
            {"基础信息": None, "财务基本面": None, "风险信号": None,
             "重大事件": None, "机构动向": None},
            [{"板块": "基础信息", "数据源": "tencent_quote", "错误": "timeout"}]
        )
        test_args = ["fetch_fundamentals.py", "--symbol", "600183"]
        with patch('sys.argv', test_args):
            with patch('sys.stdout.write'):
                exit_code = main()
                assert exit_code == 1

    def test_exit_code_2_on_invalid_symbol(self):
        test_args = ["fetch_fundamentals.py", "--symbol", "ABC"]
        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    @patch('fetch_fundamentals.fetch_all_sections')
    def test_output_writes_to_file(self, mock_fetch, tmp_path):
        mock_fetch.return_value = (
            {"基础信息": {"公司档案": {"股票简称": "test"}},
             "财务基本面": {}, "风险信号": {}, "重大事件": {}, "机构动向": {}},
            []
        )
        outfile = tmp_path / "result.json"
        test_args = ["fetch_fundamentals.py", "--symbol", "600183", "--output", str(outfile)]
        with patch('sys.argv', test_args):
            exit_code = main()
        assert exit_code == 0
        assert outfile.exists()
        data = json.loads(outfile.read_text())
        assert data["股票代码"] == "600183"
