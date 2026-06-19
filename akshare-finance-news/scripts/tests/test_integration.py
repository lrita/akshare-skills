"""集成测试 — 需要真实网络，标记为 integration"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from fetch_news import fetch_all_news, is_similar_title, compute_time_threshold, parse_time


@pytest.mark.integration
class TestIntegration:
    """端到端集成测试"""

    def test_fetch_all_news_returns_valid_structure(self):
        """验证返回结构符合预期"""
        result = fetch_all_news()

        assert isinstance(result, dict)
        assert "fetch_time" in result
        assert "total_count" in result
        assert "news" in result
        assert "errors" in result
        assert isinstance(result["news"], list)
        assert isinstance(result["errors"], list)

    def test_news_items_have_required_fields(self):
        """验证每条新闻包含必需字段"""
        result = fetch_all_news()

        assert len(result["news"]) > 0, "应至少返回一条新闻"
        for item in result["news"]:
            assert "title" in item
            assert "time" in item
            assert "content" in item
            # 不应包含 url 和 source 字段
            assert "url" not in item
            assert "source" not in item

    def test_total_count_matches_news_length(self):
        """验证 total_count 与 news 数组长度一致"""
        result = fetch_all_news()
        assert result["total_count"] == len(result["news"])

    def test_no_duplicate_titles(self):
        """验证无重复标题"""
        result = fetch_all_news()
        if result["total_count"] < 2:
            pytest.skip("新闻数量不足，跳过去重验证")
        titles = [item["title"] for item in result["news"]]
        for i in range(len(titles)):
            for j in range(i + 1, len(titles)):
                assert not is_similar_title(titles[i], titles[j]), \
                    f"发现重复标题: '{titles[i]}' 和 '{titles[j]}'"

    def test_all_news_within_time_range(self):
        """验证所有新闻都在时间范围内"""
        result = fetch_all_news()
        threshold = compute_time_threshold()
        for item in result["news"]:
            parsed = parse_time(item["time"])
            if parsed is not None:
                assert parsed >= threshold, \
                    f"新闻 '{item['title']}' 时间 {item['time']} 早于阈值 {threshold}"
