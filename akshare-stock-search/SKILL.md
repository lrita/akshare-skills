---
name: akshare-stock-search
description: Use when the user needs to search for A-stock or HK-stock by code, name, keyword, or pinyin initials. Provides fast local SQLite-cached lookup with exact/prefix/fuzzy/pinyin matching. Use this before fetching any stock data that requires a stock code.
---

# 股票搜索

## 概述

通过代码、名称、关键词或拼音首字母搜索 A 股（沪深京）和港股，基于本地 SQLite 缓存实现毫秒级响应。缓存自动过期刷新（默认 7 天 TTL）。

## 使用方式

```bash
# 搜索股票
uv run python scripts/search_stock.py search 平安
uv run python scripts/search_stock.py search 000001 --market zh_a
uv run python scripts/search_stock.py search pabx --market zh_a

# 手动刷新缓存
uv run python scripts/search_stock.py refresh
uv run python scripts/search_stock.py refresh --force
```

## 参数说明

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `search <keyword>` | 是 | - | 搜索关键词 |
| `--market zh_a\|hk` | 否 | 全部 | 限定市场 |
| `--limit N` | 否 | 20 | 最大返回条数 |
| `--output path` | 否 | stdout | 输出 JSON 文件路径 |
| `refresh` | - | - | 增量刷新缓存 |
| `refresh --force` | - | - | 强制全量刷新 |

## 输出格式

JSON 数组到 stdout，按匹配优先级 + 市场 + 代码排序：

```json
[
  {"market": "zh_a", "code": "000001", "name": "平安银行", "match_type": "exact"},
  {"market": "zh_a", "code": "000002", "name": "万科A",   "match_type": "fuzzy"}
]
```

match_type: exact > prefix > fuzzy > pinyin

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AKSHARE_SKILL_CACHE_DIR` | `~/.cache/akshare-skill` | 缓存目录 |
| `AKSHARE_STOCK_CACHE_TTL_DAYS` | `7` | 缓存有效期（天） |

## 退出码

| code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 数据源全部失败 |
| 2 | 参数非法 |

## 依赖

```bash
uv pip install akshare pypinyin
```

pypinyin 为推荐依赖，未安装时拼音搜索自动跳过。
