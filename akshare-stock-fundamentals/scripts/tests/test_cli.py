"""测试 CLI 参数解析和板块编排逻辑。"""
import sys
import os
import json
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
        sections = {"basic_info": None, "fundamentals": None, "risk_signals": None, "events": None, "institutional": None}
        errors = [{"section": "basic_info", "source": "tencent_quote", "error": "timeout"}]
        result = build_output("600183", sections, errors, "20260621")
        assert result["symbol"] == "600183"
        assert "fetch_time" in result
        assert "sections" in result
        assert "errors" in result

    def test_stock_name_extracted_from_basic_info(self):
        sections = {
            "basic_info": {"profile": {"security_short_name": "生益科技"}},
            "fundamentals": {"financials": {}},
            "risk_signals": None,
            "events": None,
            "institutional": None,
        }
        result = build_output("600183", sections, [], "20260621")
        assert result["stock_name"] == "生益科技"

    def test_stock_name_fallback_to_symbol(self):
        sections = {"basic_info": None, "fundamentals": {"financials": {}}, "risk_signals": None, "events": None, "institutional": None}
        result = build_output("600183", sections, [], "20260621")
        assert result["stock_name"] == "600183"


class TestFetchAllSections:
    @patch('fetch_fundamentals.fetch_tencent_quote', return_value={"name": "test"})
    @patch('fetch_fundamentals.fetch_eastmoney_search', return_value={"security_short_name": "test"})
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
        assert set(sections.keys()) == {"basic_info", "fundamentals", "risk_signals", "events", "institutional"}

    @patch('fetch_fundamentals.fetch_tencent_quote', side_effect=Exception("fail"))
    @patch('fetch_fundamentals.fetch_eastmoney_search', side_effect=Exception("fail"))
    @patch('fetch_fundamentals.fetch_stock_add_stock', side_effect=Exception("fail"))
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
    def test_section_is_none_when_all_sources_fail(self, mock_limiter, *mocks):
        mock_limiter_instance = MagicMock()
        mock_limiter.return_value = mock_limiter_instance
        sections, errors = fetch_all_sections("600183", "20260621", mock_limiter_instance)
        assert sections["basic_info"] is None
        assert sections["fundamentals"] is not None


class TestMain:
    @patch('fetch_fundamentals.fetch_all_sections')
    def test_exit_code_0_on_success(self, mock_fetch):
        mock_fetch.return_value = (
            {"basic_info": {"profile": {"security_short_name": "test"}},
             "fundamentals": {"financials": {}}, "risk_signals": {}, "events": {}, "institutional": {}},
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
            {"basic_info": None, "fundamentals": None, "risk_signals": None,
             "events": None, "institutional": None},
            [{"section": "basic_info", "source": "tencent_quote", "error": "timeout"}]
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
            {"basic_info": {"profile": {"security_short_name": "test"}},
             "fundamentals": {}, "risk_signals": {}, "events": {}, "institutional": {}},
            []
        )
        outfile = tmp_path / "result.json"
        test_args = ["fetch_fundamentals.py", "--symbol", "600183", "--output", str(outfile)]
        with patch('sys.argv', test_args):
            exit_code = main()
        assert exit_code == 0
        assert outfile.exists()
        data = json.loads(outfile.read_text())
        assert data["symbol"] == "600183"
