---
name: akshare-fund-holdings
description: Use when the user needs to analyze fund "herding" by calculating the TopN stocks with the highest aggregated holding value across equity and mixed-type mutual funds. Supports configurable fund scale threshold and top-N count.
---

# 基金抱团 TopN 股票分析

## 概述

基于 akshare 新浪财经公募基金数据，拉取股票型和混合型基金的前十大持仓，按股票聚合计算各基金持仓市值的总和，输出持仓最集中的 TopN 股票及其近 4 个季度趋势，供 AI 分析基金抱团方向。

## 使用方式

```bash
# 默认参数：min_scale=10亿, Top100
uv run python scripts/fund_holdings.py

# 自定义 TopN 和规模门槛
uv run python scripts/fund_holdings.py --top-n 50 --min-scale 20.0

# 仅股票型基金
uv run python scripts/fund_holdings.py --fund-types 股票型基金

# 调整并发数
uv run python scripts/fund_holdings.py --workers 4
```

JSON 输出到 stdout，运行进度和错误日志到 stderr。

## 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--top-n` | 100 | 返回 TopN 股票 |
| `--min-scale` | 10.0 | 最低总募集规模（亿元） |
| `--fund-types` | 股票型基金,混合型基金 | 基金类型，逗号分隔 |
| `--workers` | 8 | 并发 worker 数 |

## 输出格式

```json
{
  "meta": {
    "fetch_time": "2026-06-20 15:30:00",
    "fund_types": ["股票型基金", "混合型基金"],
    "min_scale_yi": 10.0,
    "total_funds_fetched": 3580,
    "success_funds": 3421,
    "failed_funds": 159,
    "quarters": ["2026Q1", "2025Q4", "2025Q3", "2025Q2"],
    "top_n": 100,
    "actual_top_n": 100
  },
  "top_stocks": [
    {
      "rank": 1,
      "stock_code": "600519",
      "stock_name": "贵州茅台",
      "total_holding_amount": 125800000000,
      "fund_count": 892,
      "quarterly_trend": [
        {"quarter": "2025Q2", "amount": 28100000000, "fund_count": 750},
        {"quarter": "2025Q3", "amount": 29500000000, "fund_count": 780},
        {"quarter": "2025Q4", "amount": 31200000000, "fund_count": 810},
        {"quarter": "2026Q1", "amount": 37000000000, "fund_count": 892}
      ]
    }
  ],
  "errors": [
    {"fund_code": "001234", "error": "timeout"}
  ]
}
```

- 金额单位：万元
- `quarterly_trend` 按季度升序排列
- 缓存目录：`~/.cache/akshare-fund-holdings/`

## 缓存策略

脚本始终使用缓存，按以下策略自动判断有效性：

| 缓存 | 路径 | 过期策略 |
|---|---|---|
| 基金列表 | `fund_list.json` | 7 天 |
| 持仓数据 | `holdings/{基金代码}.json` | 季度智能过期（缺少最新季度则重新拉取） |
| 失败记录 | `failures.json` | 持久保留，每次运行自动重试 |

## 依赖

```bash
uv pip install akshare pandas
```
