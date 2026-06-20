"""交易日判断测试 (mock akshare)"""
from datetime import date
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch
import trading_day


# 固定的 mock 交易日集合（10天）
MOCK_DATES = {
    date(2026, 6, 15),  # Monday
    date(2026, 6, 16),  # Tuesday
    date(2026, 6, 17),  # Wednesday
    date(2026, 6, 18),  # Thursday
    date(2026, 6, 19),  # Friday
    date(2026, 6, 22),  # Monday next week
    date(2026, 6, 23),  # Tuesday
    date(2026, 6, 24),  # Wednesday
    date(2026, 6, 25),  # Thursday
    date(2026, 6, 26),  # Friday
}


class TestIsTradingDay:
    """is_trading_day 测试"""

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_trading_day_returns_true(self):
        assert trading_day.is_trading_day(date(2026, 6, 15)) is True

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_non_trading_day_returns_false(self):
        # Saturday
        assert trading_day.is_trading_day(date(2026, 6, 20)) is False

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_sunday_not_trading_day(self):
        assert trading_day.is_trading_day(date(2026, 6, 21)) is False


class TestNextTradingDay:
    """next_trading_day 测试"""

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_input_is_trading_day_returns_self(self):
        result = trading_day.next_trading_day(date(2026, 6, 15))
        assert result == date(2026, 6, 15)

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_saturday_returns_monday(self):
        result = trading_day.next_trading_day(date(2026, 6, 20))
        assert result == date(2026, 6, 22)

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_sunday_returns_monday(self):
        result = trading_day.next_trading_day(date(2026, 6, 21))
        assert result == date(2026, 6, 22)

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_friday_after_hours_returns_friday(self):
        result = trading_day.next_trading_day(date(2026, 6, 19))
        assert result == date(2026, 6, 19)

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_beyond_last_trading_day_returns_none(self):
        result = trading_day.next_trading_day(date(2026, 6, 27))
        assert result is None

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_before_first_trading_day_returns_first(self):
        result = trading_day.next_trading_day(date(2026, 6, 10))
        assert result == date(2026, 6, 15)


class TestCountTradingDays:
    """count_trading_days 测试"""

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_full_workweek(self):
        result = trading_day.count_trading_days(
            date(2026, 6, 15), date(2026, 6, 19)
        )
        assert result == 5

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_range_includes_weekend(self):
        result = trading_day.count_trading_days(
            date(2026, 6, 15), date(2026, 6, 22)
        )
        assert result == 6  # 5 weekdays + Monday

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_single_trading_day(self):
        result = trading_day.count_trading_days(
            date(2026, 6, 15), date(2026, 6, 15)
        )
        assert result == 1

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_single_weekend_day(self):
        result = trading_day.count_trading_days(
            date(2026, 6, 20), date(2026, 6, 20)
        )
        assert result == 0

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_empty_range(self):
        result = trading_day.count_trading_days(
            date(2026, 6, 22), date(2026, 6, 19)
        )
        assert result == 0

    @patch.object(trading_day, '_loaded', True)
    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_beyond_data_range(self):
        result = trading_day.count_trading_days(
            date(2026, 6, 27), date(2026, 6, 30)
        )
        assert result == 0
