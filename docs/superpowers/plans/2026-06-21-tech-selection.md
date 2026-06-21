# akshare-tech-selection 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 基于 akshare 的 20 个技术指标 API，构建全功能技术选股工作台 SKILL，支持 4 种模式（single/intersect/scan/full）

**架构：** 三层结构 — fetcher.py（20 个 API 调用+解析）、engine.py（4 种模式聚合逻辑）、tech_selection.py（CLI 入口）。ThreadPoolExecutor 并发调用，统一 JSON 输出到 stdout

**技术栈：** Python 3, akshare, pandas, argparse, concurrent.futures

---

### 任务 1：项目骨架 + SKILL.md

**文件：**
- 创建：`akshare-tech-selection/SKILL.md`
- 创建：`akshare-tech-selection/scripts/__init__.py`
- 创建：`akshare-tech-selection/scripts/tests/__init__.py`
- 创建：`akshare-tech-selection/scripts/tests/conftest.py`

- [ ] **步骤 1：创建目录树和 SKILL.md**

```bash
mkdir -p akshare-tech-selection/scripts/tests
```

```markdown
<!-- SKILL.md -->
---
name: akshare-tech-selection
description: 技术指标选股工作台。基于 akshare 20 个技术选股 API，支持单指标查询、多指标交集筛选、全市场技术面扫描和全量分析四种模式。覆盖同花顺技术指标（创新高/低、连续涨跌、放量缩量、均线突破、量价关系、险资举牌、机构评级）、涨停板分析（涨跌停池、次新股池、昨日涨停表现、炸板股池）、异动监控（板块异动、个股盘口异动）。
---

# 技术指标选股

## 概述

基于 akshare 20 个技术选股 API，提供 4 种工作模式的技术面选股工具。所有输出为结构化 JSON。

## 使用方式

```bash
uv run python scripts/tech_selection.py --mode <mode> [options]
```

## 参数说明

### --mode（必需）

- `single`：单指标查询
- `intersect`：多指标交集筛选
- `scan`：全市场技术面扫描（按股票聚合信号）
- `full`：全量分析（scan + 指标健康度详情）

### --indicator（single/intersect 必需）

fetcher 函数名。single 模式传单个，intersect 模式逗号分隔多个。可选值：

| indicator | 描述 | 参数 |
|-----------|------|------|
| `fetch_cxg_ths` | 创新高 | symbol: 创月/半年/一年/历史新高 |
| `fetch_cxd_ths` | 创新低 | symbol: 创月/半年/一年/历史新低 |
| `fetch_lxsz_ths` | 连续上涨 | 无 |
| `fetch_lxxd_ths` | 连续下跌 | 无 |
| `fetch_cxfl_ths` | 持续放量 | 无 |
| `fetch_cxsl_ths` | 持续缩量 | 无 |
| `fetch_xstp_ths` | 向上突破均线 | symbol: 5/10/20/30/60/90/250/500日均线 |
| `fetch_xxtp_ths` | 向下突破均线 | symbol: 5/10/20/30/60/90/250/500日均线 |
| `fetch_ljqs_ths` | 量价齐升 | 无 |
| `fetch_ljqd_ths` | 量价齐跌 | 无 |
| `fetch_xzjp_ths` | 险资举牌 | 无 |
| `fetch_forecast_cninfo` | 机构评级预测 | date: YYYYMMDD |
| `fetch_zt_pool_strong` | 强势涨停池 | date: YYYYMMDD |
| `fetch_zt_pool` | 涨停池（全量涨停板） | date: YYYYMMDD |
| `fetch_zt_pool_dtgc` | 跌停股池 | date: YYYYMMDD |
| `fetch_zt_pool_sub_new` | 次新股池 | date: YYYYMMDD |
| `fetch_zt_pool_previous` | 昨日涨停今日表现 | date: YYYYMMDD |
| `fetch_zt_pool_zbgc` | 炸板股池 | date: YYYYMMDD |
| `fetch_board_change` | 板块异动排名 | 无 |
| `fetch_changes` | 个股盘口异动 | symbol: 22种异动类型 |

### --date（可选）

日期 `YYYYMMDD`，默认今天。作用于涨停板类(6) + 机构评级(1)。其他 13 个指标忽略此参数。

### --symbol（可选）

格式 `indicator_name=value`，可重复多次。覆盖指标的默认 symbol。

默认 symbol 表：

| indicator | 默认 symbol |
|-----------|-------------|
| `fetch_cxg_ths` | 创月新高 |
| `fetch_cxd_ths` | 创月新低 |
| `fetch_xstp_ths` | 500日均线 |
| `fetch_xxtp_ths` | 500日均线 |
| `fetch_changes` | 大笔买入 |

### --signal-threshold（可选，默认 1）

scan/full 模式下，只返回 signal_count >= N 的股票。

### --top-n（可选）

只返回前 N 条结果，默认全量。

### --workers（可选，默认 8）

并发数。

### --output（可选）

输出 JSON 文件路径，默认 stdout。

## 输出格式

统一 JSON 输出到 stdout，日志/错误写入 stderr。

### single 模式

```json
{
  "mode": "single",
  "indicator": "fetch_lxsz_ths",
  "params": {},
  "fetch_time": "2026-06-21 15:30:00",
  "count": 62,
  "data": [
    {
      "stock_code": "603192",
      "stock_name": "汇得科技",
      "序号": 1,
      "收盘价": 27.33,
      "连涨天数": 7,
      "所属行业": "化学制品"
    }
  ],
  "errors": []
}
```

### intersect 模式

```json
{
  "mode": "intersect",
  "indicators": ["fetch_lxsz_ths", "fetch_cxfl_ths"],
  "params_per_indicator": {},
  "fetch_time": "...",
  "total_indicators": 2,
  "succeeded_indicators": 2,
  "intersect_count": 8,
  "indicator_counts": {"fetch_lxsz_ths": 62, "fetch_cxfl_ths": 114},
  "data": [
    {
      "stock_code": "000423",
      "stock_name": "东阿阿胶",
      "matched_indicators": ["fetch_lxsz_ths", "fetch_cxfl_ths"],
      "indicator_details": {
        "fetch_lxsz_ths": {"序-号": 10, "收盘价": 55.25},
        "fetch_cxfl_ths": {"序-号": 5, "放量天数": 5}
      }
    }
  ],
  "errors": []
}
```

### scan 模式

```json
{
  "mode": "scan",
  "fetch_time": "...",
  "total_indicators": 20,
  "succeeded_indicators": 18,
  "signal_summary": {
    "total_stocks_with_signals": 2341,
    "top_signals": [
      {"indicator": "fetch_lxsz_ths", "count": 62}
    ]
  },
  "data": [
    {
      "stock_code": "000423",
      "stock_name": "东阿阿胶",
      "signals": [
        {"indicator": "fetch_lxsz_ths", "category": "连续上涨", "detail": {}}
      ],
      "signal_count": 3
    }
  ],
  "errors": []
}
```

### full 模式

在 scan 基础上，`signal_summary` 扩展为详细版：

```json
{
  "mode": "full",
  "fetch_time": "...",
  "total_indicators": 20,
  "succeeded_indicators": 18,
  "signal_summary": {
    "total_stocks_with_signals": 2341,
    "indicators": [
      {"indicator": "fetch_lxsz_ths", "category": "连续上涨", "status": "success", "total_rows": 62}
    ]
  },
  "data": [...],
  "errors": []
}
```

### exit code

| code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 部分失败或全部 API 失败 |
| 2 | 参数错误 |

## 错误处理

- 单个 API 失败：记录 error，不阻断其他 API
- 全部 API 失败：exit 1，仅输出 errors
- 参数错误：exit 2，stderr 输出原因

## 缓存策略

无缓存，实时查询。

## 依赖

```bash
uv pip install akshare pandas
```

## 使用示例

```bash
# single：查连续上涨
uv run python scripts/tech_selection.py --mode single --indicator fetch_lxsz_ths

# single：查一年新高
uv run python scripts/tech_selection.py --mode single --indicator fetch_cxg_ths --symbol fetch_cxg_ths=一年新高

# intersect：连续上涨 AND 持续放量 AND 向上突破60日均线
uv run python scripts/tech_selection.py \
  --mode intersect \
  --indicator fetch_lxsz_ths,fetch_cxfl_ths,fetch_xstp_ths \
  --symbol fetch_xstp_ths=60日均线

# scan：全量扫描，只看 3 个信号以上的股票
uv run python scripts/tech_selection.py --mode scan --date 20260620 --signal-threshold 3

# scan：只看 top 20
uv run python scripts/tech_selection.py --mode scan --top-n 20

# full：全量分析输出到文件
uv run python scripts/tech_selection.py --mode full --date 20260620 --output result.json
```
```

- [ ] **步骤 2：提交**

```bash
cd akshare-tech-selection
git init
git add SKILL.md scripts/__init__.py scripts/tests/__init__.py
git commit -m "chore: add akshare-tech-selection project skeleton with SKILL.md

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 2：conftest.py 测试配置

**文件：**
- 创建：`akshare-tech-selection/scripts/tests/conftest.py`

- [ ] **步骤 1：编写 conftest.py**

```python
"""pytest configuration for akshare-tech-selection"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires network)"
    )
```

- [ ] **步骤 2：验证 pytest 加载配置**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/ --collect-only 2>&1 | head -5
```

预期：无错误，pytest 成功初始化（即使还没有测试文件）

- [ ] **步骤 3：提交**

```bash
git add scripts/tests/conftest.py
git commit -m "chore: add pytest conftest with integration marker

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 3：fetcher.py — 常量和工具函数（TDD）

**文件：**
- 创建：`akshare-tech-selection/scripts/fetcher.py`
- 创建：`akshare-tech-selection/scripts/tests/test_fetcher.py`

- [ ] **步骤 1：编写失败的测试 — normalize_stock_code**

```python
"""fetcher 单元测试 (mock akshare API)"""
import os, sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fetcher


class TestNormalizeStockCode:
    def test_six_digit_code_unchanged(self):
        assert fetcher.normalize_stock_code("000001") == "000001"

    def test_sz_prefixed_code_stripped(self):
        assert fetcher.normalize_stock_code("SZ000001") == "000001"

    def test_sh_prefixed_code_stripped(self):
        assert fetcher.normalize_stock_code("SH600519") == "600519"

    def test_bj_prefixed_code_stripped(self):
        assert fetcher.normalize_stock_code("BJ830799") == "830799"

    def test_already_six_digit_string(self):
        assert fetcher.normalize_stock_code("300750") == "300750"

    def test_none_returns_none(self):
        assert fetcher.normalize_stock_code(None) is None

    def test_empty_string_returns_empty(self):
        assert fetcher.normalize_stock_code("") == ""

    def test_four_digit_converts_to_six(self):
        assert fetcher.normalize_stock_code("0001") == "000001"


class TestStandardizeOutput:
    def test_basic_dataframe(self):
        df = pd.DataFrame({
            "股票代码": ["000001", "600519"],
            "股票简称": ["平安银行", "贵州茅台"],
            "涨跌幅": [1.5, np.nan],
        })
        result = fetcher.standardize_output(
            df, code_col="股票代码", name_col="股票简称",
            indicator="fetch_test", category="测试指标",
            categories=["测试类"],
        )
        assert result["indicator"] == "fetch_test"
        assert result["category"] == "测试指标"
        assert result["categories"] == ["测试类"]
        assert result["count"] == 2
        assert len(result["data"]) == 2
        assert result["data"][0]["stock_code"] == "000001"
        assert result["data"][0]["stock_name"] == "平安银行"
        assert result["data"][0]["涨跌幅"] == 1.5
        assert result["data"][1]["涨跌幅"] is None  # NaN → null

    def test_empty_dataframe_returns_none(self):
        df = pd.DataFrame()
        result = fetcher.standardize_output(
            df, code_col="股票代码", name_col="股票简称",
            indicator="fetch_test", category="测试",
            categories=["测试类"],
        )
        assert result is None

    def test_none_dataframe_returns_none(self):
        result = fetcher.standardize_output(
            None, code_col="股票代码", name_col="股票简称",
            indicator="fetch_test", category="测试",
            categories=["测试类"],
        )
        assert result is None


class TestIndicatorRegistry:
    def test_registry_contains_all_20_indicators(self):
        assert len(fetcher.ALL_INDICATORS) == 20

    def test_each_indicator_has_required_keys(self):
        for ind in fetcher.ALL_INDICATORS:
            assert "name" in ind
            assert "api" in ind
            assert "category" in ind
            assert "code_col" in ind
            assert "name_col" in ind

    def test_no_duplicate_indicator_names(self):
        names = [ind["name"] for ind in fetcher.ALL_INDICATORS]
        assert len(names) == len(set(names))
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_fetcher.py -v 2>&1
```

预期：FAIL — `fetcher` module 不存在或缺少 `normalize_stock_code` 等函数

- [ ] **步骤 3：编写 fetcher.py — 常量和工具函数**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
技术指标选股 — 数据获取层
封装 20 个 akshare 技术选股 API，统一列名标准化和代码格式
"""
import pandas as pd
import numpy as np


# ---- 常量 ----

ALL_INDICATORS = [
    # 第 1 类：同花顺技术指标 (12 个)
    {
        "name": "fetch_cxg_ths",
        "api": "stock_rank_cxg_ths",
        "category": "创新高",
        "categories": ["同花顺技术指标", "趋势类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": True,
        "default_symbol": "创月新高",
        "needs_date": False,
        "arg_map": lambda symbol: (symbol,),
    },
    {
        "name": "fetch_cxd_ths",
        "api": "stock_rank_cxd_ths",
        "category": "创新低",
        "categories": ["同花顺技术指标", "趋势类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": True,
        "default_symbol": "创月新低",
        "needs_date": False,
        "arg_map": lambda symbol: (symbol,),
    },
    {
        "name": "fetch_lxsz_ths",
        "api": "stock_rank_lxsz_ths",
        "category": "连续上涨",
        "categories": ["同花顺技术指标", "趋势类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
        "arg_map": lambda: (),
    },
    {
        "name": "fetch_lxxd_ths",
        "api": "stock_rank_lxxd_ths",
        "category": "连续下跌",
        "categories": ["同花顺技术指标", "趋势类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
        "arg_map": lambda: (),
    },
    {
        "name": "fetch_cxfl_ths",
        "api": "stock_rank_cxfl_ths",
        "category": "持续放量",
        "categories": ["同花顺技术指标", "量价类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
        "arg_map": lambda: (),
    },
    {
        "name": "fetch_cxsl_ths",
        "api": "stock_rank_cxsl_ths",
        "category": "持续缩量",
        "categories": ["同花顺技术指标", "量价类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
        "arg_map": lambda: (),
    },
    {
        "name": "fetch_xstp_ths",
        "api": "stock_rank_xstp_ths",
        "category": "向上突破",
        "categories": ["同花顺技术指标", "突破类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": True,
        "default_symbol": "500日均线",
        "needs_date": False,
        "arg_map": lambda symbol: (symbol,),
    },
    {
        "name": "fetch_xxtp_ths",
        "api": "stock_rank_xxtp_ths",
        "category": "向下突破",
        "categories": ["同花顺技术指标", "突破类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": True,
        "default_symbol": "500日均线",
        "needs_date": False,
        "arg_map": lambda symbol: (symbol,),
    },
    {
        "name": "fetch_ljqs_ths",
        "api": "stock_rank_ljqs_ths",
        "category": "量价齐升",
        "categories": ["同花顺技术指标", "量价类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
        "arg_map": lambda: (),
    },
    {
        "name": "fetch_ljqd_ths",
        "api": "stock_rank_ljqd_ths",
        "category": "量价齐跌",
        "categories": ["同花顺技术指标", "量价类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
        "arg_map": lambda: (),
    },
    {
        "name": "fetch_xzjp_ths",
        "api": "stock_rank_xzjp_ths",
        "category": "险资举牌",
        "categories": ["同花顺技术指标", "资金类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
        "arg_map": lambda: (),
    },
    {
        "name": "fetch_forecast_cninfo",
        "api": "stock_rank_forecast_cninfo",
        "category": "机构评级",
        "categories": ["同花顺技术指标", "评级类"],
        "code_col": "证券代码",
        "name_col": "证券简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
        "arg_map": lambda date: (date,),
    },
    # 第 2 类：涨停板分析 (6 个)
    {
        "name": "fetch_zt_pool_strong",
        "api": "stock_zt_pool_strong_em",
        "category": "强势涨停",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
        "arg_map": lambda date: (date,),
    },
    {
        "name": "fetch_zt_pool",
        "api": "stock_zt_pool_em",
        "category": "涨停池",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
        "arg_map": lambda date: (date,),
    },
    {
        "name": "fetch_zt_pool_dtgc",
        "api": "stock_zt_pool_dtgc_em",
        "category": "跌停股池",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
        "arg_map": lambda date: (date,),
    },
    {
        "name": "fetch_zt_pool_sub_new",
        "api": "stock_zt_pool_sub_new_em",
        "category": "次新股池",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
        "arg_map": lambda date: (date,),
    },
    {
        "name": "fetch_zt_pool_previous",
        "api": "stock_zt_pool_previous_em",
        "category": "昨日涨停表现",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
        "arg_map": lambda date: (date,),
    },
    {
        "name": "fetch_zt_pool_zbgc",
        "api": "stock_zt_pool_zbgc_em",
        "category": "炸板股池",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
        "arg_map": lambda date: (date,),
    },
    # 第 3 类：异动监控 (2 个)
    {
        "name": "fetch_board_change",
        "api": "stock_board_change_em",
        "category": "板块异动",
        "categories": ["异动监控"],
        "code_col": "板块异动最频繁个股及所属类型-股票代码",
        "name_col": "板块异动最频繁个股及所属类型-股票名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
        "arg_map": lambda: (),
    },
    {
        "name": "fetch_changes",
        "api": "stock_changes_em",
        "category": "个股异动",
        "categories": ["异动监控"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": True,
        "default_symbol": "大笔买入",
        "needs_date": False,
        "arg_map": lambda symbol: (symbol,),
    },
]

# 按名称快速查找
INDICATOR_MAP = {ind["name"]: ind for ind in ALL_INDICATORS}


# ---- 工具函数 ----

def normalize_stock_code(code: str | None) -> str | None:
    """标准化股票代码：去除 SZ/SH/BJ 等前缀，补零到 6 位"""
    if code is None:
        return None
    code = str(code).strip().upper()
    for prefix in ("SZ", "SH", "BJ"):
        if code.startswith(prefix):
            code = code[len(prefix):]
    code = code.zfill(6)
    return code


def _nan_to_none(obj):
    """递归将 NaN 转为 None（用于 JSON 序列化）"""
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _nan_to_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_nan_to_none(v) for v in obj]
    return obj


def standardize_output(
    df: pd.DataFrame | None,
    code_col: str,
    name_col: str,
    indicator: str,
    category: str,
    categories: list[str],
) -> dict | None:
    """将 akshare 返回的 DataFrame 转为标准化 dict。
    
    Args:
        df: akshare API 返回的 DataFrame
        code_col: 股票代码列名
        name_col: 股票名称列名
        indicator: fetcher 名称
        category: 指标中文简称
        categories: 指标分类路径
    
    Returns:
        标准化 dict 格式，或 None（数据为空）
    """
    if df is None or df.empty:
        return None
    df = df.copy()
    # NaN → None
    df = df.where(df.notna(), None)
    records = df.to_dict(orient="records")
    for record in records:
        # 标准化股票代码
        if code_col in record:
            record["stock_code"] = normalize_stock_code(record.get(code_col))
        else:
            record["stock_code"] = None
        # 股票名称
        record["stock_name"] = record.get(name_col)
    # 递归清理 NaN
    records = _nan_to_none(records)
    return {
        "indicator": indicator,
        "category": category,
        "categories": categories,
        "count": len(records),
        "data": records,
    }


# 为每个指标生成 fetcher 函数（通过闭包动态生成）
def _make_fetcher(ind_def: dict):
    """根据指标定义创建 fetcher 函数"""
    import akshare as ak
    
    api_name = ind_def["api"]
    code_col = ind_def["code_col"]
    name_col = ind_def["name_col"]
    indicator = ind_def["name"]
    category = ind_def["category"]
    categories = ind_def["categories"]
    
    def fetcher(symbol: str | None = None, date: str | None = None) -> dict | None:
        try:
            fn = getattr(ak, api_name)
            # 构建参数
            if ind_def["needs_date"] and date:
                if "forecast" in api_name or "cninfo" in api_name:
                    result = fn(date=date)
                else:
                    result = fn(date=date)
            elif ind_def["needs_date"]:
                # 有 date 需求但未传入，用 arg_map 无参调用（某些 API 有默认值）
                args = ind_def["arg_map"]() if not ind_def.get("needs_symbol") else None
                if args is not None:
                    result = fn(*args)
                else:
                    result = fn()
            elif ind_def["needs_symbol"]:
                sym = symbol if symbol else ind_def["default_symbol"]
                args = ind_def["arg_map"](sym)
                result = fn(*args)
            else:
                args = ind_def["arg_map"]()
                result = fn(*args)
            return standardize_output(
                result, code_col, name_col,
                indicator, category, categories,
            )
        except Exception:
            return None
    return fetcher


# 为所有 20 个指标生成 fetcher 函数，并注入到模块作用域
_globals = globals()
for _ind in ALL_INDICATORS:
    _fn = _make_fetcher(_ind)
    _fn.__name__ = _ind["name"]
    _fn.__doc__ = f"获取{_ind['category']}榜单"
    _globals[_ind["name"]] = _fn
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_fetcher.py -v 2>&1
```

预期：全部 PASS

- [ ] **步骤 5：提交**

```bash
git add scripts/fetcher.py scripts/tests/test_fetcher.py
git commit -m "feat: add fetcher layer with 20 indicator definitions and helpers

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 4：fetcher.py — 股票代码格式兼容性测试 + 批量验证

**文件：**
- 修改：`akshare-tech-selection/scripts/tests/test_fetcher.py`

- [ ] **步骤 1：追加股票代码格式兼容性测试**

在 `test_fetcher.py` 末尾追加：

```python
class TestStockCodeCompatibility:
    """验证不同 API 的代码列能正确标准化"""
    
    def make_df(self, code_col, codes):
        return pd.DataFrame({
            code_col: codes,
            "名称": ["股票A", "股票B", "股票C"],
        })
    
    def test_ths_rank_code_column(self):
        """同花顺 rank 指标用 股票代码 列，6位格式"""
        df = self.make_df("股票代码", ["000001", "600519", "300750"])
        result = fetcher.standardize_output(
            df, "股票代码", "名称",
            "fetch_test", "测试", ["测试"],
        )
        assert result["data"][0]["stock_code"] == "000001"
        assert result["data"][1]["stock_code"] == "600519"
    
    def test_zt_pool_code_column(self):
        """涨停板用 代码 列，6位格式"""
        df = self.make_df("代码", ["000811", "600519", "300750"])
        result = fetcher.standardize_output(
            df, "代码", "名称",
            "fetch_test", "测试", ["测试"],
        )
        assert result["data"][1]["stock_code"] == "600519"
    
    def test_changes_em_code_column(self):
        """个股异动用 代码 列，6位格式"""
        df = self.make_df("代码", ["920161", "603177", "001296"])
        result = fetcher.standardize_output(
            df, "代码", "名称",
            "fetch_test", "测试", ["测试"],
        )
        assert result["data"][0]["stock_code"] == "920161"
    
    def test_forecast_cninfo_code_column(self):
        """机构评级用 证券代码 列，6位格式"""
        df = self.make_df("证券代码", ["000552", "600519", "688981"])
        result = fetcher.standardize_output(
            df, "证券代码", "证券简称",
            "fetch_test", "测试", ["测试"],
        )
        assert result["data"][2]["stock_code"] == "688981"
    
    def test_board_change_code_column(self):
        """板块异动用长列名，6位格式"""
        df = self.make_df("板块异动最频繁个股及所属类型-股票代码", ["301669", "001218", "688333"])
        result = fetcher.standardize_output(
            df, "板块异动最频繁个股及所属类型-股票代码",
            "板块异动最频繁个股及所属类型-股票名称",
            "fetch_test", "测试", ["测试"],
        )
        assert result["data"][0]["stock_code"] == "301669"
```

- [ ] **步骤 2：运行全部测试验证通过**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_fetcher.py -v 2>&1
```

预期：全部 PASS

- [ ] **步骤 3：提交**

```bash
git add scripts/tests/test_fetcher.py
git commit -m "test: add stock code format compatibility tests for all API categories

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 5：engine.py — run_single 模式（TDD）

**文件：**
- 创建：`akshare-tech-selection/scripts/engine.py`
- 创建：`akshare-tech-selection/scripts/tests/test_engine.py`

- [ ] **步骤 1：编写失败的测试 — test_engine.py (run_single)**

```python
"""engine 单元测试 (mock fetcher)"""
import os, sys, json
from datetime import date, datetime
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import engine


# ---- Mock fetcher 工厂 ----

def make_mock_fetcher(name, category, data_rows=None):
    """创建一个模拟的 fetcher 函数"""
    def mock_fetcher(symbol=None, date=None):
        if data_rows is None:
            return None
        records = []
        for i, row in enumerate(data_rows):
            record = {
                "stock_code": row.get("code", f"00000{i}"),
                "stock_name": row.get("name", f"测试{i}"),
                "extra_field": row.get("extra", 0),
            }
            # 加法原始列
            for k, v in row.items():
                if k not in ("code", "name", "extra"):
                    record[k] = v
            records.append(record)
        return {
            "indicator": name,
            "category": category,
            "categories": [category],
            "count": len(records),
            "data": records,
        }
    return mock_fetcher


class TestRunSingle:
    def test_returns_expected_structure(self, monkeypatch):
        mock = make_mock_fetcher("fetch_test", "测试", [
            {"code": "000001", "name": "平安银行", "close": 10.5},
            {"code": "600519", "name": "贵州茅台", "close": 1800.0},
        ])
        # 动态注入 mock
        # engine 通过 fetcher 模块获取函数，这里直接传 callable
        result = engine.run_single("fetch_test", _fetcher_callable=mock, symbol=None, date=None)
        assert result["mode"] == "single"
        assert result["indicator"] == "fetch_test"
        assert result["count"] == 2
        assert len(result["data"]) == 2
        assert "fetch_time" in result
        assert result["errors"] == []

    def test_fetcher_returns_none_produces_null_data(self, monkeypatch):
        mock = make_mock_fetcher("fetch_empty", "空", None)
        result = engine.run_single("fetch_empty", _fetcher_callable=mock)
        assert result["mode"] == "single"
        assert result["count"] == 0
        assert result["data"] == []
        assert len(result["errors"]) == 1
        assert result["errors"][0]["api"] == "fetch_empty"
        assert "null_data" in result["errors"][0]["error"].lower() or "empty" in result["errors"][0]["error"].lower()

    def test_data_items_contain_stock_code_and_stock_name(self, monkeypatch):
        mock = make_mock_fetcher("fetch_test", "测试", [
            {"code": "000001", "name": "平安银行"},
        ])
        result = engine.run_single("fetch_test", _fetcher_callable=mock)
        item = result["data"][0]
        assert item["stock_code"] == "000001"
        assert item["stock_name"] == "平安银行"
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_engine.py::TestRunSingle -v 2>&1
```

预期：FAIL — `engine` module 不存在或缺少 `run_single`

- [ ] **步骤 3：编写 engine.py — run_single**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
技术指标选股 — 引擎层
实现 4 种工作模式：single / intersect / scan / full
"""
import time
import random
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import fetcher


# ---- 工具 ----

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _call_fetcher(ind_name: str, symbol: str | None = None, date: str | None = None):
    """调用单个 fetcher，返回 (ind_name, result_dict_or_None, error_dict_or_None)"""
    fn = getattr(fetcher, ind_name, None)
    if fn is None:
        return ind_name, None, {"indicator": ind_name, "error": f"Unknown indicator: {ind_name}", "api": ind_name}
    try:
        result = fn(symbol=symbol, date=date)
        if result is None:
            return ind_name, None, {"indicator": ind_name, "error": "API returned null/empty data", "api": ind_name}
        return ind_name, result, None
    except Exception as e:
        return ind_name, None, {"indicator": ind_name, "error": str(e), "api": ind_name}


def _call_fetchers_concurrent(
    ind_names: list[str],
    symbols: dict[str, str] | None = None,
    date: str | None = None,
    max_workers: int = 8,
):
    """并发调用多个 fetcher，返回 (results_dict, errors_list)"""
    if symbols is None:
        symbols = {}
    results = {}
    errors = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for ind_name in ind_names:
            sym = symbols.get(ind_name)
            time.sleep(random.uniform(0.1, 0.3))
            futures[executor.submit(_call_fetcher, ind_name, sym, date)] = ind_name
        
        for future in as_completed(futures):
            ind_name, result, error = future.result()
            if error:
                errors.append(error)
            if result:
                results[ind_name] = result
    
    return results, errors


# ---- 模式 1: single ----

def run_single(
    indicator: str,
    symbol: str | None = None,
    date: str | None = None,
    _fetcher_callable=None,
) -> dict:
    """单指标查询"""
    params = {}
    if symbol:
        params["symbol"] = symbol
    if date:
        params["date"] = date
    
    if _fetcher_callable:
        result = _fetcher_callable(symbol=symbol, date=date)
        errors = []
        if result is None:
            errors.append({"indicator": indicator, "error": "API returned null/empty data", "api": indicator})
            data = []
            count = 0
        else:
            data = result.get("data", [])
            count = result.get("count", len(data))
            errors = []
    else:
        ind_name, result, error = _call_fetcher(indicator, symbol=symbol, date=date)
        errors = [error] if error else []
        if result:
            data = result.get("data", [])
            count = result.get("count", len(data))
        else:
            data = []
            count = 0
    
    return {
        "mode": "single",
        "indicator": indicator,
        "params": params,
        "fetch_time": _now_str(),
        "count": count,
        "data": data,
        "errors": errors,
    }


# ---- 模式 2: intersect ----

def run_intersect(
    indicators: list[str],
    symbols: dict[str, str] | None = None,
    date: str | None = None,
    max_workers: int = 8,
) -> dict:
    """多指标交集筛选"""
    if symbols is None:
        symbols = {}
    
    results, errors = _call_fetchers_concurrent(indicators, symbols, date, max_workers)
    
    # 提取代码集合
    code_sets = {}
    indicator_counts = {}
    for ind_name, result in results.items():
        codes = {r.get("stock_code") for r in result.get("data", []) if r.get("stock_code")}
        code_sets[ind_name] = codes
        indicator_counts[ind_name] = result.get("count", len(codes))
    
    # 记录空数据
    for ind_name in indicators:
        if ind_name not in results:
            indicator_counts[ind_name] = 0
    
    # 取交集
    if code_sets:
        common_codes = set.intersection(*code_sets.values()) if code_sets else set()
    else:
        common_codes = set()
    
    # 构建输出
    data = []
    for code in sorted(common_codes):
        stock_name = ""
        matched = []
        details = {}
        for ind_name, codes in code_sets.items():
            if code in codes:
                matched.append(ind_name)
                # 找对应行的 detail
                for r in results[ind_name]["data"]:
                    if r.get("stock_code") == code:
                        detail = {k: v for k, v in r.items() if k not in ("stock_code", "stock_name")}
                        details[ind_name] = detail
                        if not stock_name:
                            stock_name = r.get("stock_name", "")
                        break
        data.append({
            "stock_code": code,
            "stock_name": stock_name,
            "matched_indicators": sorted(matched),
            "indicator_details": details,
        })
    
    succeeded = len(results)
    
    return {
        "mode": "intersect",
        "indicators": indicators,
        "params_per_indicator": {ind: {"symbol": symbols.get(ind)} for ind in indicators if ind in symbols},
        "fetch_time": _now_str(),
        "total_indicators": len(indicators),
        "succeeded_indicators": succeeded,
        "intersect_count": len(data),
        "indicator_counts": indicator_counts,
        "data": data,
        "errors": errors,
    }


# ---- 模式 3: scan ----

def run_scan(
    date: str | None = None,
    symbols: dict[str, str] | None = None,
    signal_threshold: int = 1,
    top_n: int | None = None,
    max_workers: int = 8,
) -> dict:
    """全市场技术面扫描"""
    if symbols is None:
        symbols = {}
    
    all_ind_names = [ind["name"] for ind in fetcher.ALL_INDICATORS]
    results, errors = _call_fetchers_concurrent(all_ind_names, symbols, date, max_workers)
    
    # 按股票代码聚合信号
    stock_signals: dict[str, dict] = {}  # code -> {stock_name, signals[]}
    
    for ind_name, result in results.items():
        for row in result.get("data", []):
            code = row.get("stock_code")
            if not code:
                continue
            if code not in stock_signals:
                stock_signals[code] = {
                    "stock_name": row.get("stock_name", ""),
                    "signals": [],
                }
            detail = {k: v for k, v in row.items() if k not in ("stock_code", "stock_name")}
            stock_signals[code]["signals"].append({
                "indicator": ind_name,
                "category": result["category"],
                "detail": detail,
            })
    
    # 按 signal_count 降序，过滤阈值
    data = []
    for code, info in stock_signals.items():
        info["stock_code"] = code
        info["signal_count"] = len(info["signals"])
        if info["signal_count"] >= signal_threshold:
            data.append(info)
    
    data.sort(key=lambda x: x["signal_count"], reverse=True)
    
    if top_n and top_n > 0:
        data = data[:top_n]
    
    # signal_summary
    top_signals = sorted(
        [{"indicator": name, "count": r["count"]} for name, r in results.items()],
        key=lambda x: x["count"],
        reverse=True,
    )
    
    return {
        "mode": "scan",
        "fetch_time": _now_str(),
        "total_indicators": len(all_ind_names),
        "succeeded_indicators": len(results),
        "signal_summary": {
            "total_stocks_with_signals": len(stock_signals),
            "top_signals": top_signals,
        },
        "data": data,
        "errors": errors,
    }


# ---- 模式 4: full ----

def run_full(
    date: str | None = None,
    symbols: dict[str, str] | None = None,
    signal_threshold: int = 1,
    top_n: int | None = None,
    max_workers: int = 8,
) -> dict:
    """全量分析（scan + 详细指标健康度）"""
    if symbols is None:
        symbols = {}
    
    all_ind_names = [ind["name"] for ind in fetcher.ALL_INDICATORS]
    results, errors = _call_fetchers_concurrent(all_ind_names, symbols, date, max_workers)
    
    # 按股票代码聚合信号（与 scan 相同）
    stock_signals: dict[str, dict] = {}
    
    for ind_name, result in results.items():
        for row in result.get("data", []):
            code = row.get("stock_code")
            if not code:
                continue
            if code not in stock_signals:
                stock_signals[code] = {
                    "stock_name": row.get("stock_name", ""),
                    "signals": [],
                }
            detail = {k: v for k, v in row.items() if k not in ("stock_code", "stock_name")}
            stock_signals[code]["signals"].append({
                "indicator": ind_name,
                "category": result["category"],
                "detail": detail,
            })
    
    data = []
    for code, info in stock_signals.items():
        info["stock_code"] = code
        info["signal_count"] = len(info["signals"])
        if info["signal_count"] >= signal_threshold:
            data.append(info)
    
    data.sort(key=lambda x: x["signal_count"], reverse=True)
    
    if top_n and top_n > 0:
        data = data[:top_n]
    
    # signal_summary 详细版
    indicators_summary = []
    for ind in fetcher.ALL_INDICATORS:
        ind_name = ind["name"]
        if ind_name in results:
            indicators_summary.append({
                "indicator": ind_name,
                "category": ind["category"],
                "status": "success",
                "total_rows": results[ind_name]["count"],
            })
        else:
            # 检查是否在 errors 中
            in_errors = any(e.get("indicator") == ind_name for e in errors)
            indicators_summary.append({
                "indicator": ind_name,
                "category": ind["category"],
                "status": "error" if in_errors else "unknown",
                "total_rows": 0,
            })
    
    return {
        "mode": "full",
        "fetch_time": _now_str(),
        "total_indicators": len(all_ind_names),
        "succeeded_indicators": len(results),
        "signal_summary": {
            "total_stocks_with_signals": len(stock_signals),
            "indicators": indicators_summary,
        },
        "data": data,
        "errors": errors,
    }
```

- [ ] **步骤 4：运行 run_single 测试验证通过**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_engine.py::TestRunSingle -v 2>&1
```

预期：PASS

- [ ] **步骤 5：提交**

```bash
git add scripts/engine.py scripts/tests/test_engine.py
git commit -m "feat: add engine layer with run_single mode

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 6：engine.py — run_intersect 测试 + 验证

**文件：**
- 修改：`akshare-tech-selection/scripts/tests/test_engine.py`

- [ ] **步骤 1：追加 run_intersect 测试**

在 test_engine.py 末尾追加：

```python
class TestRunIntersect:
    def test_two_indicators_with_overlap(self, monkeypatch):
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 3,
                "data": [
                    {"stock_code": "000001", "stock_name": "平安银行", "val": 1},
                    {"stock_code": "600519", "stock_name": "贵州茅台", "val": 2},
                    {"stock_code": "300750", "stock_name": "宁德时代", "val": 3},
                ],
            }
        def mock_b(symbol=None, date=None):
            return {
                "indicator": "fetch_b", "category": "B类", "categories": ["B"],
                "count": 2,
                "data": [
                    {"stock_code": "600519", "stock_name": "贵州茅台", "val": 5},
                    {"stock_code": "000001", "stock_name": "平安银行", "val": 6},
                ],
            }
        # 直接测试交集逻辑
        import fetcher
        monkeypatch.setattr(fetcher, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(fetcher, "fetch_b", mock_b, raising=False)
        result = engine.run_intersect(["fetch_a", "fetch_b"], max_workers=1)
        assert result["intersect_count"] == 2
        codes = [d["stock_code"] for d in result["data"]]
        assert "000001" in codes
        assert "600519" in codes
        assert result["succeeded_indicators"] == 2

    def test_no_overlap_returns_empty(self, monkeypatch):
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 1,
                "data": [{"stock_code": "000001", "stock_name": "平安"}],
            }
        def mock_b(symbol=None, date=None):
            return {
                "indicator": "fetch_b", "category": "B类", "categories": ["B"],
                "count": 1,
                "data": [{"stock_code": "600519", "stock_name": "茅台"}],
            }
        import fetcher
        monkeypatch.setattr(fetcher, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(fetcher, "fetch_b", mock_b, raising=False)
        result = engine.run_intersect(["fetch_a", "fetch_b"], max_workers=1)
        assert result["intersect_count"] == 0
        assert result["data"] == []

    def test_one_fetcher_returns_none(self, monkeypatch):
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 1,
                "data": [{"stock_code": "000001", "stock_name": "平安"}],
            }
        def mock_b(symbol=None, date=None):
            return None
        import fetcher
        monkeypatch.setattr(fetcher, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(fetcher, "fetch_b", mock_b, raising=False)
        result = engine.run_intersect(["fetch_a", "fetch_b"], max_workers=1)
        assert result["intersect_count"] == 0
        assert result["indicator_counts"]["fetch_b"] == 0
        assert len(result["errors"]) >= 1

    def test_each_result_has_matched_indicators_and_details(self, monkeypatch):
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 1,
                "data": [{"stock_code": "000001", "stock_name": "平安", "score": 90}],
            }
        import fetcher
        monkeypatch.setattr(fetcher, "fetch_a", mock_a, raising=False)
        result = engine.run_intersect(["fetch_a"], max_workers=1)
        assert result["intersect_count"] == 1
        item = result["data"][0]
        assert "fetch_a" in item["matched_indicators"]
        assert "fetch_a" in item["indicator_details"]
        assert item["indicator_details"]["fetch_a"]["score"] == 90
```

- [ ] **步骤 2：运行 run_intersect 测试验证通过**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_engine.py::TestRunIntersect -v 2>&1
```

预期：PASS（engine.py 已有 run_intersect 实现）

- [ ] **步骤 3：提交**

```bash
git add scripts/tests/test_engine.py
git commit -m "test: add run_intersect tests with overlap and edge cases

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 7：engine.py — run_scan 测试 + 验证

**文件：**
- 修改：`akshare-tech-selection/scripts/tests/test_engine.py`

- [ ] **步骤 1：追加 run_scan 测试**

在 test_engine.py 末尾追加：

```python
class TestRunScan:
    def test_aggregates_signals_by_stock(self, monkeypatch):
        """同一只股票在多个指标命中，应聚合为一个条目"""
        import fetcher as ft
        
        # 临时替换 ALL_INDICATORS 为测试集
        test_indicators = [
            {"name": "fetch_a", "api": "mock", "category": "A类", "categories": ["A"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False, "arg_map": lambda: ()},
            {"name": "fetch_b", "api": "mock", "category": "B类", "categories": ["B"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False, "arg_map": lambda: ()},
        ]
        monkeypatch.setattr(ft, "ALL_INDICATORS", test_indicators)
        
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 2,
                "data": [
                    {"stock_code": "000001", "stock_name": "平安银行", "val": 1},
                    {"stock_code": "600519", "stock_name": "贵州茅台", "val": 2},
                ],
            }
        def mock_b(symbol=None, date=None):
            return {
                "indicator": "fetch_b", "category": "B类", "categories": ["B"],
                "count": 2,
                "data": [
                    {"stock_code": "000001", "stock_name": "平安银行", "val": 5},
                    {"stock_code": "300750", "stock_name": "宁德时代", "val": 6},
                ],
            }
        monkeypatch.setattr(ft, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(ft, "fetch_b", mock_b, raising=False)
        
        result = engine.run_scan(max_workers=1)
        
        # 000001 在 2 个指标中都出现
        pingan = [d for d in result["data"] if d["stock_code"] == "000001"][0]
        assert pingan["signal_count"] == 2
        assert len(pingan["signals"]) == 2
        signal_inds = [s["indicator"] for s in pingan["signals"]]
        assert "fetch_a" in signal_inds
        assert "fetch_b" in signal_inds

    def test_signal_threshold_filters(self, monkeypatch):
        import fetcher as ft
        test_indicators = [
            {"name": "fetch_a", "api": "mock", "category": "A类", "categories": ["A"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False, "arg_map": lambda: ()},
            {"name": "fetch_b", "api": "mock", "category": "B类", "categories": ["B"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False, "arg_map": lambda: ()},
        ]
        monkeypatch.setattr(ft, "ALL_INDICATORS", test_indicators)
        
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 1,
                "data": [{"stock_code": "000001", "stock_name": "平安银行", "val": 1}],
            }
        def mock_b(symbol=None, date=None):
            return {
                "indicator": "fetch_b", "category": "B类", "categories": ["B"],
                "count": 1,
                "data": [{"stock_code": "600519", "stock_name": "贵州茅台", "val": 2}],
            }
        monkeypatch.setattr(ft, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(ft, "fetch_b", mock_b, raising=False)
        
        # threshold=2: 只有同时在 2 个指标的股票才出现
        result = engine.run_scan(max_workers=1, signal_threshold=2)
        # 没有股票同时命中两个
        assert len(result["data"]) == 0

    def test_top_n_limits_results(self, monkeypatch):
        import fetcher as ft
        test_indicators = [
            {"name": "fetch_a", "api": "mock", "category": "A类", "categories": ["A"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False, "arg_map": lambda: ()},
        ]
        monkeypatch.setattr(ft, "ALL_INDICATORS", test_indicators)
        
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 5,
                "data": [
                    {"stock_code": f"00000{i}", "stock_name": f"股票{i}", "val": i}
                    for i in range(1, 6)
                ],
            }
        monkeypatch.setattr(ft, "fetch_a", mock_a, raising=False)
        
        result = engine.run_scan(max_workers=1, top_n=3)
        assert len(result["data"]) == 3

    def test_signal_summary_contains_top_signals(self, monkeypatch):
        import fetcher as ft
        test_indicators = [
            {"name": "fetch_a", "api": "mock", "category": "A类", "categories": ["A"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False, "arg_map": lambda: ()},
            {"name": "fetch_b", "api": "mock", "category": "B类", "categories": ["B"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False, "arg_map": lambda: ()},
        ]
        monkeypatch.setattr(ft, "ALL_INDICATORS", test_indicators)
        
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 10,
                "data": [{"stock_code": f"00000{i}", "stock_name": f"s{i}"} for i in range(10)],
            }
        def mock_b(symbol=None, date=None):
            return {
                "indicator": "fetch_b", "category": "B类", "categories": ["B"],
                "count": 3,
                "data": [{"stock_code": f"10000{i}", "stock_name": f"t{i}"} for i in range(3)],
            }
        monkeypatch.setattr(ft, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(ft, "fetch_b", mock_b, raising=False)
        
        result = engine.run_scan(max_workers=1)
        summary = result["signal_summary"]
        assert summary["total_stocks_with_signals"] == 13  # 10 + 3, no overlap
        assert len(summary["top_signals"]) == 2
```

- [ ] **步骤 2：运行 run_scan 测试验证通过**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_engine.py::TestRunScan -v 2>&1
```

预期：PASS

- [ ] **步骤 3：提交**

```bash
git add scripts/tests/test_engine.py
git commit -m "test: add run_scan tests for signal aggregation, threshold, top-n

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 8：engine.py — run_full 测试 + 验证

**文件：**
- 修改：`akshare-tech-selection/scripts/tests/test_engine.py`

- [ ] **步骤 1：追加 run_full 测试**

在 test_engine.py 末尾追加：

```python
class TestRunFull:
    def test_has_detailed_signal_summary(self, monkeypatch):
        import fetcher as ft
        test_indicators = [
            {"name": "fetch_a", "api": "mock", "category": "A类", "categories": ["A"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False, "arg_map": lambda: ()},
            {"name": "fetch_b", "api": "mock", "category": "B类", "categories": ["B"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False, "arg_map": lambda: ()},
        ]
        monkeypatch.setattr(ft, "ALL_INDICATORS", test_indicators)
        
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 5,
                "data": [{"stock_code": f"00000{i}", "stock_name": f"s{i}"} for i in range(5)],
            }
        def mock_b(symbol=None, date=None):
            return None  # this one fails
        monkeypatch.setattr(ft, "fetch_a", mock_a, raising=False)
        monkeypatch.setattr(ft, "fetch_b", mock_b, raising=False)
        
        result = engine.run_full(max_workers=1)
        
        assert result["mode"] == "full"
        assert result["total_indicators"] == 2
        assert result["succeeded_indicators"] == 1
        
        # signal_summary 详细版有 indicators 数组
        summary = result["signal_summary"]
        assert "indicators" in summary
        assert "total_stocks_with_signals" in summary
        assert len(summary["indicators"]) == 2
        
        # fetch_a 应该是 success
        a_info = [i for i in summary["indicators"] if i["indicator"] == "fetch_a"][0]
        assert a_info["status"] == "success"
        assert a_info["total_rows"] == 5
        
        # fetch_b 应该有 error status
        b_info = [i for i in summary["indicators"] if i["indicator"] == "fetch_b"][0]
        assert b_info["status"] == "error"
        assert b_info["total_rows"] == 0

    def test_data_structure_same_as_scan(self, monkeypatch):
        import fetcher as ft
        test_indicators = [
            {"name": "fetch_a", "api": "mock", "category": "A类", "categories": ["A"],
             "code_col": "代码", "name_col": "名称", "needs_symbol": False,
             "default_symbol": None, "needs_date": False, "arg_map": lambda: ()},
        ]
        monkeypatch.setattr(ft, "ALL_INDICATORS", test_indicators)
        
        def mock_a(symbol=None, date=None):
            return {
                "indicator": "fetch_a", "category": "A类", "categories": ["A"],
                "count": 1,
                "data": [{"stock_code": "000001", "stock_name": "平安", "val": 1}],
            }
        monkeypatch.setattr(ft, "fetch_a", mock_a, raising=False)
        
        result = engine.run_full()
        assert "data" in result
        assert len(result["data"]) == 1
        assert result["data"][0]["stock_code"] == "000001"
        assert result["data"][0]["signal_count"] == 1
        assert "signals" in result["data"][0]
```

- [ ] **步骤 2：运行 run_full 测试验证通过**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_engine.py::TestRunFull -v 2>&1
```

预期：PASS

- [ ] **步骤 3：运行全部 engine 测试**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_engine.py -v 2>&1
```

预期：全部 PASS

- [ ] **步骤 4：提交**

```bash
git add scripts/tests/test_engine.py
git commit -m "test: add run_full tests for detailed indicator health summary

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 9：CLI 入口 — tech_selection.py (TDD)

**文件：**
- 创建：`akshare-tech-selection/scripts/tech_selection.py`
- 修改：`akshare-tech-selection/scripts/tests/test_engine.py`（追加 CLI 参数解析测试）

- [ ] **步骤 1：编写失败的测试 — CLI 参数解析**

在 test_engine.py 末尾追加：

```python
class TestCLIParsing:
    """测试 CLI 参数解析逻辑（不实际执行 main）"""
    
    def test_parse_single_mode(self):
        from tech_selection import parse_args
        args = parse_args(["--mode", "single", "--indicator", "fetch_lxsz_ths"])
        assert args.mode == "single"
        assert args.indicator == "fetch_lxsz_ths"
    
    def test_parse_intersect_mode(self):
        from tech_selection import parse_args
        args = parse_args([
            "--mode", "intersect",
            "--indicator", "fetch_lxsz_ths,fetch_cxfl_ths",
        ])
        assert args.mode == "intersect"
        assert args.indicator == "fetch_lxsz_ths,fetch_cxfl_ths"
    
    def test_parse_with_date(self):
        from tech_selection import parse_args
        args = parse_args([
            "--mode", "scan",
            "--date", "20260620",
        ])
        assert args.date == "20260620"
    
    def test_parse_with_symbol(self):
        from tech_selection import parse_args
        args = parse_args([
            "--mode", "single",
            "--indicator", "fetch_cxg_ths",
            "--symbol", "fetch_cxg_ths=一年新高",
        ])
        assert len(args.symbol) == 1
        assert args.symbol[0] == "fetch_cxg_ths=一年新高"
    
    def test_parse_multiple_symbols(self):
        from tech_selection import parse_args
        args = parse_args([
            "--mode", "intersect",
            "--indicator", "fetch_cxg_ths,fetch_xstp_ths",
            "--symbol", "fetch_cxg_ths=一年新高",
            "--symbol", "fetch_xstp_ths=60日均线",
        ])
        assert len(args.symbol) == 2
    
    def test_parse_signal_threshold_default(self):
        from tech_selection import parse_args
        args = parse_args(["--mode", "scan"])
        assert args.signal_threshold == 1
    
    def test_parse_signal_threshold_custom(self):
        from tech_selection import parse_args
        args = parse_args(["--mode", "scan", "--signal-threshold", "5"])
        assert args.signal_threshold == 5
    
    def test_parse_top_n(self):
        from tech_selection import parse_args
        args = parse_args(["--mode", "scan", "--top-n", "50"])
        assert args.top_n == 50
    
    def test_parse_workers_default(self):
        from tech_selection import parse_args
        args = parse_args(["--mode", "scan"])
        assert args.workers == 8
    
    def test_parse_with_output(self):
        from tech_selection import parse_args
        args = parse_args(["--mode", "scan", "--output", "result.json"])
        assert args.output == "result.json"
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_engine.py::TestCLIParsing -v 2>&1
```

预期：FAIL — `tech_selection` module 不存在或缺少 `parse_args`

- [ ] **步骤 3：编写 tech_selection.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
技术指标选股 — CLI 入口
支持 4 种工作模式：single / intersect / scan / full
"""
import sys
import json
import argparse
from datetime import date

import engine


VALID_MODES = ("single", "intersect", "scan", "full")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="技术指标选股工作台 — 基于 akshare 20 个技术选股 API",
    )
    parser.add_argument(
        "--mode", required=True,
        choices=VALID_MODES,
        help="工作模式: single / intersect / scan / full",
    )
    parser.add_argument(
        "--indicator",
        help="指标名 (single: 单个; intersect: 逗号分隔多个)",
    )
    parser.add_argument(
        "--date",
        default=date.today().strftime("%Y%m%d"),
        help="日期 YYYYMMDD，默认今天 (作用于涨停板类+机构评级)",
    )
    parser.add_argument(
        "--symbol",
        action="append",
        default=[],
        help="格式 indicator_name=value，可重复。如 --symbol fetch_cxg_ths=一年新高",
    )
    parser.add_argument(
        "--signal-threshold",
        type=int,
        default=1,
        help="scan/full 中只返回 signal_count >= N 的股票，默认 1",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help="只返回前 N 条结果，默认全量",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="并发数，默认 8",
    )
    parser.add_argument(
        "--output",
        help="输出 JSON 文件路径，默认 stdout",
    )
    return parser.parse_args(argv)


def _parse_symbols(raw_symbols: list[str]) -> dict[str, str]:
    """解析 --symbol 参数为 dict"""
    result = {}
    for item in raw_symbols:
        if "=" in item:
            key, value = item.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def main() -> None:
    args = parse_args()
    
    # 参数校验
    if args.mode in ("single", "intersect") and not args.indicator:
        print(f"[ERROR] --mode {args.mode} 需要 --indicator 参数", file=sys.stderr)
        sys.exit(2)
    
    # 解析 symbol 参数
    symbols = _parse_symbols(args.symbol)
    
    # 路由到对应模式
    if args.mode == "single":
        sym = symbols.get(args.indicator)
        result = engine.run_single(args.indicator, symbol=sym, date=args.date)
        if args.top_n and result["data"]:
            result["data"] = result["data"][:args.top_n]
            result["count"] = len(result["data"])
    
    elif args.mode == "intersect":
        indicators = [s.strip() for s in args.indicator.split(",") if s.strip()]
        if not indicators:
            print("[ERROR] --indicator 不能为空", file=sys.stderr)
            sys.exit(2)
        result = engine.run_intersect(
            indicators, symbols=symbols, date=args.date, max_workers=args.workers,
        )
        if args.top_n and result["data"]:
            result["data"] = result["data"][:args.top_n]
            result["intersect_count"] = len(result["data"])
    
    elif args.mode == "scan":
        result = engine.run_scan(
            date=args.date, symbols=symbols,
            signal_threshold=args.signal_threshold,
            top_n=args.top_n, max_workers=args.workers,
        )
    
    elif args.mode == "full":
        result = engine.run_full(
            date=args.date, symbols=symbols,
            signal_threshold=args.signal_threshold,
            top_n=args.top_n, max_workers=args.workers,
        )
    
    else:
        print(f"[ERROR] 未知 mode: {args.mode}", file=sys.stderr)
        sys.exit(2)
    
    # 输出
    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
            f.write("\n")
    else:
        print(output_json)
    
    # exit code
    failed = result.get("errors", [])
    total = result.get("total_indicators", 1)
    succeeded = result.get("succeeded_indicators", 0)
    
    if failed and succeeded == 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_engine.py::TestCLIParsing -v 2>&1
```

预期：PASS

- [ ] **步骤 5：运行全部单元测试**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/ -v --ignore=scripts/tests/test_integration.py 2>&1
```

预期：全部 PASS

- [ ] **步骤 6：提交**

```bash
git add scripts/tech_selection.py scripts/tests/test_engine.py
git commit -m "feat: add CLI entry point with argparse and all 4 modes

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 10：集成测试

**文件：**
- 创建：`akshare-tech-selection/scripts/tests/test_integration.py`

- [ ] **步骤 1：编写集成测试**

```python
"""集成测试 — 需要真实网络，标记为 integration"""
import os, sys, json, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "tech_selection.py")


def run_cli(*args):
    result = subprocess.run(
        [sys.executable, SCRIPT_PATH] + list(args),
        capture_output=True, text=True,
        timeout=180,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.mark.integration
class TestRealAPI:
    def test_single_mode_lxsz_returns_data(self):
        rc, stdout, stderr = run_cli("--mode", "single", "--indicator", "fetch_lxsz_ths")
        assert rc == 0, f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["mode"] == "single"
        assert data["indicator"] == "fetch_lxsz_ths"
        assert data["count"] > 0
        assert len(data["data"]) > 0
        assert "stock_code" in data["data"][0]
        assert "stock_name" in data["data"][0]
    
    def test_single_mode_cxg_with_symbol(self):
        rc, stdout, stderr = run_cli(
            "--mode", "single",
            "--indicator", "fetch_cxg_ths",
            "--symbol", "fetch_cxg_ths=一年新高",
        )
        assert rc == 0, f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["count"] > 0
    
    def test_intersect_mode_two_indicators(self):
        rc, stdout, stderr = run_cli(
            "--mode", "intersect",
            "--indicator", "fetch_lxsz_ths,fetch_ljqs_ths",
        )
        assert rc == 0, f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["mode"] == "intersect"
        assert data["total_indicators"] == 2
        # 两个 real API 应该都成功
        assert data["succeeded_indicators"] >= 1
    
    def test_scan_mode_returns_signal_data(self):
        rc, stdout, stderr = run_cli("--mode", "scan", "--top-n", "10")
        assert rc == 0, f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["mode"] == "scan"
        assert data["total_indicators"] == 20
        assert "signal_summary" in data
        assert "data" in data
        assert len(data["data"]) <= 10
        # 应有信号聚合
        if data["data"]:
            item = data["data"][0]
            assert "signals" in item
            assert "signal_count" in item
            assert item["signal_count"] >= 1
    
    def test_full_mode_has_detailed_summary(self):
        rc, stdout, stderr = run_cli("--mode", "full", "--top-n", "5")
        assert rc == 0, f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["mode"] == "full"
        summary = data["signal_summary"]
        assert "indicators" in summary
        assert len(summary["indicators"]) == 20
        # 检查每个 indicator 条目结构
        for ind in summary["indicators"]:
            assert "indicator" in ind
            assert "status" in ind
            assert "total_rows" in ind
    
    def test_invalid_mode_exits_2(self):
        rc, stdout, stderr = run_cli("--mode", "invalid")
        assert rc == 2
    
    def test_single_missing_indicator_exits_2(self):
        rc, stdout, stderr = run_cli("--mode", "single")
        assert rc == 2
    
    def test_output_to_file(self, tmp_path):
        output_file = tmp_path / "test_output.json"
        rc, stdout, stderr = run_cli(
            "--mode", "single",
            "--indicator", "fetch_lxsz_ths",
            "--output", str(output_file),
        )
        assert rc == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["mode"] == "single"
```

- [ ] **步骤 2：运行集成测试**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_integration.py -v -m integration --timeout=180 2>&1
```

预期：PASS（需网络连接正常）

- [ ] **步骤 3：提交**

```bash
git add scripts/tests/test_integration.py
git commit -m "test: add integration tests for all 4 modes with real API calls

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 11：最终验证 + 提交

- [ ] **步骤 1：运行全部测试**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/ -v 2>&1
```

预期：全部 PASS（单元测试）或 PASS + SKIP（集成测试，取决于网络）

- [ ] **步骤 2：确认 SKILL.md 不存在占位符或 TODO**

```bash
grep -r "TODO\|待定\|FIXME\|XXX" akshare-tech-selection/SKILL.md akshare-tech-selection/scripts/*.py 2>&1
```

预期：无输出（没有遗留占位符）

- [ ] **步骤 3：确认 akshare 前缀符合 CLAUDE.md 规则 0**

规则 0 要求 skill 名称使用 "akshare-" 前缀。SKILL.md 中 name 已是 `akshare-tech-selection`。

- [ ] **步骤 4：最终提交**

```bash
git add -A
git commit -m "chore: finalize akshare-tech-selection skill implementation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
