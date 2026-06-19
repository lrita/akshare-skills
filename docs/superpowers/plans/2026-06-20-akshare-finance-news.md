# akshare-finance-news 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建一个财经快讯 SKILL，从 4 个财经数据源并发获取新闻，按时间过滤，去重，抓取完整内容，输出结构化 JSON。

**架构：** SKILL.md 描述使用方式 + `scripts/fetch_news.py` 封装核心流水线。使用 `concurrent.futures.ThreadPoolExecutor` 实现 API 调用和内容抓取的并发控制，BeautifulSoup 提取正文，输出 JSON 到 stdout。

**技术栈：** Python ≥ 3.10, akshare, requests, beautifulsoup4, difflib (stdlib), concurrent.futures (stdlib)

---

### 任务 1：创建目录结构与 SKILL.md

**文件：**
- 创建：`akshare-finance-news/SKILL.md`
- 创建：`akshare-finance-news/scripts/__init__.py`
- 创建：`akshare-finance-news/scripts/tests/__init__.py`

- [ ] **步骤 1：创建 SKILL.md**

```markdown
---
name: akshare-finance-news
description: Use when the user wants to fetch the latest Chinese financial news and analyze their potential impact on the A-stock market, or when they need a summary of recent financial events from Chinese financial media sources including Eastmoney, Sina Finance, and 10jqka.
---

# 财经快讯分析

## 概述

从东财财经早餐、东财全球快讯、新浪财经快讯、同花顺财经直播 4 个数据源获取当日及昨日 15:00 后的财经新闻，提取完整内容，输出结构化 JSON 供大模型分析对 A 股的影响。

## 使用方式

运行 `scripts/fetch_news.py`，获得结构化 JSON 新闻列表。

```bash
uv run python scripts/fetch_news.py
```

脚本将 JSON 输出到 stdout，运行日志输出到 stderr。

## 输出格式

```json
{
  "fetch_time": "2026-06-20 14:30:00",
  "total_count": 15,
  "news": [
    {
      "title": "央行下调基准利率至14.25%",
      "time": "2026-06-20 00:28:26",
      "content": "完整新闻正文..."
    }
  ],
  "errors": [
    {"title": "某新闻标题", "error": "timeout"}
  ]
}
```

## 分析 Prompt

拿到 JSON 输出后，将 `news` 数组中的内容与以下 prompt 一起提交给大模型：

> 以下是最近24小时内的财经新闻。请逐一分析每条新闻对今日A股盘面可能造成的影响，包括：
> 1. 可能受影响的板块和个股
> 2. 预计影响方向和程度（利好/利空，强/中/弱）
> 3. 综合判断今日市场情绪
>
> 如果某条新闻对A股无明显影响，简单说明原因后跳过。

## 依赖

```bash
uv pip install akshare requests beautifulsoup4
```
```

- [ ] **步骤 2：创建 `__init__.py` 文件**

```bash
touch akshare-finance-news/scripts/__init__.py
touch akshare-finance-news/scripts/tests/__init__.py
```

- [ ] **步骤 3：Commit**

```bash
git add akshare-finance-news/
git commit -m "feat: add akshare-finance-news SKILL.md and directory structure

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 2：时间过滤模块（TDD）

**文件：**
- 创建：`akshare-finance-news/scripts/tests/test_filter.py`
- 创建：`akshare-finance-news/scripts/fetch_news.py`（初始版本，仅包含过滤相关函数）

- [ ] **步骤 1：编写失败的测试**

在 `akshare-finance-news/scripts/tests/test_filter.py` 中：

```python
"""时间过滤逻辑测试"""
from datetime import datetime, timedelta
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fetch_news import compute_time_threshold, parse_time, filter_by_time


class TestComputeTimeThreshold:
    """compute_time_threshold 测试"""

    def test_returns_datetime(self):
        result = compute_time_threshold()
        assert isinstance(result, datetime)

    def test_is_yesterday_3pm(self):
        result = compute_time_threshold()
        now = datetime.now()
        assert result.hour == 15
        assert result.minute == 0
        assert result.second == 0
        # 日期应该是今天或昨天（取决于当前时间是否在 15:00 之前或之后）
        # 实际需求：保留 >= 昨日 15:00 的记录
        # 阈值就是昨天 15:00
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        expected = yesterday.replace(hour=15, minute=0, second=0)
        assert result == expected


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
```

- [ ] **步骤 2：运行测试验证失败**

```bash
uv run pytest akshare-finance-news/scripts/tests/test_filter.py -v
```
预期：全部 FAIL（函数未定义）

- [ ] **步骤 3：编写最少实现代码**

在 `akshare-finance-news/scripts/fetch_news.py` 中：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
财经快讯数据获取脚本
从 4 个数据源获取财经新闻，过滤、去重、抓取内容，输出结构化 JSON
"""
from datetime import datetime, timedelta
import sys


def compute_time_threshold() -> datetime:
    """计算时间阈值：昨日 15:00:00"""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    return yesterday.replace(hour=15, minute=0, second=0)


def parse_time(time_str: str) -> datetime | None:
    """解析时间字符串，支持多种格式，失败返回 None"""
    if not time_str or not isinstance(time_str, str):
        return None
    try:
        return datetime.strptime(time_str.strip(), "%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return None


def filter_by_time(records: list[dict], threshold: datetime) -> list[dict]:
    """过滤记录，保留发布时间 >= threshold 的记录"""
    result = []
    for record in records:
        time_str = record.get("time")
        parsed = parse_time(time_str)
        if parsed is None:
            continue
        if parsed >= threshold:
            result.append(record)
    return result
```

- [ ] **步骤 4：运行测试验证通过**

```bash
uv run pytest akshare-finance-news/scripts/tests/test_filter.py -v
```
预期：全部 PASS (7 tests)

- [ ] **步骤 5：Commit**

```bash
git add akshare-finance-news/scripts/fetch_news.py akshare-finance-news/scripts/tests/test_filter.py
git commit -m "feat: add time filtering module with tests

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 3：去重模块（TDD）

**文件：**
- 创建：`akshare-finance-news/scripts/tests/test_dedup.py`
- 修改：`akshare-finance-news/scripts/fetch_news.py`（添加去重函数）

- [ ] **步骤 1：编写失败的测试**

在 `akshare-finance-news/scripts/tests/test_dedup.py` 中：

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

```bash
uv run pytest akshare-finance-news/scripts/tests/test_dedup.py -v
```
预期：全部 FAIL（函数未定义）

- [ ] **步骤 3：编写最少实现代码**

在 `akshare-finance-news/scripts/fetch_news.py` 的 import 区域添加：

```python
from difflib import SequenceMatcher
```

在文件末尾添加：

```python
def is_similar_title(title1: str, title2: str, threshold: float = 0.75) -> bool:
    """判断两个标题是否相似 (基于 SequenceMatcher)

    参数:
        title1: 第一个标题
        title2: 第二个标题
        threshold: 相似度阈值，默认 0.75

    返回:
        bool: 相似则为 True
    """
    if not title1 or not title2:
        return False
    # 极短标题(少于5字符)不参与相似度判断
    if len(title1) < 5 or len(title2) < 5:
        return False
    return SequenceMatcher(None, title1, title2).ratio() >= threshold


def deduplicate(records: list[dict]) -> list[dict]:
    """按标题相似度去重，相似记录保留内容更长的

    参数:
        records: 新闻记录列表

    返回:
        list[dict]: 去重后的记录列表
    """
    if not records:
        return []

    result = []
    for record in records:
        found_similar = False
        for i, existing in enumerate(result):
            if is_similar_title(record.get("title", ""), existing.get("title", "")):
                found_similar = True
                # 保留内容更长的
                if len(record.get("content", "")) > len(existing.get("content", "")):
                    result[i] = record
                break
        if not found_similar:
            result.append(record)
    return result
```

- [ ] **步骤 4：运行测试验证通过**

```bash
uv run pytest akshare-finance-news/scripts/tests/test_dedup.py -v
```
预期：全部 PASS (8 tests)

- [ ] **步骤 5：Commit**

```bash
git add akshare-finance-news/scripts/fetch_news.py akshare-finance-news/scripts/tests/test_dedup.py
git commit -m "feat: add deduplication module with tests

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 4：内容抓取模块（TDD）

**文件：**
- 创建：`akshare-finance-news/scripts/tests/test_fetch.py`
- 修改：`akshare-finance-news/scripts/fetch_news.py`（添加抓取相关函数）

- [ ] **步骤 1：编写失败的测试**

在 `akshare-finance-news/scripts/tests/test_fetch.py` 中：

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

```bash
uv run pytest akshare-finance-news/scripts/tests/test_fetch.py -v
```
预期：全部 FAIL（函数未定义）

- [ ] **步骤 3：编写最少实现代码**

在 `akshare-finance-news/scripts/fetch_news.py` 的 import 区域添加：

```python
import requests
from bs4 import BeautifulSoup
import time
import random
```

在文件末尾添加：

```python
def build_browser_headers() -> dict[str, str]:
    """构建模拟真实浏览器的请求头

    返回:
        dict: HTTP 请求头字典
    """
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }


def extract_text_from_html(html: str | None) -> str:
    """从 HTML 中提取正文文本

    参数:
        html: HTML 字符串

    返回:
        str: 提取的纯文本
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # 移除 script 和 style 标签
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # 优先从 article 标签提取
    article = soup.find("article")
    if article:
        return article.get_text(separator="\n", strip=True)

    # 尝试常见的内容容器
    for selector in [".article-content", ".news-content", "#article", ".content", ".main-content"]:
        container = soup.select_one(selector)
        if container:
            return container.get_text(separator="\n", strip=True)

    # 降级：从 body 提取
    body = soup.find("body")
    if body:
        text = body.get_text(separator="\n", strip=True)
        # 去除空行
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)

    return ""


def fetch_article_content(url: str) -> str | None:
    """抓取文章完整内容（含反爬策略）

    参数:
        url: 文章链接

    返回:
        str | None: 成功返回正文，失败返回 None
    """
    headers = build_browser_headers()

    for attempt in range(2):  # 初次 + 1 次重试
        try:
            # 随机延迟 1-3 秒
            if attempt > 0:
                delay = random.uniform(1, 3)
                time.sleep(delay)

            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                return extract_text_from_html(resp.text)
            else:
                if attempt == 1:
                    return None
        except (requests.Timeout, requests.ConnectionError, requests.RequestException):
            if attempt == 1:
                return None
            time.sleep(2)  # 重试前等待

    return None
```

- [ ] **步骤 4：运行测试验证通过**

```bash
uv run pytest akshare-finance-news/scripts/tests/test_fetch.py -v
```
预期：全部 PASS (12 tests)

- [ ] **步骤 5：Commit**

```bash
git add akshare-finance-news/scripts/fetch_news.py akshare-finance-news/scripts/tests/test_fetch.py
git commit -m "feat: add content fetching module with anti-crawler measures and tests

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 5：数据源调用与流水线编排

**文件：**
- 修改：`akshare-finance-news/scripts/fetch_news.py`（添加 main 流水线）

- [ ] **步骤 1：编写 main 流水线**

在 `akshare-finance-news/scripts/fetch_news.py` 的 import 区域添加：

```python
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

# 抑制 akshare 和 requests 的警告日志
warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)
```

在文件末尾添加以下函数：

```python
# --- 数据源适配层 ---

def _fetch_cjzc_em() -> list[dict]:
    """获取东财财经早餐数据"""
    import akshare as ak
    df = ak.stock_info_cjzc_em()
    records = []
    for _, row in df.iterrows():
        records.append({
            "title": str(row.get("标题", "")),
            "time": str(row.get("发布时间", "")),
            "content": str(row.get("摘要", "")),  # 降级用摘要
            "url": str(row.get("链接", "")),
        })
    return records


def _fetch_global_em() -> list[dict]:
    """获取东财全球快讯数据"""
    import akshare as ak
    df = ak.stock_info_global_em()
    records = []
    for _, row in df.iterrows():
        records.append({
            "title": str(row.get("标题", "")),
            "time": str(row.get("发布时间", "")),
            "content": str(row.get("摘要", "")),
            "url": str(row.get("链接", "")),
        })
    return records


def _fetch_global_sina() -> list[dict]:
    """获取新浪财经快讯数据（无链接，内容已在返回中）"""
    import akshare as ak
    df = ak.stock_info_global_sina()
    records = []
    for _, row in df.iterrows():
        records.append({
            "title": str(row.get("内容", ""))[:50],  # 前 50 字作为标题
            "time": str(row.get("时间", "")),
            "content": str(row.get("内容", "")),
            "url": "",  # 新浪无链接
        })
    return records


def _fetch_global_ths() -> list[dict]:
    """获取同花顺财经直播数据"""
    import akshare as ak
    df = ak.stock_info_global_ths()
    records = []
    for _, row in df.iterrows():
        records.append({
            "title": str(row.get("标题", "")),
            "time": str(row.get("发布时间", "")),
            "content": str(row.get("内容", "")),
            "url": str(row.get("链接", "")),
        })
    return records


# 数据源注册表
_SOURCES = [
    ("stock_info_cjzc_em", _fetch_cjzc_em),
    ("stock_info_global_em", _fetch_global_em),
    ("stock_info_global_sina", _fetch_global_sina),
    ("stock_info_global_ths", _fetch_global_ths),
]


def _enrich_with_full_content(records: list[dict], semaphore_count: int = 5) -> tuple[list[dict], list[dict]]:
    """对带有 url 的记录并发抓取完整内容

    参数:
        records: 新闻记录列表
        semaphore_count: 最大并发数

    返回:
        (news, errors): 内容填充后的 news 列表和 errors 列表
    """
    from threading import Semaphore

    semaphore = Semaphore(semaphore_count)
    errors = []

    def fetch_one(record: dict) -> dict:
        url = record.get("url", "")
        if not url:
            # 新浪无链接，内容已在 API 返回中
            return record
        with semaphore:
            full_content = fetch_article_content(url)
        if full_content is not None:
            record["content"] = full_content
        else:
            # 降级：保留 API 返回的摘要作为 content
            errors.append({
                "title": record.get("title", ""),
                "error": "fetch_failed",
            })
        return record

    enriched = []
    with ThreadPoolExecutor(max_workers=semaphore_count) as executor:
        futures = {executor.submit(fetch_one, r): i for i, r in enumerate(records)}
        results = [None] * len(records)
        for future in as_completed(futures, timeout=600):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception:
                results[idx] = records[idx]
                errors.append({
                    "title": records[idx].get("title", ""),
                    "error": "thread_error",
                })

    enriched = [r for r in results if r is not None]
    return enriched, errors


def fetch_all_news() -> dict:
    """主流水线：并发获取 → 过滤 → 去重 → 抓取内容 → 输出

    返回:
        dict: 包含 news 和 errors 的结果字典
    """
    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    threshold = compute_time_threshold()

    # 1. 并发获取 4 个数据源
    all_records = []
    fetch_errors = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {
            executor.submit(func): name
            for name, func in _SOURCES
        }
        for future in as_completed(future_map, timeout=30):
            name = future_map[future]
            try:
                records = future.result()
                all_records.extend(records)
            except Exception as e:
                fetch_errors.append({
                    "title": name,
                    "error": f"api_error: {str(e)[:100]}",
                })

    # 2. 时间过滤
    filtered = filter_by_time(all_records, threshold)

    # 3. 去重
    deduped = deduplicate(filtered)

    # 4. 抓取完整内容（并发，最多 5 并发）
    enriched, fetch_errors_detail = _enrich_with_full_content(deduped)

    # 5. 清洗输出：移除非标准字段
    output_news = []
    for record in enriched:
        output_news.append({
            "title": record.get("title", ""),
            "time": record.get("time", ""),
            "content": record.get("content", ""),
        })

    all_errors = fetch_errors + fetch_errors_detail

    return {
        "fetch_time": fetch_time,
        "total_count": len(output_news),
        "news": output_news,
        "errors": all_errors,
    }


def main():
    """脚本入口：输出 JSON 到 stdout，日志到 stderr"""
    try:
        result = fetch_all_news()
    except Exception as e:
        logger.error("Fatal error: %s", e)
        json.dump({
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_count": 0,
            "news": [],
            "errors": [{"title": "fatal", "error": str(e)[:200]}],
        }, sys.stdout, ensure_ascii=False, indent=2)
        sys.exit(2)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)

    # 退出码
    if result["total_count"] == 0:
        sys.exit(2)
    elif result["errors"]:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **步骤 2：运行所有单元测试确保不破坏已有功能**

```bash
uv run pytest akshare-finance-news/scripts/tests/ -v --ignore=akshare-finance-news/scripts/tests/test_integration.py
```
预期：全部已有的 27 个单元测试 PASS

- [ ] **步骤 3：Commit**

```bash
git add akshare-finance-news/scripts/fetch_news.py
git commit -m "feat: add data source adapters and main pipeline orchestration

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 6：集成测试

**文件：**
- 创建：`akshare-finance-news/scripts/tests/test_integration.py`

- [ ] **步骤 1：编写集成测试**

在 `akshare-finance-news/scripts/tests/test_integration.py` 中：

```python
"""集成测试 — 需要真实网络，标记为 integration"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import json
import pytest
from fetch_news import fetch_all_news


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
        from fetch_news import is_similar_title
        for i in range(len(titles)):
            for j in range(i + 1, len(titles)):
                assert not is_similar_title(titles[i], titles[j]), \
                    f"发现重复标题: '{titles[i]}' 和 '{titles[j]}'"

    def test_all_news_within_time_range(self):
        """验证所有新闻都在时间范围内"""
        result = fetch_all_news()
        from fetch_news import compute_time_threshold, parse_time

        threshold = compute_time_threshold()
        for item in result["news"]:
            parsed = parse_time(item["time"])
            if parsed is not None:
                assert parsed >= threshold, \
                    f"新闻 '{item['title']}' 时间 {item['time']} 早于阈值 {threshold}"
```

- [ ] **步骤 2：运行集成测试确认网络调用正常**

```bash
uv run pytest akshare-finance-news/scripts/tests/test_integration.py -v -m integration
```
预期：5 tests PASS（如网络异常，部分可能 FAIL，需根据实际情况调整）

- [ ] **步骤 3：Commit**

```bash
git add akshare-finance-news/scripts/tests/test_integration.py
git commit -m "test: add integration tests for end-to-end validation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 7：运行完整测试套件并最终验证

- [ ] **步骤 1：运行所有单元测试**

```bash
uv run pytest akshare-finance-news/scripts/tests/ -v --ignore=akshare-finance-news/scripts/tests/test_integration.py
```
预期：全部单元测试 PASS

- [ ] **步骤 2：运行集成测试（如有网络）**

```bash
uv run pytest akshare-finance-news/scripts/tests/test_integration.py -v -m integration
```

- [ ] **步骤 3：手动执行脚本验证 JSON 输出有效性**

```bash
uv run python akshare-finance-news/scripts/fetch_news.py 2>/dev/null | python3 -m json.tool > /dev/null && echo "JSON valid"
```
预期：`JSON valid`

- [ ] **步骤 4：查看一条完整输出确认格式正确**

```bash
uv run python akshare-finance-news/scripts/fetch_news.py 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps({'fetch_time':d['fetch_time'],'total_count':d['total_count'],'news_sample':d['news'][0] if d['news'] else None,'errors':d['errors']}, ensure_ascii=False, indent=2))"
```

- [ ] **步骤 5：最终 Commit**

```bash
git add -A
git commit -m "chore: finalize akshare-finance-news implementation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 总结

| 任务 | 内容 | 文件数 |
|------|------|--------|
| 任务 1 | 目录结构与 SKILL.md | 3 |
| 任务 2 | 时间过滤模块 (TDD) | 2 |
| 任务 3 | 去重模块 (TDD) | 2 |
| 任务 4 | 内容抓取模块 (TDD) | 2 |
| 任务 5 | 数据源适配与流水线 | 1 |
| 任务 6 | 集成测试 | 1 |
| 任务 7 | 最终验证 | — |

**最终文件结构：**
```
akshare-finance-news/
  SKILL.md
  scripts/
    __init__.py
    fetch_news.py
    tests/
      __init__.py
      test_filter.py
      test_dedup.py
      test_fetch.py
      test_integration.py
```

**运行方式：**
```bash
# 安装依赖
uv pip install akshare requests beautifulsoup4

# 执行脚本
uv run python akshare-finance-news/scripts/fetch_news.py

# 运行测试
uv run pytest akshare-finance-news/scripts/tests/ -v
```
