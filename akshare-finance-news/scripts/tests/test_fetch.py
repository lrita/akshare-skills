"""内容抓取测试 (mock HTTP 请求)"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, MagicMock
from fetch_news import build_browser_headers, extract_text_from_html


class TestBuildBrowserHeaders:
    """build_browser_headers 测试"""

    def test_returns_dict(self):
        headers = build_browser_headers()
        assert isinstance(headers, dict)

    def test_contains_user_agent(self):
        headers = build_browser_headers()
        assert "User-Agent" in headers
        assert "Chrome" in headers["User-Agent"]

    def test_contains_accept_headers(self):
        headers = build_browser_headers()
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "Accept-Encoding" in headers

    def test_contains_cache_control(self):
        headers = build_browser_headers()
        assert "Cache-Control" in headers


class TestExtractTextFromHtml:
    """extract_text_from_html 测试"""

    def test_extract_from_article_tag(self):
        html = """
        <html><head><title>test</title></head><body>
        <article><p>这是正文第一段。</p><p>这是正文第二段。</p></article>
        </body></html>
        """
        text = extract_text_from_html(html)
        assert "这是正文第一段" in text
        assert "这是正文第二段" in text

    def test_extract_from_paragraphs(self):
        html = """
        <html><body>
        <div class="content"><p>段落1内容。</p><p>段落2内容。</p></div>
        </body></html>
        """
        text = extract_text_from_html(html)
        assert "段落1内容" in text
        assert "段落2内容" in text

    def test_removes_script_tags(self):
        html = """
        <html><body>
        <script>console.log('remove me');</script>
        <p>正常内容。</p>
        </body></html>
        """
        text = extract_text_from_html(html)
        assert "console.log" not in text
        assert "正常内容" in text

    def test_removes_style_tags(self):
        html = """
        <html><head><style>.red { color: red; }</style></head>
        <body><p>正常内容。</p></body></html>
        """
        text = extract_text_from_html(html)
        assert ".red" not in text
        assert "正常内容" in text

    def test_empty_html(self):
        text = extract_text_from_html("")
        assert text == ""

    def test_none_html(self):
        text = extract_text_from_html(None)
        assert text == ""


class TestFetchArticleContent:
    """fetch_article_content 测试 (mock requests)"""

    @patch("fetch_news.requests.get")
    def test_successful_fetch(self, mock_get):
        from fetch_news import fetch_article_content

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><article><p>新闻全文内容。</p></article></body></html>"
        mock_get.return_value = mock_response

        content = fetch_article_content("https://example.com/news/123")
        assert "新闻全文内容" in content
        mock_get.assert_called_once()

    @patch("fetch_news.requests.get")
    def test_retry_on_failure(self, mock_get):
        from fetch_news import fetch_article_content

        # 第一次失败，第二次成功
        fail_response = MagicMock()
        fail_response.status_code = 500
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.text = "<html><body><p>重试后成功。</p></body></html>"
        mock_get.side_effect = [fail_response, success_response]

        content = fetch_article_content("https://example.com/news/456")
        assert "重试后成功" in content
        assert mock_get.call_count == 2

    @patch("fetch_news.requests.get")
    @patch("time.sleep", return_value=None)  # 不真实等待
    def test_returns_none_after_all_retries(self, mock_sleep, mock_get):
        from fetch_news import fetch_article_content

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        content = fetch_article_content("https://example.com/news/789")
        assert content is None
        assert mock_get.call_count == 2  # 初次 + 1 次重试

    @patch("fetch_news.requests.get")
    @patch("time.sleep", return_value=None)
    def test_timeout_handled(self, mock_sleep, mock_get):
        from fetch_news import fetch_article_content
        import requests as req

        mock_get.side_effect = req.Timeout("Request timed out")

        content = fetch_article_content("https://example.com/timeout")
        assert content is None
        assert mock_get.call_count == 2  # 初次 + 1 次重试

    @patch("fetch_news.requests.get")
    def test_browser_headers_used(self, mock_get):
        from fetch_news import fetch_article_content

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>内容</p></body></html>"
        mock_get.return_value = mock_response

        fetch_article_content("https://example.com/news")
        call_kwargs = mock_get.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert "User-Agent" in headers
        assert "Chrome" in headers["User-Agent"]
        assert call_kwargs.get("timeout") == 15
