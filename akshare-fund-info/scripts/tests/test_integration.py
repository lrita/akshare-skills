"""集成测试 — 需要真实网络，标记为 integration"""
import os, sys, json, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "fund_info.py")


def run_cli(*args):
    result = subprocess.run(
        [sys.executable, SCRIPT_PATH] + list(args),
        capture_output=True, text=True,
        timeout=120,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.mark.integration
class TestRealAPI:
    def test_valid_code_returns_all_sections(self):
        rc, stdout, stderr = run_cli("--code", "000001")
        assert rc == 0
        data = json.loads(stdout)
        assert "meta" in data
        assert "overview" in data
        assert "nav_history" in data
        assert "risk_analysis" in data
        assert "profit_probability" in data
        assert "asset_allocation" in data
        assert "fee_and_rules" in data
        assert "stock_holdings" in data
        assert "bond_holdings" in data
        assert "industry_allocation" in data
        assert "errors" in data

    def test_overview_has_expected_fields(self):
        rc, stdout, stderr = run_cli("--code", "000001")
        data = json.loads(stdout)
        overview = data["overview"]
        assert overview is not None
        assert "fund_full_name" in overview
        assert "fund_type" in overview
        assert "fund_manager" in overview
        assert "benchmark" in overview

    def test_nav_history_is_list(self):
        rc, stdout, stderr = run_cli("--code", "000001")
        data = json.loads(stdout)
        nav = data["nav_history"]
        assert isinstance(nav, list)
        assert len(nav) > 100
        first = nav[0]
        assert "date" in first
        assert "unit_net_value" in first
        assert "daily_return" in first

    def test_risk_analysis_has_three_periods(self):
        rc, stdout, stderr = run_cli("--code", "000001")
        data = json.loads(stdout)
        risk = data["risk_analysis"]
        assert risk is not None
        assert len(risk) == 3

    def test_fee_and_rules_structure(self):
        rc, stdout, stderr = run_cli("--code", "000001")
        data = json.loads(stdout)
        fee = data["fee_and_rules"]
        assert fee is not None
        assert "purchase_status" in fee
        assert "redemption_fee_table" in fee
        assert "purchase_rules" in fee
        assert "redemption_rules" in fee

    def test_stock_holdings_structure(self):
        rc, stdout, stderr = run_cli("--code", "000001")
        data = json.loads(stdout)
        stock = data["stock_holdings"]
        assert stock is not None
        assert isinstance(stock, list)
        if len(stock) > 0:
            assert "stock_code" in stock[0]
            assert "net_value_ratio" in stock[0]


@pytest.mark.integration
class TestCLIErrors:
    def test_non_digit_code_exit_code_2(self):
        rc, stdout, stderr = run_cli("--code", "abcdef")
        assert rc == 2
