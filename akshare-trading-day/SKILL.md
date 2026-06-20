---
name: akshare-trading-day
description: Use when the user needs to check if a specific date is an A-stock trading day, find the next trading day, or count trading days in a date range. Based on Sina finance trading calendar data.
---

# A股交易日判断

## 概述

基于新浪财经交易日历数据（通过 akshare `tool_trade_date_hist_sina`），提供交易日相关查询。

## 使用方式

```bash
# 判断是否为交易日
uv run python scripts/trading_day.py check 2026-06-22

# 查询下一个交易日（含当日）
uv run python scripts/trading_day.py next 2026-06-20

# 统计范围内交易日数量（含起止日）
uv run python scripts/trading_day.py count 2026-06-01 2026-06-30
```

## 输出格式

所有命令输出 JSON 到 stdout，错误信息到 stderr。

### check
```json
{"is_trading_day": true}
```

### next
```json
{"next_trading_day": "2026-06-22"}
```

### count
```json
{"count": 20}
```

## 依赖

```bash
uv pip install akshare
```
