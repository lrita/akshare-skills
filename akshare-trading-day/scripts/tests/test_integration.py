"""集成测试 — 需要真实网络，标记为 integration"""
from datetime import date
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
import trading_day


@pytest.mark.integration
class TestIntegration:
    """真实网络集成测试"""

    def test_load_succeeds(self):
        """验证数据加载成功"""
        trading_day._trade_dates.clear()
        trading_day._loaded = False
        trading_day._load_trade_dates()
        assert len(trading_day._trade_dates) > 5000

    def test_known_trading_day(self):
        """验证已知交易日"""
        trading_day._trade_dates.clear()
        trading_day._loaded = False
        assert trading_day.is_trading_day(date(2026, 6, 22)) is True  # Monday

    def test_known_non_trading_day(self):
        """验证已知非交易日"""
        assert trading_day.is_trading_day(date(2026, 6, 20)) is False  # Saturday

    def test_next_from_weekend(self):
        """验证周末返回周一"""
        result = trading_day.next_trading_day(date(2026, 6, 20))
        assert result is not None
        assert result.weekday() < 5  # Must be a weekday
        assert result >= date(2026, 6, 20)

    def test_count_workweek(self):
        """验证一周内有5个交易日"""
        result = trading_day.count_trading_days(
            date(2026, 6, 1), date(2026, 6, 5)
        )
        assert result == 5

    def test_cli_check_command(self):
        """验证 CLI check 命令"""
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), "..", "trading_day.py")
        result = subprocess.run(
            [sys.executable, script_path, "check", "2026-06-22"],
            capture_output=True, text=True,
        )
        import json
        data = json.loads(result.stdout)
        assert "is_trading_day" in data
        assert isinstance(data["is_trading_day"], bool)
