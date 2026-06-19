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
