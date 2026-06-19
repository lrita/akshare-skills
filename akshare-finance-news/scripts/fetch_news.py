#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
财经快讯数据获取脚本
从 4 个数据源获取财经新闻，过滤、去重、抓取内容，输出结构化 JSON
"""
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import sys
import requests
from bs4 import BeautifulSoup
import time
import random
import json
import logging
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

# 抑制 akshare 和 requests 的警告日志
warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def compute_time_threshold(now: datetime | None = None) -> datetime:
    """计算时间阈值，根据星期自动确定起始时间

    - 周一: 返回上周五 15:00:00（覆盖整个周末的新闻）
    - 周二至周日: 返回昨日 15:00:00

    参数:
        now: 可选，用于测试的当前时间；默认 datetime.now()

    返回:
        datetime: 时间过滤阈值
    """
    if now is None:
        now = datetime.now()

    if now.weekday() == 0:  # Monday
        # 回到上周五
        days_back = 3
    else:
        days_back = 1

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    threshold_day = today - timedelta(days=days_back)
    return threshold_day.replace(hour=15, minute=0, second=0)


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


def is_similar_title(title1: str, title2: str, threshold: float = 0.70) -> bool:
    """判断两个标题是否相似 (基于 SequenceMatcher 与子序列检查)

    参数:
        title1: 第一个标题
        title2: 第二个标题
        threshold: 相似度阈值，默认 0.70

    返回:
        bool: 相似则为 True
    """
    if not title1 or not title2:
        return False
    # 极短标题(少于3字符)不参与相似度判断
    if len(title1) < 3 or len(title2) < 3:
        return False

    shorter = title1 if len(title1) <= len(title2) else title2
    longer = title2 if len(title1) <= len(title2) else title1

    # 较短标题是较长标题的子序列（字符按顺序出现）
    it = iter(longer)
    if all(c in it for c in shorter):
        return True

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
