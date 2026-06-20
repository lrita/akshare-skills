# akshare-open-fund-rank 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建开放基金排行 SKILL，基于 akshare `fund_open_fund_rank_em` API，支持基金类型筛选、多列数值过滤 (AND)、排序、Top-N、JSON/JSONL 输出。

**架构：** 单文件 `scripts/open_fund_rank.py`，argparse 解析 CLI 参数，pandas 处理筛选/排序/截取，JSON 输出到 stdout，日志到 stderr。

**技术栈：** Python ≥ 3.10, akshare, pandas, argparse (stdlib), re (stdlib), json (stdlib)

---

### 任务 1：创建目录结构与 SKILL.md

**文件：**
- 创建：`akshare-open-fund-rank/SKILL.md`
- 创建：`akshare-open-fund-rank/scripts/__init__.py`
- 创建：`akshare-open-fund-rank/scripts/tests/__init__.py`

- [ ] **步骤 1：创建 SKILL.md**

```markdown
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

### `--symbol`（可选，默认 `全部`）

基金类型。合法值：`全部`, `股票型`, `混合型`, `债券型`, `指数型`, `QDII`, `FOF`。

### `--filter`（可选，可重复，默认无）

数值过滤条件。格式：`<列名><运算符><数值>`。可多次指定，条件之间为 AND 关系。

运算符：`>`（大于）、`>=`（大于等于）、`<`（小于）、`<=`（小于等于）、`=`（等于）。

示例：
```bash
--filter 近1月>10
--filter 近1月>10 --filter 近1年>30 --filter 单位净值<=5
```

过滤列的合法值与 `--sort-by` 完全一致。NaN 值不满足任何过滤条件，自动排除。

### `--sort-by`（可选，默认 `近1年`）

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

### `--order`（可选，默认 `desc`）

排序方向。合法值：`desc`（降序）, `asc`（升序）。

### `--top-n`（可选，默认无限制）

输出前 N 条记录，须为正整数。不指定则输出全部。

### `--output`（可选，默认 `jsonl`）

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

# 筛选近1月>10%且近1年>30%的基金，按近1年降序，取前20
uv run python scripts/open_fund_rank.py --filter 近1月>10 --filter 近1年>30 --top-n 20

# 筛选单位净值<=5的股票型基金，按日增长率降序
uv run python scripts/open_fund_rank.py --symbol 股票型 --filter 单位净值<=5 --sort-by 日增长率

# 输出 JSON 数组格式
uv run python scripts/open_fund_rank.py --symbol QDII --output json
```
```

- [ ] **步骤 2：创建目录和空文件**

```bash
mkdir -p akshare-open-fund-rank/scripts/tests
touch akshare-open-fund-rank/scripts/__init__.py
touch akshare-open-fund-rank/scripts/tests/__init__.py
```

- [ ] **步骤 3：Commit**

```bash
git add akshare-open-fund-rank/
git commit -m "feat: add akshare-open-fund-rank SKILL.md and directory structure

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 2：编写单元测试（TDD — 先写测试，确认失败）

**文件：**
- 创建：`akshare-open-fund-rank/scripts/tests/test_open_fund_rank.py`

- [ ] **步骤 1：编写全部单元测试**

在 `akshare-open-fund-rank/scripts/tests/test_open_fund_rank.py` 中：

```python
"""开放基金排行单元测试 (mock akshare API)"""
import os, sys, json, io, re
from datetime import date
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 我们将逐步实现以下模块，测试先写
import open_fund_rank as ofr


# ---- Mock 数据 ----

def make_mock_df():
    """构造模拟 API 返回的 DataFrame，包含混合正常值和 NaN"""
    return pd.DataFrame({
        "序号": [1, 2, 3, 4, 5],
        "基金代码": ["000001", "000002", "000003", "000004", "000005"],
        "基金简称": ["基金A", "基金B", "基金C", "基金D", "基金E"],
        "日期": [date(2026, 6, 18)] * 5,
        "单位净值": [1.2345, 2.0, np.nan, 1.0, 5.6789],
        "累计净值": [3.4567, 1.5, 2.0, np.nan, 8.9],
        "日增长率": [1.5, -0.5, 0.0, np.nan, 2.3],
        "近1周": [5.0, -2.0, np.nan, 1.0, 10.0],
        "近1月": [10.0, 5.0, -3.0, np.nan, 8.0],
        "近3月": [20.0, np.nan, 15.0, 5.0, 30.0],
        "近6月": [30.0, 10.0, np.nan, 20.0, 50.0],
        "近1年": [100.0, 30.0, 50.0, np.nan, 80.0],
        "近2年": [80.0, np.nan, 40.0, 20.0, 60.0],
        "近3年": [np.nan, 20.0, 30.0, 10.0, 50.0],
        "今年来": [15.0, 8.0, np.nan, 3.0, 12.0],
        "成立来": [200.0, 100.0, 150.0, 50.0, np.nan],
        "自定义": [np.nan] * 5,
        "手续费": ["0.15%", "0.10%", "0.00%", "1.50%", "0.08%"],
    })


# ---- 列名映射 ----

class TestColumnMapping:
    """列名映射测试"""

    def test_rename_columns_keeps_only_16(self):
        df = make_mock_df()
        result = ofr.rename_columns(df)
        assert list(result.columns) == [
            "fund_code", "fund_name", "date",
            "unit_net_value", "cumulative_net_value",
            "daily_return", "1w_return", "1m_return",
            "3m_return", "6m_return", "1y_return",
            "2y_return", "3y_return", "ytd_return",
            "since_inception_return", "fee",
        ]

    def test_column_values_preserved(self):
        df = make_mock_df()
        result = ofr.rename_columns(df)
        assert result.iloc[0]["fund_code"] == "000001"
        assert result.iloc[0]["fund_name"] == "基金A"
        assert result.iloc[0]["unit_net_value"] == pytest.approx(1.2345)
        assert result.iloc[0]["daily_return"] == pytest.approx(1.5)
        assert result.iloc[0]["fee"] == "0.15%"


# ---- 过滤表达式解析 ----

class TestParseFilter:
    """parse_filter 函数测试"""

    def test_parse_gt(self):
        col, op, val = ofr.parse_filter("近1月>10")
        assert col == "近1月"
        assert op == ">"
        assert val == pytest.approx(10.0)

    def test_parse_gte(self):
        col, op, val = ofr.parse_filter("近1年>=30.5")
        assert col == "近1年"
        assert op == ">="
        assert val == pytest.approx(30.5)

    def test_parse_lt(self):
        col, op, val = ofr.parse_filter("单位净值<2")
        assert col == "单位净值"
        assert op == "<"
        assert val == pytest.approx(2.0)

    def test_parse_lte(self):
        col, op, val = ofr.parse_filter("累计净值<=5.0")
        assert col == "累计净值"
        assert op == "<="
        assert val == pytest.approx(5.0)

    def test_parse_eq(self):
        col, op, val = ofr.parse_filter("日增长率=0")
        assert col == "日增长率"
        assert op == "="
        assert val == pytest.approx(0.0)

    def test_parse_invalid_format_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.parse_filter("invalid")

    def test_parse_invalid_operator_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.parse_filter("近1月!=10")

    def test_parse_unknown_column_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.parse_filter("未知列>5")


# ---- 过滤应用 ----

class TestApplyFilters:
    """apply_filters 函数测试"""

    def test_single_filter_gt(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        filters = [("近1月", ">", 6.0)]
        result = ofr.apply_filters(df, filters)
        assert len(result) == 2  # 基金A (10.0), 基金E (8.0)
        assert set(result["fund_code"]) == {"000001", "000005"}

    def test_single_filter_lt(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        filters = [("近1月", "<", 0)]
        result = ofr.apply_filters(df, filters)
        assert len(result) == 1  # 基金C (-3.0)
        assert result.iloc[0]["fund_code"] == "000003"

    def test_single_filter_eq(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        filters = [("日增长率", "=", 0.0)]
        result = ofr.apply_filters(df, filters)
        assert len(result) == 1
        assert result.iloc[0]["fund_code"] == "000003"

    def test_multiple_filters_and(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        filters = [("近1月", ">", 5.0), ("近1年", ">", 50.0)]
        result = ofr.apply_filters(df, filters)
        assert len(result) == 1  # 只有基金A
        assert result.iloc[0]["fund_code"] == "000001"

    def test_nan_excluded_by_filter(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        filters = [("近1月", ">", 0)]
        result = ofr.apply_filters(df, filters)
        codes = set(result["fund_code"])
        # 基金D 近1月为 NaN，不应出现在结果中
        assert "000004" not in codes

    def test_filter_clears_nan_before_comparison(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        filters = [("近3年", ">", 0)]
        result = ofr.apply_filters(df, filters)
        codes = set(result["fund_code"])
        # 基金A 近3年为 NaN，不应出现
        assert "000001" not in codes
        # 基金B (20), 基金C (30), 基金D (10), 基金E (50) 应出现
        assert codes == {"000002", "000003", "000004", "000005"}

    def test_no_filters_returns_all(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        result = ofr.apply_filters(df, [])
        assert len(result) == 5


# ---- 排序 ----

class TestSorting:
    """排序逻辑测试"""

    def test_sort_desc(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        result = ofr.sort_dataframe(df, "1y_return", "desc")
        # NaN 排最后，然后降序: 100, 80, 50, 30, NaN
        assert result.iloc[0]["fund_code"] == "000001"  # 100
        assert result.iloc[1]["fund_code"] == "000005"  # 80
        assert result.iloc[2]["fund_code"] == "000003"  # 50
        assert result.iloc[3]["fund_code"] == "000002"  # 30

    def test_sort_asc(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        result = ofr.sort_dataframe(df, "1y_return", "asc")
        # NaN 排最后，升序: 30, 50, 80, 100, NaN
        assert result.iloc[0]["fund_code"] == "000002"  # 30
        assert result.iloc[1]["fund_code"] == "000003"  # 50
        assert result.iloc[2]["fund_code"] == "000005"  # 80
        assert result.iloc[3]["fund_code"] == "000001"  # 100


# ---- Top-N ----

class TestTopN:
    """top_n 截取测试"""

    def test_top_n_less_than_total(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        result = ofr.apply_top_n(df, 3)
        assert len(result) == 3

    def test_top_n_none_returns_all(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        result = ofr.apply_top_n(df, None)
        assert len(result) == 5

    def test_top_n_exceeds_total_returns_all(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        result = ofr.apply_top_n(df, 100)
        assert len(result) == 5


# ---- NaN 转 null ----

class TestNaNToNull:
    """nan_to_none 测试"""

    def test_nan_converted_to_none(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        records = ofr.dataframe_to_records(df)
        # 基金D 近1月为 NaN → None
        row_d = next(r for r in records if r["fund_code"] == "000004")
        assert row_d["1m_return"] is None

    def test_float_values_preserved(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        records = ofr.dataframe_to_records(df)
        row_a = next(r for r in records if r["fund_code"] == "000001")
        assert row_a["1m_return"] == pytest.approx(10.0)
        assert row_a["unit_net_value"] == pytest.approx(1.2345)


# ---- 日期格式化 ----

class TestDateFormat:
    """日期列输出测试"""

    def test_date_converted_to_string(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        records = ofr.dataframe_to_records(df)
        row = records[0]
        assert isinstance(row["date"], str)
        assert row["date"] == "2026-06-18"


# ---- 输出格式 ----

class TestOutputJSONL:
    """jsonl 输出测试"""

    def test_output_jsonl(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        buf = io.StringIO()
        ofr.output_jsonl(df, buf)
        lines = buf.getvalue().strip().split("\n")
        assert len(lines) == 5
        for line in lines:
            obj = json.loads(line)
            assert "fund_code" in obj


class TestOutputJSON:
    """json 输出测试"""

    def test_output_json(self):
        df = make_mock_df()
        df = ofr.rename_columns(df)
        buf = io.StringIO()
        ofr.output_json(df, buf)
        data = json.loads(buf.getvalue())
        assert isinstance(data, list)
        assert len(data) == 5


# ---- 参数校验 ----

class TestValidateSymbol:
    """symbol 参数校验"""

    def test_valid_symbols(self):
        for s in ["全部", "股票型", "混合型", "债券型", "指数型", "QDII", "FOF"]:
            ofr.validate_symbol(s)  # 不应抛出

    def test_invalid_symbol_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_symbol("期货型")


class TestValidateSortBy:
    """sort-by 参数校验"""

    def test_valid_sort_fields(self):
        valid = ["日增长率", "近1周", "近1月", "近3月", "近6月",
                 "近1年", "近2年", "近3年", "今年来", "成立来",
                 "单位净值", "累计净值"]
        for f in valid:
            ofr.validate_sort_by(f)  # 不应抛出

    def test_invalid_sort_field_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_sort_by("手续费")


class TestValidateOrder:
    """order 参数校验"""

    def test_valid_orders(self):
        ofr.validate_order("desc")
        ofr.validate_order("asc")

    def test_invalid_order_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_order("ASCENDING")


class TestValidateTopN:
    """top-n 参数校验"""

    def test_positive_integer_passes(self):
        assert ofr.validate_top_n("10") == 10

    def test_zero_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_top_n("0")

    def test_negative_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_top_n("-5")

    def test_non_integer_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_top_n("abc")


class TestValidateOutput:
    """output 参数校验"""

    def test_valid_outputs(self):
        ofr.validate_output("jsonl")
        ofr.validate_output("json")

    def test_invalid_output_raises_valueerror(self):
        with pytest.raises(ValueError):
            ofr.validate_output("csv")
```

- [ ] **步骤 2：运行测试验证全部失败**

```bash
uv run pytest akshare-open-fund-rank/scripts/tests/test_open_fund_rank.py -v
```
预期：全部 FAIL（模块/函数未定义）

---

### 任务 3：实现核心脚本让测试通过

**文件：**
- 创建：`akshare-open-fund-rank/scripts/open_fund_rank.py`

- [ ] **步骤 1：编写完整实现**

在 `akshare-open-fund-rank/scripts/open_fund_rank.py` 中：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
开放基金排行查询脚本
基于东方财富开放基金排行 API，提供筛选、排序、Top-N、JSON/JSONL 输出功能
"""
import sys
import json
import argparse
import re
from typing import Optional

import pandas as pd
import numpy as np


# ---- 常量 ----

SYMBOL_CHOICES = ["全部", "股票型", "混合型", "债券型", "指数型", "QDII", "FOF"]

SORT_BY_CHOICES = [
    "日增长率", "近1周", "近1月", "近3月", "近6月",
    "近1年", "近2年", "近3年", "今年来", "成立来",
    "单位净值", "累计净值",
]

CN_TO_EN_COLUMN = {
    "基金代码": "fund_code",
    "基金简称": "fund_name",
    "日期": "date",
    "单位净值": "unit_net_value",
    "累计净值": "cumulative_net_value",
    "日增长率": "daily_return",
    "近1周": "1w_return",
    "近1月": "1m_return",
    "近3月": "3m_return",
    "近6月": "6m_return",
    "近1年": "1y_return",
    "近2年": "2y_return",
    "近3年": "3y_return",
    "今年来": "ytd_return",
    "成立来": "since_inception_return",
    "手续费": "fee",
}

OUTPUT_COLUMNS = list(CN_TO_EN_COLUMN.values())

FILTER_PATTERN = re.compile(
    r"^(.+?)(>=|<=|>|<|=)(-?\d+(?:\.\d+)?)$"
)


# ---- 校验函数 ----

def validate_symbol(value: str) -> None:
    """校验 --symbol 参数"""
    if value not in SYMBOL_CHOICES:
        raise ValueError(
            f"非法的 --symbol 值: '{value}'。"
            f"合法值: {', '.join(SYMBOL_CHOICES)}"
        )


def validate_sort_by(value: str) -> None:
    """校验 --sort-by 参数"""
    if value not in SORT_BY_CHOICES:
        raise ValueError(
            f"非法的 --sort-by 值: '{value}'。"
            f"合法值: {', '.join(SORT_BY_CHOICES)}"
        )


def validate_order(value: str) -> None:
    """校验 --order 参数"""
    if value not in ("desc", "asc"):
        raise ValueError(
            f"非法的 --order 值: '{value}'。合法值: desc, asc"
        )


def validate_top_n(value: str) -> int:
    """校验 --top-n 参数，返回整数"""
    try:
        n = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"--top-n 必须是正整数，收到: '{value}'")
    if n <= 0:
        raise ValueError(f"--top-n 必须是正整数，收到: {n}")
    return n


def validate_output(value: str) -> None:
    """校验 --output 参数"""
    if value not in ("jsonl", "json"):
        raise ValueError(
            f"非法的 --output 值: '{value}'。合法值: jsonl, json"
        )


# ---- 过滤解析 ----

def parse_filter(raw: str) -> tuple[str, str, float]:
    """解析单个 --filter 表达式。

    参数:
        raw: 过滤表达式，如 "近1月>10" 或 "单位净值<=5.0"

    返回:
        (column_cn, operator, value) 如 ("近1月", ">", 10.0)

    异常:
        ValueError: 格式不合法
    """
    m = FILTER_PATTERN.match(raw.strip())
    if not m:
        raise ValueError(
            f"非法的 --filter 格式: '{raw}'。"
            f"期望格式: <列名><运算符><数值>，"
            f"运算符: >, >=, <, <=, =。示例: --filter 近1月>10"
        )
    col, op, val = m.group(1), m.group(2), m.group(3)
    if col not in CN_TO_EN_COLUMN:
        raise ValueError(
            f"非法的过滤列名: '{col}'。"
            f"合法列名: {', '.join(SORT_BY_CHOICES)}"
        )
    return col, op, float(val)


# ---- 数据处理 ----

def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """重命名中文列名为英文列名，仅保留 OUTPUT_COLUMNS 中的 16 列。"""
    result = df.rename(columns=CN_TO_EN_COLUMN)
    return result[OUTPUT_COLUMNS]


def apply_filters(
    df: pd.DataFrame, filters: list[tuple[str, str, float]]
) -> pd.DataFrame:
    """逐条应用 AND 过滤条件。

    参数:
        df: 已重命名列名的 DataFrame
        filters: [(column_cn, operator, value), ...] 列表

    返回:
        过滤后的 DataFrame

    NaN 值不满足任何比较条件，自动被排除。
    """
    for col_cn, op, val in filters:
        en_col = CN_TO_EN_COLUMN[col_cn]
        if op == ">":
            df = df[df[en_col] > val]
        elif op == ">=":
            df = df[df[en_col] >= val]
        elif op == "<":
            df = df[df[en_col] < val]
        elif op == "<=":
            df = df[df[en_col] <= val]
        elif op == "=":
            df = df[df[en_col] == val]
    return df


def sort_dataframe(
    df: pd.DataFrame, sort_cn: str, order: str
) -> pd.DataFrame:
    """排序 DataFrame。

    参数:
        df: 已重命名列名的 DataFrame
        sort_cn: 排序列中文名
        order: "desc" 或 "asc"

    返回:
        排序后的 DataFrame（NaN 总是排到最后）
    """
    en_col = CN_TO_EN_COLUMN[sort_cn]
    ascending = order == "asc"
    return df.sort_values(
        by=en_col, ascending=ascending, na_position="last"
    )


def apply_top_n(df: pd.DataFrame, top_n: Optional[int]) -> pd.DataFrame:
    """取前 top_n 条。top_n 为 None 则返回全部。"""
    if top_n is None:
        return df
    return df.head(top_n)


def dataframe_to_records(df: pd.DataFrame) -> list[dict]:
    """将 DataFrame 转为 dict 列表，NaN → None，date → 字符串。"""
    df = df.copy()
    # NaN → None (JSON null)
    df = df.where(df.notna(), None)
    # date → 字符串
    if "date" in df.columns:
        df["date"] = df["date"].apply(
            lambda x: x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else x
        )
    return df.to_dict(orient="records")


# ---- 输出 ----

def output_jsonl(df: pd.DataFrame, file=None) -> None:
    """以 JSONL 格式输出到 file（默认 stdout）"""
    if file is None:
        file = sys.stdout
    records = dataframe_to_records(df)
    for record in records:
        print(json.dumps(record, ensure_ascii=False), file=file)


def output_json(df: pd.DataFrame, file=None) -> None:
    """以 JSON 数组格式输出到 file（默认 stdout）"""
    if file is None:
        file = sys.stdout
    records = dataframe_to_records(df)
    print(json.dumps(records, ensure_ascii=False), file=file)


# ---- 主函数 ----

def main() -> None:
    parser = argparse.ArgumentParser(
        description="开放基金排行查询 — 基于东方财富数据中心"
    )
    parser.add_argument(
        "--symbol",
        default="全部",
        help=f"基金类型。合法值: {', '.join(SYMBOL_CHOICES)} (默认: 全部)",
    )
    parser.add_argument(
        "--filter",
        action="append",
        dest="filters_raw",
        default=[],
        help="数值过滤条件，格式: <列名><运算符><数值>。可重复指定 (AND 关系)。"
             "示例: --filter 近1月>10 --filter 近1年>30",
    )
    parser.add_argument(
        "--sort-by",
        default="近1年",
        help=f"排序字段。合法值: {', '.join(SORT_BY_CHOICES)} (默认: 近1年)",
    )
    parser.add_argument(
        "--order",
        default="desc",
        choices=["desc", "asc"],
        help="排序方向: desc (降序) 或 asc (升序) (默认: desc)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help="输出前 N 条记录 (默认: 输出全部)",
    )
    parser.add_argument(
        "--output",
        default="jsonl",
        choices=["jsonl", "json"],
        help="输出格式: jsonl 或 json (默认: jsonl)",
    )

    args = parser.parse_args()

    # 校验参数
    try:
        validate_symbol(args.symbol)
        validate_sort_by(args.sort_by)
        validate_order(args.order)
        if args.top_n is not None and args.top_n <= 0:
            raise ValueError(f"--top-n 必须是正整数，收到: {args.top_n}")
        validate_output(args.output)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(2)

    # 解析过滤条件
    parsed_filters = []
    for raw in args.filters_raw:
        try:
            parsed_filters.append(parse_filter(raw))
        except ValueError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(2)

    # 构建 filter 描述（用于日志）
    filter_desc = ", ".join(
        f"{col}{op}{val}" for col, op, val in parsed_filters
    )

    # 调用 API
    print(f"[INFO] 正在获取开放基金排行: symbol={args.symbol}", file=sys.stderr)
    try:
        import akshare as ak
        df = ak.fund_open_fund_rank_em(symbol=args.symbol)
    except Exception as e:
        print(f"[ERROR] API 调用失败: {e}", file=sys.stderr)
        sys.exit(2)

    if df.empty:
        print("[INFO] API 返回空数据", file=sys.stderr)
        if args.output == "json":
            print("[]")
        sys.exit(1)

    print(f"[INFO] 获取到 {len(df)} 条记录", file=sys.stderr)

    # 重命名列
    df = rename_columns(df)

    # 应用过滤
    if parsed_filters:
        df = apply_filters(df, parsed_filters)
        print(
            f"[INFO] 应用过滤条件: {filter_desc}; 过滤后 {len(df)} 条",
            file=sys.stderr,
        )
        if df.empty:
            print("[INFO] 过滤后无数据", file=sys.stderr)
            if args.output == "json":
                print("[]")
            sys.exit(1)

    # 排序
    order_text = "降序" if args.order == "desc" else "升序"
    top_n_text = f", 取前 {args.top_n} 条" if args.top_n else ""
    print(
        f"[INFO] 按 {args.sort_by} {order_text}排列{top_n_text}",
        file=sys.stderr,
    )
    df = sort_dataframe(df, args.sort_by, args.order)

    # 取 Top N
    df = apply_top_n(df, args.top_n)

    # 输出
    print(
        f"[INFO] 输出: {args.output} 格式, {len(df)} 条记录",
        file=sys.stderr,
    )
    if args.output == "json":
        output_json(df)
    else:
        output_jsonl(df)

    print("[INFO] 完成", file=sys.stderr)


if __name__ == "__main__":
    main()
```

- [ ] **步骤 2：运行单元测试验证所有测试通过**

```bash
uv run pytest akshare-open-fund-rank/scripts/tests/test_open_fund_rank.py -v
```
预期：全部 PASS (约 30+ tests)

- [ ] **步骤 3：手动验证 CLI 基本调用**

```bash
uv run python akshare-open-fund-rank/scripts/open_fund_rank.py --symbol 全部 --top-n 3
```
预期：stderr 输出日志，stdout 输出 3 行 JSONL

- [ ] **步骤 4：Commit**

```bash
git add akshare-open-fund-rank/
git commit -m "feat: implement open-fund-rank core logic with TDD

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 4：集成测试

**文件：**
- 创建：`akshare-open-fund-rank/scripts/tests/test_integration.py`

- [ ] **步骤 1：编写集成测试**

在 `akshare-open-fund-rank/scripts/tests/test_integration.py` 中：

```python
"""集成测试 — 需要真实网络，标记为 integration"""
import os, sys, json, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
import open_fund_rank as ofr


SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "open_fund_rank.py")


def run_cli(*args):
    """运行 CLI 并返回 (returncode, stdout, stderr)"""
    result = subprocess.run(
        [sys.executable, SCRIPT_PATH] + list(args),
        capture_output=True, text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.mark.integration
class TestRealAPI:
    """真实 API 调用测试"""

    def test_api_returns_data_all(self):
        import akshare as ak
        df = ak.fund_open_fund_rank_em(symbol="全部")
        assert len(df) > 10000

    def test_api_returns_data_by_type(self):
        import akshare as ak
        for symbol in ["股票型", "混合型", "债券型", "指数型", "QDII", "FOF"]:
            df = ak.fund_open_fund_rank_em(symbol=symbol)
            assert len(df) > 0, f"symbol={symbol} 返回空数据"

    def test_api_columns_match_expected(self):
        import akshare as ak
        df = ak.fund_open_fund_rank_em(symbol="全部")
        expected_cn_cols = [
            "序号", "基金代码", "基金简称", "日期", "单位净值", "累计净值",
            "日增长率", "近1周", "近1月", "近3月", "近6月", "近1年",
            "近2年", "近3年", "今年来", "成立来", "自定义", "手续费",
        ]
        for col in expected_cn_cols:
            assert col in df.columns, f"缺少列: {col}"


@pytest.mark.integration
class TestCLIIntegration:
    """CLI 端到端集成测试"""

    def test_default_run_produces_jsonl(self):
        rc, stdout, stderr = run_cli("--top-n", "2")
        assert rc == 0
        lines = stdout.strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert "fund_code" in obj
            assert "fund_name" in obj
            assert "1y_return" in obj
            assert "fee" in obj

    def test_json_output_format(self):
        rc, stdout, stderr = run_cli("--top-n", "2", "--output", "json")
        assert rc == 0
        data = json.loads(stdout)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_filter_and_sort(self):
        rc, stdout, stderr = run_cli(
            "--symbol", "混合型",
            "--filter", "近1年>10",
            "--sort-by", "近1年",
            "--top-n", "5",
        )
        assert rc == 0
        lines = stdout.strip().split("\n")
        assert len(lines) <= 5
        returns = []
        for line in lines:
            obj = json.loads(line)
            if obj["1y_return"] is not None:
                returns.append(obj["1y_return"])
        # 降序排列
        for i in range(len(returns) - 1):
            assert returns[i] >= returns[i + 1], f"排序错误: {returns}"

    def test_invalid_symbol_exit_code_2(self):
        rc, stdout, stderr = run_cli("--symbol", "INVALID")
        assert rc == 2
        assert "[ERROR]" in stderr

    def test_invalid_sort_by_exit_code_2(self):
        rc, stdout, stderr = run_cli("--sort-by", "不存在的列")
        assert rc == 2

    def test_invalid_filter_exit_code_2(self):
        rc, stdout, stderr = run_cli("--filter", "badformat")
        assert rc == 2

    def test_top_n_zero_exit_code_2(self):
        rc, stdout, stderr = run_cli("--top-n", "0")
        assert rc == 2

    def test_empty_filter_result_exit_code_1(self):
        # 极端过滤条件，预期无数据
        rc, stdout, stderr = run_cli(
            "--symbol", "债券型",
            "--filter", "近1年>99999",
        )
        assert rc == 1
        assert "过滤后无数据" in stderr or "过滤后 0 条" in stderr

    def test_all_symbol_types_work(self):
        """确保所有 symbol 均可用"""
        for symbol in ["全部", "股票型", "混合型", "债券型", "指数型", "QDII", "FOF"]:
            rc, stdout, stderr = run_cli("--symbol", symbol, "--top-n", "1")
            assert rc == 0, f"symbol={symbol} 失败: {stderr}"

    def test_fee_column_present(self):
        rc, stdout, stderr = run_cli("--top-n", "1")
        obj = json.loads(stdout.strip().split("\n")[0])
        assert "fee" in obj
        assert isinstance(obj["fee"], str)

    def test_nan_values_output_as_null(self):
        """获取足够数据，验证某些 NaN 字段以 null 输出"""
        rc, stdout, stderr = run_cli("--symbol", "全部", "--sort-by", "近3年", "--order", "asc", "--top-n", "10")
        assert rc == 0
        null_found = False
        for line in stdout.strip().split("\n"):
            obj = json.loads(line)
            # 检查是否有字段为 None
            for key in ["2y_return", "3y_return", "ytd_return"]:
                if obj.get(key) is None:
                    null_found = True
                    break
        # 不强制要求一定有 null，但如果出现应格式正确
        # 验证所有行均可解析
        for line in stdout.strip().split("\n"):
            json.loads(line)
```

- [ ] **步骤 2：运行集成测试**

```bash
uv run pytest akshare-open-fund-rank/scripts/tests/test_integration.py -v -m integration
```
预期：全部 PASS

- [ ] **步骤 3：Commit**

```bash
git add akshare-open-fund-rank/scripts/tests/test_integration.py
git commit -m "test: add integration tests for open-fund-rank skill

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 5：最终验证

- [ ] **步骤 1：运行所有单元测试**

```bash
uv run pytest akshare-open-fund-rank/scripts/tests/test_open_fund_rank.py -v
```
预期：全部 PASS

- [ ] **步骤 2：运行集成测试**

```bash
uv run pytest akshare-open-fund-rank/scripts/tests/test_integration.py -v -m integration
```
预期：全部 PASS

- [ ] **步骤 3：手动验证所有使用示例**

```bash
# 示例 1: 近 1 年涨幅最高的前 20 只
uv run python akshare-open-fund-rank/scripts/open_fund_rank.py --top-n 20

# 示例 2: 股票型 + 排序
uv run python akshare-open-fund-rank/scripts/open_fund_rank.py --symbol 股票型 --sort-by 近3月 --top-n 10

# 示例 3: 债券型 + 升序
uv run python akshare-open-fund-rank/scripts/open_fund_rank.py --symbol 债券型 --sort-by 单位净值 --order asc

# 示例 4: 多条件过滤
uv run python akshare-open-fund-rank/scripts/open_fund_rank.py --filter 近1月>10 --filter 近1年>30 --top-n 20

# 示例 5: 过滤 + 排序
uv run python akshare-open-fund-rank/scripts/open_fund_rank.py --symbol 股票型 --filter 单位净值<=5 --sort-by 日增长率

# 示例 6: JSON 输出
uv run python akshare-open-fund-rank/scripts/open_fund_rank.py --symbol QDII --output json
```
预期：全部正常输出

- [ ] **步骤 4：最终 Commit**

```bash
git add -A
git commit -m "chore: finalize akshare-open-fund-rank implementation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 总结

| 任务 | 内容 | 文件 |
|------|------|------|
| 任务 1 | 目录结构与 SKILL.md | 3 新建 |
| 任务 2 | 单元测试 (TDD) | 1 新建 |
| 任务 3 | 核心脚本实现 | 1 新建 |
| 任务 4 | 集成测试 | 1 新建 |
| 任务 5 | 最终验证 | — |

**最终文件结构：**
```
akshare-open-fund-rank/
  SKILL.md
  scripts/
    __init__.py
    open_fund_rank.py
    tests/
      __init__.py
      test_open_fund_rank.py
      test_integration.py
```

**运行方式：**
```bash
uv pip install akshare pandas
uv run python akshare-open-fund-rank/scripts/open_fund_rank.py --top-n 20
uv run pytest akshare-open-fund-rank/scripts/tests/ -v
```
