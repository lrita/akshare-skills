"""时间过滤逻辑测试"""
from datetime import datetime, timedelta
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fetch_news import compute_time_threshold, parse_time, filter_by_time


class TestComputeTimeThreshold:
    """compute_time_threshold 测试 — 周一使用上周五15:00，其他日使用昨日15:00"""

    def test_monday_uses_last_friday_3pm(self):
        """周一: 阈值 = 上周五 15:00"""
        fake_now = datetime(2026, 6, 22, 10, 30, 0)  # Monday
        result = compute_time_threshold(now=fake_now)
        expect = datetime(2026, 6, 19, 15, 0, 0)  # 上周五
        assert result == expect

    def test_tuesday_uses_yesterday_3pm(self):
        fake_now = datetime(2026, 6, 23, 10, 30, 0)  # Tuesday
        result = compute_time_threshold(now=fake_now)
        expect = datetime(2026, 6, 22, 15, 0, 0)  # 周一 15:00
        assert result == expect

    def test_wednesday_uses_yesterday_3pm(self):
        fake_now = datetime(2026, 6, 24, 10, 30, 0)  # Wednesday
        result = compute_time_threshold(now=fake_now)
        expect = datetime(2026, 6, 23, 15, 0, 0)
        assert result == expect

    def test_thursday_uses_yesterday_3pm(self):
        fake_now = datetime(2026, 6, 25, 10, 30, 0)  # Thursday
        result = compute_time_threshold(now=fake_now)
        expect = datetime(2026, 6, 24, 15, 0, 0)
        assert result == expect

    def test_friday_uses_yesterday_3pm(self):
        fake_now = datetime(2026, 6, 26, 10, 30, 0)  # Friday
        result = compute_time_threshold(now=fake_now)
        expect = datetime(2026, 6, 25, 15, 0, 0)
        assert result == expect

    def test_saturday_uses_yesterday_3pm(self):
        fake_now = datetime(2026, 6, 27, 10, 30, 0)  # Saturday
        result = compute_time_threshold(now=fake_now)
        expect = datetime(2026, 6, 26, 15, 0, 0)
        assert result == expect

    def test_sunday_uses_yesterday_3pm(self):
        fake_now = datetime(2026, 6, 28, 10, 30, 0)  # Sunday
        result = compute_time_threshold(now=fake_now)
        expect = datetime(2026, 6, 27, 15, 0, 0)
        assert result == expect

    def test_returns_datetime(self):
        result = compute_time_threshold()
        assert isinstance(result, datetime)


class TestParseTime:
    """parse_time 测试"""

    def test_standard_format(self):
        result = parse_time("2026-06-20 00:28:26")
        assert result == datetime(2026, 6, 20, 0, 28, 26)

    def test_sina_format(self):
        result = parse_time("2026-06-19 22:46:23")
        assert result == datetime(2026, 6, 19, 22, 46, 23)

    def test_invalid_format_returns_none(self):
        result = parse_time("invalid-time-string")
        assert result is None


class TestFilterByTime:
    """filter_by_time 测试"""

    def make_record(self, title, time_str):
        return {"title": title, "time": time_str, "content": "test"}

    def test_keep_records_after_threshold(self):
        threshold = datetime(2026, 6, 19, 15, 0, 0)
        records = [
            self.make_record("news1", "2026-06-20 08:00:00"),
            self.make_record("news2", "2026-06-19 16:00:00"),
            self.make_record("news3", "2026-06-19 14:00:00"),
        ]
        result = filter_by_time(records, threshold)
        assert len(result) == 2
        assert result[0]["title"] == "news1"
        assert result[1]["title"] == "news2"

    def test_empty_records(self):
        result = filter_by_time([], datetime.now())
        assert result == []

    def test_record_missing_time_field(self):
        threshold = datetime(2026, 6, 19, 15, 0, 0)
        records = [
            self.make_record("no_time", None),
            self.make_record("has_time", "2026-06-20 08:00:00"),
        ]
        result = filter_by_time(records, threshold)
        assert len(result) == 1
        assert result[0]["title"] == "has_time"

    def test_record_with_invalid_time(self):
        threshold = datetime(2026, 6, 19, 15, 0, 0)
        records = [
            self.make_record("bad_time", "not-a-date"),
            self.make_record("good", "2026-06-20 08:00:00"),
        ]
        result = filter_by_time(records, threshold)
        assert len(result) == 1
        assert result[0]["title"] == "good"
