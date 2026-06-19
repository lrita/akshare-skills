"""去重逻辑测试"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fetch_news import is_similar_title, deduplicate


class TestIsSimilarTitle:
    """is_similar_title 测试"""

    def test_identical_titles(self):
        assert is_similar_title("央行下调基准利率至14.25%", "央行下调基准利率至14.25%")

    def test_similar_titles(self):
        # 标题高度相似，仅标点差异
        assert is_similar_title(
            "央行宣布下调基准利率至14.25%",
            "央行下调基准利率至14.25%"
        )

    def test_different_titles(self):
        assert not is_similar_title(
            "央行下调基准利率至14.25%",
            "A股三大股指集体高开"
        )

    def test_one_empty(self):
        assert not is_similar_title("", "央行下调基准利率")
        assert not is_similar_title("央行下调基准利率", "")

    def test_very_short_titles(self):
        # 极短标题不应误判
        assert not is_similar_title("快讯", "早报")


class TestDeduplicate:
    """deduplicate 测试"""

    def make_record(self, title, content="test content"):
        return {"title": title, "time": "2026-06-20 10:00:00", "content": content}

    def test_no_duplicates(self):
        records = [
            self.make_record("新闻A"),
            self.make_record("新闻B"),
            self.make_record("新闻C"),
        ]
        result = deduplicate(records)
        assert len(result) == 3

    def test_remove_duplicate(self):
        records = [
            self.make_record("央行下调基准利率"),
            self.make_record("央行下调基准利率至14.25%"),  # 相似，应去重
        ]
        result = deduplicate(records)
        assert len(result) == 1

    def test_keep_longer_content_when_duplicate(self):
        records = [
            self.make_record("央行下调基准利率", "短内容"),
            self.make_record("央行下调基准利率至14.25%", "这是一段更长的新闻正文内容"),
        ]
        result = deduplicate(records)
        assert len(result) == 1
        assert result[0]["content"] == "这是一段更长的新闻正文内容"

    def test_empty_list(self):
        assert deduplicate([]) == []

    def test_multiple_similar_groups(self):
        records = [
            self.make_record("央行下调利率", "内容1"),
            self.make_record("央行宣布下调利率至新低", "更长的央行内容"),  # similar to above
            self.make_record("A股收涨", "内容3"),
            self.make_record("A股三大指数收涨", "更长的A股内容"),  # similar to above
        ]
        result = deduplicate(records)
        assert len(result) == 2
        # 每组的更长内容被保留
        contents = {r["content"] for r in result}
        assert "更长的央行内容" in contents
        assert "更长的A股内容" in contents
