---
name: akshare-open-fund-rank
description: Use when the user needs to fetch open-end fund rankings from East Money — lookup net values, returns across multiple periods (1w/1m/3m/6m/1y/2y/3y/YTD/since inception), filter by numeric conditions, sort by any return metric, and get top-N performers. Supports filtering by fund type (equity, hybrid, bond, index, QDII, FOF).
---

# 开放基金排行

## 概述

调用东方财富开放基金排行 API (`akshare.fund_open_fund_rank_em`)，获取全量基金净值及多周期涨幅数据。支持按基金类型筛选、按多列数值过滤（AND 关系）、按任意指标排序、取 Top N 结果，以 JSON 或 JSONL 格式输出。

数据来源：https://fund.eastmoney.com/data/fundranking.html

## 使用方式

```bash
uv run python scripts/open_fund_rank.py [options]
```

所有输出写入 stdout，日志/错误信息写入 stderr。exit code: 0 成功, 1 无数据/过滤后为空, 2 参数错误/API 不可用。

## 参数说明

### `--symbol` (可选，默认 `全部`)

基金类型。合法值：`全部`, `股票型`, `混合型`, `债券型`, `指数型`, `QDII`, `FOF`。

### `--filter` (可选，可重复，默认无)

数值过滤条件。格式：`<列名><运算符><数值>`。可多次指定，条件之间为 AND 关系。

运算符：`>`（大于）、`>=`（大于等于）、`<`（小于）、`<=`（小于等于）、`=`（等于）。

示例：
```bash
--filter 近1月>10
--filter 近1月>10 --filter 近1年>30 --filter 单位净值<=5
```

过滤列的合法值与 `--sort-by` 完全一致。NaN 值不满足任何过滤条件，自动排除。

### `--sort-by` (可选，默认 `近1年`)

排序字段。合法值及单位：

| 值 | 单位 | 说明 |
|---|---|---|
| `日增长率` | % | 日涨跌幅 |
| `近1周` | % | 近 1 周涨跌幅 |
| `近1月` | % | 近 1 月涨跌幅 |
| `近3月` | % | 近 3 月涨跌幅 |
| `近6月` | % | 近 6 月涨跌幅 |
| `近1年` | % | 近 1 年涨跌幅 |
| `近2年` | % | 近 2 年涨跌幅 |
| `近3年` | % | 近 3 年涨跌幅 |
| `今年来` | % | 今年以来涨跌幅 |
| `成立来` | % | 成立以来涨跌幅 |
| `单位净值` | 元 | 单位净值 |
| `累计净值` | 元 | 累计净值 |

### `--order` (可选，默认 `desc`)

排序方向。合法值：`desc`（降序）, `asc`（升序）。

### `--top-n` (可选，默认无限制)

输出前 N 条记录，须为正整数。不指定则输出全部。

### `--output` (可选，默认 `jsonl`)

输出格式。合法值：`jsonl`（每行一个 JSON 对象）, `json`（JSON 数组）。

## 输出格式

共 16 个字段：

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `fund_code` | string | - | 基金代码 |
| `fund_name` | string | - | 基金简称 |
| `date` | string | - | 净值日期 (YYYY-MM-DD) |
| `unit_net_value` | float/null | 元 | 单位净值 |
| `cumulative_net_value` | float/null | 元 | 累计净值 |
| `daily_return` | float/null | % | 日增长率 |
| `1w_return` | float/null | % | 近 1 周涨幅 |
| `1m_return` | float/null | % | 近 1 月涨幅 |
| `3m_return` | float/null | % | 近 3 月涨幅 |
| `6m_return` | float/null | % | 近 6 月涨幅 |
| `1y_return` | float/null | % | 近 1 年涨幅 |
| `2y_return` | float/null | % | 近 2 年涨幅 |
| `3y_return` | float/null | % | 近 3 年涨幅 |
| `ytd_return` | float/null | % | 今年以来涨幅 |
| `since_inception_return` | float/null | % | 成立来涨幅 |
| `fee` | string | - | 手续费 |

NaN 值输出为 `null`。

### jsonl 输出示例（默认）

```json
{"fund_code":"014915","fund_name":"财通匠心优选一年持有混合A","date":"2026-06-18","unit_net_value":4.0954,"cumulative_net_value":4.0954,"daily_return":2.83,"1w_return":23.34,"1m_return":67.32,"3m_return":145.88,"6m_return":173.96,"1y_return":473.75,"2y_return":431.94,"3y_return":394.97,"ytd_return":163.10,"since_inception_return":309.54,"fee":"0.15%"}
```

### json 输出示例

```json
[
  {"fund_code":"014915","fund_name":"财通匠心优选一年持有混合A", ...}
]
```

## 缓存策略

无缓存，每次实时查询，保证数据最新。

## 依赖

```bash
uv pip install akshare pandas
```

## 使用示例

```bash
# 获取近 1 年涨幅最高的前 20 只基金
uv run python scripts/open_fund_rank.py --top-n 20

# 获取股票型基金，按近 3 月涨幅排序，取前 10
uv run python scripts/open_fund_rank.py --symbol 股票型 --sort-by 近3月 --top-n 10

# 获取债券型基金，按单位净值升序排列
uv run python scripts/open_fund_rank.py --symbol 债券型 --sort-by 单位净值 --order asc

# 筛选近1月>10%且近1年>30%的基金，按近1年降序，取前20
uv run python scripts/open_fund_rank.py --filter 近1月>10 --filter 近1年>30 --top-n 20

# 筛选单位净值<=5的股票型基金，按日增长率降序
uv run python scripts/open_fund_rank.py --symbol 股票型 --filter 单位净值<=5 --sort-by 日增长率

# 输出 JSON 数组格式
uv run python scripts/open_fund_rank.py --symbol QDII --output json
```
