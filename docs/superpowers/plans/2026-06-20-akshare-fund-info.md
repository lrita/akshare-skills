# akshare-fund-info 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建公募基金综合信息 SKILL，基于 akshare 的多个基金 API，输入单个基金代码，并发获取基本概况、净值走势、风险分析、盈利概率、费率规则、持仓、行业配置等全部维度的数据，聚合为结构化 JSON 输出。

**架构：** 单文件 `scripts/fund_info.py`，`ThreadPoolExecutor(max_workers=5)` 并发调用 10 个 API，聚合为 9 个 section 的 dict，`json.dump` 输出到 stdout，日志到 stderr。

**技术栈：** Python ≥ 3.10, akshare, pandas, concurrent.futures (stdlib), argparse (stdlib), json (stdlib)

---

### 任务 1：创建目录结构与 SKILL.md

**文件：**
- 创建：`akshare-fund-info/SKILL.md`
- 创建：`akshare-fund-info/scripts/__init__.py`
- 创建：`akshare-fund-info/scripts/tests/__init__.py`

- [ ] **步骤 1：创建 SKILL.md**

```markdown
---
name: akshare-fund-info
description: Use when the user needs to look up detailed information about a specific open-end fund — overview, NAV history, risk analysis, profit probability, fee structure, holding rules, stock/bond holdings, industry allocation. Provides comprehensive multi-dimensional data for fund analysis. Single fund per invocation.
---

# 公募基金综合信息

## 概述

基于 akshare 多个基金信息 API，输入单个基金代码（6位），并发获取基本概况、净值走势（成立来全量）、风险分析、盈利概率、费率规则、资产配置、股票持仓、债券持仓、行业配置等全部维度的数据，聚合为结构化 JSON 输出，供 AI Agent 进行基金分析。

## 使用方式

```bash
uv run python scripts/fund_info.py --code 000001
```

所有输出写入 stdout（单个 JSON 对象），日志/错误信息写入 stderr。exit code: 0 成功, 1 部分失败/无数据, 2 参数错误。

## 参数说明

### `--code`（必需）

6 位纯数字基金代码，如 `000001`、`015641`。

## 输出格式

输出为一个顶层 JSON 对象，包含 `meta`、9 个数据 section、`errors`。

### meta

| 字段 | 类型 | 说明 |
|---|---|---|
| `fund_code` | string | 查询的基金代码 |
| `fetch_time` | string | 数据获取时间 (YYYY-MM-DD HH:MM:SS) |
| `portfolio_year` | string | 持仓查询年份 |
| `portfolio_date` | string | 资产配置查询日期 (YYYYMMDD) |
| `nav_period` | string | 净值走势时间段（固定 "成立来"） |
| `nav_indicator` | string | 净值走势指标（固定 "单位净值走势"） |

### overview — 基本概况

数据来源: akshare.fund_overview_em

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `fund_full_name` | string | - | 基金全称 |
| `fund_name` | string | - | 基金简称 |
| `fund_code` | string | - | 基金代码 |
| `fund_type` | string | - | 基金类型 |
| `issue_date` | string | - | 发行日期 |
| `establishment_date` | string | - | 成立日期 |
| `establishment_scale` | string | - | 成立时规模（原始文本） |
| `net_asset_value` | string | - | 净资产规模（原始文本） |
| `share_size` | string | - | 份额规模（原始文本） |
| `fund_manager` | string | - | 基金管理人 |
| `fund_custodian` | string | - | 基金托管人 |
| `portfolio_manager` | string | - | 基金经理人 |
| `dividends_since_inception` | string | - | 成立来分红 |
| `management_fee_rate` | string | - | 管理费率（原始文本） |
| `custodian_fee_rate` | string | - | 托管费率（原始文本） |
| `sales_service_fee_rate` | string | - | 销售服务费率（原始文本） |
| `max_subscription_fee_rate` | string | - | 最高认购费率（原始文本） |
| `benchmark` | string | - | 业绩比较基准 |
| `tracking_target` | string | - | 跟踪标的 |

### nav_history — 净值走势

数据来源: akshare.fund_open_fund_info_em (indicator="单位净值走势", period="成立来")

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `date` | string | - | 净值日期 (YYYY-MM-DD) |
| `unit_net_value` | float/null | 元 | 单位净值 |
| `daily_return` | float/null | % | 日增长率 |

### risk_analysis — 风险分析

数据来源: akshare.fund_individual_analysis_xq

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `period` | string | - | 周期（近1年/近3年/近5年） |
| `risk_return_rank` | int/null | 百分位 | 较同类风险收益比（0-100，越高越好） |
| `risk_resilience_rank` | int/null | 百分位 | 较同类抗风险波动（0-100，越高越好） |
| `annualized_volatility` | float/null | % | 年化波动率 |
| `annualized_sharpe` | float/null | - | 年化夏普比率 |
| `max_drawdown` | float/null | % | 最大回撤 |

### profit_probability — 盈利概率

数据来源: akshare.fund_individual_profit_probability_xq

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `holding_period` | string | - | 持有时长（满6个月/满1年/满2年/满3年） |
| `profit_probability` | float/null | % | 盈利概率 |
| `avg_return` | float/null | % | 平均收益 |

### asset_allocation — 资产配置

数据来源: akshare.fund_individual_detail_hold_xq

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `asset_type` | string | - | 资产类型 |
| `allocation_ratio` | float/null | % | 仓位占比 |

### fee_and_rules — 费率与交易规则

数据来源: akshare.fund_fee_em + akshare.fund_individual_detail_info_xq

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `purchase_status` | string | - | 申购状态 |
| `redemption_status` | string | - | 赎回状态 |
| `auto_invest_status` | string | - | 定投状态 |
| `management_fee_rate` | string | - | 管理费率（每年） |
| `custodian_fee_rate` | string | - | 托管费率（每年） |
| `sales_service_fee_rate` | string | - | 销售服务费率（每年） |
| `redemption_fee_table` | array | - | [{period: string, rate: string}]，rate 单位为 % |
| `purchase_rules` | array | - | [{amount_range: string, fee_rate: string}] |
| `redemption_rules` | array | - | [{holding_period: string, fee_rate: string}] |
| `other_fees` | array | - | [{name: string, rate: string}] |

### stock_holdings — 股票持仓

数据来源: akshare.fund_portfolio_hold_em（最新季度）

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `stock_code` | string | - | 股票代码 |
| `stock_name` | string | - | 股票名称 |
| `net_value_ratio` | float/null | % | 占净值比例 |
| `shares_held` | float/null | 万股 | 持股数 |
| `market_value` | float/null | 万元 | 持仓市值 |
| `quarter` | string | - | 报告期 |

### bond_holdings — 债券持仓

数据来源: akshare.fund_portfolio_bond_hold_em（最新季度）

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `bond_code` | string | - | 债券代码 |
| `bond_name` | string | - | 债券名称 |
| `net_value_ratio` | float/null | % | 占净值比例 |
| `market_value` | float/null | 万元 | 持仓市值 |
| `quarter` | string | - | 报告期 |

### industry_allocation — 行业配置

数据来源: akshare.fund_portfolio_industry_allocation_em

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `industry_name` | string | - | 行业类别 |
| `net_value_ratio` | float/null | % | 占净值比例 |
| `market_value` | float/null | 万元 | 市值 |
| `report_date` | string | - | 截止时间 (YYYY-MM-DD) |

### errors

| 字段 | 类型 | 说明 |
|---|---|---|
| `section` | string | 失败的 section 名称 |
| `error` | string | 错误描述 |
| `api` | string | 调用的 API 函数名 |

NaN 值输出为 `null`。nav_history 为成立来全量历史数据（通常数千条）。

## 缓存策略

无缓存，每次实时查询，保证数据最新。

## 依赖

```bash
uv pip install akshare pandas
```

## 使用示例

```bash
# 查询基金 000001 的完整信息
uv run python scripts/fund_info.py --code 000001

# 查询基金 015641
uv run python scripts/fund_info.py --code 015641
```
```

- [ ] **步骤 2：创建目录和空文件**

```bash
mkdir -p akshare-fund-info/scripts/tests
touch akshare-fund-info/scripts/__init__.py
touch akshare-fund-info/scripts/tests/__init__.py
```

- [ ] **步骤 3：Commit**

```bash
git add akshare-fund-info/
git commit -m "feat: add akshare-fund-info SKILL.md and directory structure

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 2：编写单元测试（TDD — 红阶段）

**文件：**
- 创建：`akshare-fund-info/scripts/tests/test_fund_info.py`

- [ ] **步骤 1：编写全部单元测试**

在 `akshare-fund-info/scripts/tests/test_fund_info.py` 中：

```python
"""公募基金综合信息单元测试 (mock 全部 akshare API)"""
import os, sys, json, io
from datetime import date, datetime
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fund_info as fi


# ---- Mock 数据工厂 ----

def make_mock_overview_df():
    return pd.DataFrame([{
        "基金全称": "测试基金混合型证券投资基金",
        "基金简称": "测试基金混合A",
        "基金代码": "000001（前端）",
        "基金类型": "混合型",
        "发行日期": "2020-01-01",
        "成立日期/规模": "2020-03-15 / 5.00亿份",
        "净资产规模": "10.00亿元（截止至：2026年03月31日）",
        "份额规模": "8.00亿份（截止至：2026年03月31日）",
        "基金管理人": "测试基金公司",
        "基金托管人": "测试银行",
        "基金经理人": "张三",
        "成立来分红": "每份累计0.50元（3次）",
        "管理费率": "1.50%（每年）",
        "托管费率": "0.25%（每年）",
        "销售服务费率": "0.00%（每年）",
        "最高认购费率": "1.50%（前端）",
        "业绩比较基准": "沪深300指数*80%+中债综合指数*20%",
        "跟踪标的": "该基金无跟踪标的",
    }])


def make_mock_nav_df():
    return pd.DataFrame({
        "净值日期": [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 4)],
        "单位净值": [1.5000, 1.5100, 1.5050],
        "日增长率": [0.0, 0.67, -0.33],
    })


def make_mock_risk_df():
    return pd.DataFrame({
        "周期": ["近1年", "近3年", "近5年"],
        "较同类风险收益比": [73, 76, 53],
        "较同类抗风险波动": [39, 55, 52],
        "年化波动率": [26.71, 22.08, 20.71],
        "年化夏普比率": [2.79, 0.70, 0.01],
        "最大回撤": [15.89, 29.90, 52.93],
    })


def make_mock_profit_df():
    return pd.DataFrame({
        "持有时长": ["满6个月", "满1年", "满2年", "满3年"],
        "盈利概率": [55.0, 60.0, 63.0, 71.0],
        "平均收益": [6.15, 13.81, 29.13, 43.54],
    })


def make_mock_asset_alloc_df():
    return pd.DataFrame({
        "资产类型": ["股票", "现金", "其他"],
        "仓位占比": [51.95, 19.51, 29.09],
    })


def make_mock_fee_status_df():
    return pd.DataFrame({
        0: ["申购状态", "普通回活期宝", "极速回活期宝"],
        1: ["开放申购", "支持", "支持"],
        2: ["赎回状态", "定投状态", "超级转换"],
        3: ["开放赎回", "支持", "支持"],
        4: [np.nan, np.nan, np.nan],
        5: [np.nan, np.nan, np.nan],
    })


def make_mock_fee_op_cost_df():
    return pd.DataFrame({
        0: ["管理费率", "托管费率", "销售服务费率"],
        1: ["1.50%（每年）", "0.25%（每年）", "0.00%（每年）"],
        2: [np.nan, np.nan, np.nan],
        3: [np.nan, np.nan, np.nan],
        4: [np.nan, np.nan, np.nan],
        5: [np.nan, np.nan, np.nan],
    })


def make_mock_fee_redemption_df():
    return pd.DataFrame({
        "适用期限": ["小于7天", "大于等于7天，小于30天", "大于等于730天"],
        "赎回费率": ["1.50%", "0.75%", "0.00%"],
    })


def make_mock_trade_rules_df():
    return pd.DataFrame({
        "费用类型": ["买入规则", "买入规则", "卖出规则", "卖出规则", "其他费用", "其他费用"],
        "条件或名称": [
            "0.0万<买入金额<100.0万", "100.0万<=买入金额<500.0万",
            "0.0天<持有期限<7.0天", "7.0天<=持有期限",
            "基金管理费", "基金托管费",
        ],
        "费用": ["1.5", "1.2", "1.5", "0.5", "1.2", "0.2"],
    })


def make_mock_stock_holding_df():
    return pd.DataFrame({
        "序号": [1, 2, 3],
        "股票代码": ["002025", "600862", "600941"],
        "股票名称": ["航天电器", "中航高科", "中国移动"],
        "占净值比例": [3.46, 3.24, 2.86],
        "持股数": [209.92, 380.43, 62.11],
        "持仓市值": [7947.67, 7441.16, 6568.75],
        "季度": ["2024年1季度股票投资明细"] * 3,
    })


def make_mock_bond_holding_df():
    return pd.DataFrame({
        "序号": [1, 2],
        "债券代码": ["230304", "101564021"],
        "债券名称": ["23进出04", "15华能集MTN002"],
        "占净值比例": [4.59, 4.29],
        "持仓市值": [11114.27, 10379.44],
        "季度": ["2023年4季度债券投资明细"] * 2,
    })


def make_mock_industry_df():
    return pd.DataFrame({
        "序号": [1, 2],
        "行业类别": ["制造业", "信息技术"],
        "占净值比例": [56.58, 5.72],
        "市值": [136966.39, 13849.95],
        "截止时间": ["2023-12-31", "2023-12-31"],
    })


# ---- 代码校验 ----

class TestValidateCode:
    def test_valid_6_digit(self):
        fi.validate_code("000001")  # 不应抛出
        fi.validate_code("015641")  # 不应抛出

    def test_too_short_raises_valueerror(self):
        with pytest.raises(ValueError):
            fi.validate_code("12345")

    def test_too_long_raises_valueerror(self):
        with pytest.raises(ValueError):
            fi.validate_code("1234567")

    def test_non_digit_raises_valueerror(self):
        with pytest.raises(ValueError):
            fi.validate_code("abc123")


# ---- 年份推断 ----

class TestDeterminePortfolioYear:
    def test_after_q1_disclosure_cutoff(self):
        # 6月20日 → 已过 4/22 → 当前年份 - 1
        ref_date = date(2026, 6, 20)
        assert fi.determine_portfolio_year(ref_date) == 2025

    def test_before_q1_disclosure_cutoff(self):
        # 3月1日 → 未过 4/22 → 当前年份 - 2
        ref_date = date(2026, 3, 1)
        assert fi.determine_portfolio_year(ref_date) == 2024

    def test_on_cutoff_day(self):
        # 4月22日 → 已过 → 当前年份 - 1
        ref_date = date(2026, 4, 22)
        assert fi.determine_portfolio_year(ref_date) == 2025

    def test_january(self):
        ref_date = date(2026, 1, 15)
        assert fi.determine_portfolio_year(ref_date) == 2024


class TestDetermineHoldDate:
    def test_mid_year_returns_last_year_q4(self):
        ref_date = date(2026, 6, 20)
        assert fi.determine_hold_date(ref_date) == "20251231"

    def test_early_year_returns_two_years_ago_q4(self):
        ref_date = date(2026, 1, 15)
        assert fi.determine_hold_date(ref_date) == "20241231"

    def test_december(self):
        ref_date = date(2026, 12, 1)
        assert fi.determine_hold_date(ref_date) == "20251231"


# ---- API 响应处理 ----

class TestParseOverview:
    def test_parses_all_fields(self):
        df = make_mock_overview_df()
        result = fi.parse_overview(df)
        assert result["fund_full_name"] == "测试基金混合型证券投资基金"
        assert result["fund_name"] == "测试基金混合A"
        assert result["fund_type"] == "混合型"
        assert result["fund_manager"] == "测试基金公司"
        assert "management_fee_rate" in result
        assert "benchmark" in result

    def test_empty_df_returns_none(self):
        result = fi.parse_overview(pd.DataFrame())
        assert result is None


class TestParseNavHistory:
    def test_converts_all_records(self):
        df = make_mock_nav_df()
        result = fi.parse_nav_history(df)
        assert len(result) == 3
        assert result[0]["date"] == "2025-01-02"
        assert result[0]["unit_net_value"] == pytest.approx(1.5)
        assert result[0]["daily_return"] == pytest.approx(0.0)

    def test_empty_df_returns_none(self):
        result = fi.parse_nav_history(pd.DataFrame())
        assert result is None


class TestParseRiskAnalysis:
    def test_converts_all_records(self):
        df = make_mock_risk_df()
        result = fi.parse_risk_analysis(df)
        assert len(result) == 3
        assert result[0]["period"] == "近1年"
        assert result[0]["risk_return_rank"] == 73
        assert result[0]["annualized_volatility"] == pytest.approx(26.71)

    def test_empty_df_returns_none(self):
        result = fi.parse_risk_analysis(pd.DataFrame())
        assert result is None


class TestParseProfitProbability:
    def test_converts_all_records(self):
        df = make_mock_profit_df()
        result = fi.parse_profit_probability(df)
        assert len(result) == 4
        assert result[0]["holding_period"] == "满6个月"
        assert result[0]["profit_probability"] == pytest.approx(55.0)

    def test_empty_df_returns_none(self):
        result = fi.parse_profit_probability(pd.DataFrame())
        assert result is None


class TestParseAssetAllocation:
    def test_converts_all_records(self):
        df = make_mock_asset_alloc_df()
        result = fi.parse_asset_allocation(df)
        assert len(result) == 3
        assert result[0]["asset_type"] == "股票"
        assert result[0]["allocation_ratio"] == pytest.approx(51.95)

    def test_empty_df_returns_none(self):
        result = fi.parse_asset_allocation(pd.DataFrame())
        assert result is None


class TestParseFeeAndRules:
    def test_parses_all_fields(self):
        result = fi.parse_fee_and_rules(
            make_mock_fee_status_df(),
            make_mock_fee_op_cost_df(),
            make_mock_fee_redemption_df(),
            make_mock_trade_rules_df(),
        )
        assert result["purchase_status"] == "开放申购"
        assert result["redemption_status"] == "开放赎回"
        assert result["auto_invest_status"] == "支持"
        assert result["management_fee_rate"] == "1.50%（每年）"
        assert result["custodian_fee_rate"] == "0.25%（每年）"
        assert len(result["redemption_fee_table"]) == 3
        assert len(result["purchase_rules"]) == 2
        assert len(result["redemption_rules"]) == 2
        assert len(result["other_fees"]) == 2

    def test_empty_dfs_returns_none(self):
        empty = pd.DataFrame()
        result = fi.parse_fee_and_rules(empty, empty, empty, empty)
        assert result is None


class TestParseStockHoldings:
    def test_converts_all_records(self):
        df = make_mock_stock_holding_df()
        result = fi.parse_stock_holdings(df)
        assert len(result) == 3
        assert result[0]["stock_code"] == "002025"
        assert result[0]["net_value_ratio"] == pytest.approx(3.46)

    def test_empty_df_returns_none(self):
        result = fi.parse_stock_holdings(pd.DataFrame())
        assert result is None


class TestParseBondHoldings:
    def test_converts_all_records(self):
        df = make_mock_bond_holding_df()
        result = fi.parse_bond_holdings(df)
        assert len(result) == 2
        assert result[0]["bond_code"] == "230304"

    def test_empty_df_returns_none(self):
        result = fi.parse_bond_holdings(pd.DataFrame())
        assert result is None


class TestParseIndustryAllocation:
    def test_converts_all_records(self):
        df = make_mock_industry_df()
        result = fi.parse_industry_allocation(df)
        assert len(result) == 2
        assert result[0]["industry_name"] == "制造业"
        assert result[0]["net_value_ratio"] == pytest.approx(56.58)

    def test_empty_df_returns_none(self):
        result = fi.parse_industry_allocation(pd.DataFrame())
        assert result is None


# ---- NaN 处理 ----

class TestNaNHandling:
    def test_nan_in_dataframe_becomes_none_in_output(self):
        df = pd.DataFrame({
            "净值日期": [date(2025, 1, 2)],
            "单位净值": [np.nan],
            "日增长率": [0.0],
        })
        result = fi.parse_nav_history(df)
        assert result[0]["unit_net_value"] is None


# ---- 聚合 ----

class TestAggregateResult:
    def test_all_sections_present(self):
        aggregated = fi.aggregate_result(
            code="000001",
            overview={"fund_name": "test"},
            nav=[{"date": "2025-01-01"}],
            risk=[{"period": "近1年"}],
            profit=[{"holding_period": "满1年"}],
            asset_alloc=[{"asset_type": "股票"}],
            fee={"purchase_status": "开放申购"},
            stock_holdings=[{"stock_code": "000001"}],
            bond_holdings=[{"bond_code": "000001"}],
            industry=[{"industry_name": "制造业"}],
            errors=[],
        )
        assert "meta" in aggregated
        assert aggregated["meta"]["fund_code"] == "000001"
        assert aggregated["overview"] is not None
        assert aggregated["nav_history"] is not None
        assert aggregated["risk_analysis"] is not None
        assert aggregated["profit_probability"] is not None
        assert aggregated["asset_allocation"] is not None
        assert aggregated["fee_and_rules"] is not None
        assert aggregated["stock_holdings"] is not None
        assert aggregated["bond_holdings"] is not None
        assert aggregated["industry_allocation"] is not None
        assert aggregated["errors"] == []

    def test_failed_section_is_null_with_error(self):
        aggregated = fi.aggregate_result(
            code="000001",
            overview={"fund_name": "test"},
            nav=None,  # 失败
            risk=[{"period": "近1年"}],
            profit=[{"holding_period": "满1年"}],
            asset_alloc=[{"asset_type": "股票"}],
            fee={"purchase_status": "开放申购"},
            stock_holdings=[{"stock_code": "000001"}],
            bond_holdings=None,  # 失败
            industry=[{"industry_name": "制造业"}],
            errors=[
                {"section": "nav_history", "error": "timeout", "api": "fund_open_fund_info_em"},
                {"section": "bond_holdings", "error": "no data", "api": "fund_portfolio_bond_hold_em"},
            ],
        )
        assert aggregated["nav_history"] is None
        assert aggregated["bond_holdings"] is None
        assert len(aggregated["errors"]) == 2
        assert aggregated["errors"][0]["section"] == "nav_history"
```

- [ ] **步骤 2：运行测试验证失败**

```bash
uv run pytest akshare-fund-info/scripts/tests/test_fund_info.py -v
```
预期：全部 FAIL（模块未定义）

---

### 任务 3：实现核心脚本

**文件：**
- 创建：`akshare-fund-info/scripts/fund_info.py`

- [ ] **步骤 1：编写完整实现**

在 `akshare-fund-info/scripts/fund_info.py` 中：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
公募基金综合信息查询脚本
基于 akshare 多个基金 API，并发获取基金概况、净值、风险、费率、持仓等全维度数据
"""
import sys
import json
import argparse
import re
import time
import random
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np


# ---- 常量 ----

Q1_DISCLOSURE_CUTOFF_DAY = (4, 22)  # (month, day)

SECTION_ORDER = [
    "overview", "nav_history", "risk_analysis", "profit_probability",
    "asset_allocation", "fee_and_rules", "stock_holdings",
    "bond_holdings", "industry_allocation",
]


# ---- 校验 ----

def validate_code(code: str) -> None:
    """校验基金代码格式（6位纯数字）"""
    if not re.match(r"^\d{6}$", code):
        raise ValueError(
            f"非法的基金代码: '{code}'。基金代码必须为 6 位纯数字。"
        )


# ---- 日期推断 ----

def determine_portfolio_year(ref_date: date) -> int:
    """根据当前日期推断持仓查询年份。

    规则：若已过 Q1 披露截止日 (4/22)，取当前年份 - 1；否则取 - 2。
    例如：2026-06-20 → 2025; 2026-03-01 → 2024
    """
    cutoff_month, cutoff_day = Q1_DISCLOSURE_CUTOFF_DAY
    passed_cutoff = (
        ref_date.month > cutoff_month
        or (ref_date.month == cutoff_month and ref_date.day >= cutoff_day)
    )
    return ref_date.year - 1 if passed_cutoff else ref_date.year - 2


def determine_hold_date(ref_date: date) -> str:
    """推断 fund_individual_detail_hold_xq 的 date 参数 (YYYYMMDD)。

    取最近一个 Q4 的 12 月 31 日。若已过 4/22 用去年的 Q4，否则用前年的 Q4。
    """
    year = determine_portfolio_year(ref_date)
    return f"{year}1231"


# ---- API 响应解析 ----

def _df_to_records(df: pd.DataFrame, column_map: dict) -> list[dict]:
    """将 DataFrame 转为 dict 列表，列名映射 + NaN→None"""
    if df is None or df.empty:
        return None
    df = df.rename(columns=column_map)
    cols = list(column_map.values())
    df = df[cols].copy()
    df = df.where(df.notna(), None)
    return df.to_dict(orient="records")


def parse_overview(df: pd.DataFrame) -> dict | None:
    """解析 fund_overview_em 返回值"""
    if df is None or df.empty:
        return None
    row = df.iloc[0]
    return {
        "fund_full_name": str(row.get("基金全称", "")) if row.get("基金全称") is not None else None,
        "fund_name": str(row.get("基金简称", "")) if row.get("基金简称") is not None else None,
        "fund_code": str(row.get("基金代码", "")) if row.get("基金代码") is not None else None,
        "fund_type": str(row.get("基金类型", "")) if row.get("基金类型") is not None else None,
        "issue_date": str(row.get("发行日期", "")) if row.get("发行日期") is not None else None,
        "establishment_date": str(row.get("成立日期/规模", "")) if row.get("成立日期/规模") is not None else None,
        "establishment_scale": str(row.get("成立日期/规模", "")) if row.get("成立日期/规模") is not None else None,
        "net_asset_value": str(row.get("净资产规模", "")) if row.get("净资产规模") is not None else None,
        "share_size": str(row.get("份额规模", "")) if row.get("份额规模") is not None else None,
        "fund_manager": str(row.get("基金管理人", "")) if row.get("基金管理人") is not None else None,
        "fund_custodian": str(row.get("基金托管人", "")) if row.get("基金托管人") is not None else None,
        "portfolio_manager": str(row.get("基金经理人", "")) if row.get("基金经理人") is not None else None,
        "dividends_since_inception": str(row.get("成立来分红", "")) if row.get("成立来分红") is not None else None,
        "management_fee_rate": str(row.get("管理费率", "")) if row.get("管理费率") is not None else None,
        "custodian_fee_rate": str(row.get("托管费率", "")) if row.get("托管费率") is not None else None,
        "sales_service_fee_rate": str(row.get("销售服务费率", "")) if row.get("销售服务费率") is not None else None,
        "max_subscription_fee_rate": str(row.get("最高认购费率", "")) if row.get("最高认购费率") is not None else None,
        "benchmark": str(row.get("业绩比较基准", "")) if row.get("业绩比较基准") is not None else None,
        "tracking_target": str(row.get("跟踪标的", "")) if row.get("跟踪标的") is not None else None,
    }


def parse_nav_history(df: pd.DataFrame) -> list[dict] | None:
    """解析 fund_open_fund_info_em 返回值"""
    if df is None or df.empty:
        return None
    df = df.copy()
    df = df.where(df.notna(), None)
    records = []
    for _, row in df.iterrows():
        d = row.get("净值日期")
        date_str = ""
        if d is not None:
            if hasattr(d, "strftime"):
                date_str = d.strftime("%Y-%m-%d")
            else:
                date_str = str(d)
        val = row.get("单位净值")
        ret = row.get("日增长率")
        records.append({
            "date": date_str,
            "unit_net_value": float(val) if val is not None and not (isinstance(val, float) and np.isnan(val)) else None,
            "daily_return": float(ret) if ret is not None and not (isinstance(ret, float) and np.isnan(ret)) else None,
        })
    return records


def parse_risk_analysis(df: pd.DataFrame) -> list[dict] | None:
    """解析 fund_individual_analysis_xq 返回值"""
    return _df_to_records(df, {
        "周期": "period",
        "较同类风险收益比": "risk_return_rank",
        "较同类抗风险波动": "risk_resilience_rank",
        "年化波动率": "annualized_volatility",
        "年化夏普比率": "annualized_sharpe",
        "最大回撤": "max_drawdown",
    })


def parse_profit_probability(df: pd.DataFrame) -> list[dict] | None:
    """解析 fund_individual_profit_probability_xq 返回值"""
    return _df_to_records(df, {
        "持有时长": "holding_period",
        "盈利概率": "profit_probability",
        "平均收益": "avg_return",
    })


def parse_asset_allocation(df: pd.DataFrame) -> list[dict] | None:
    """解析 fund_individual_detail_hold_xq 返回值"""
    return _df_to_records(df, {
        "资产类型": "asset_type",
        "仓位占比": "allocation_ratio",
    })


def parse_fee_and_rules(
    fee_status_df: pd.DataFrame,
    fee_op_cost_df: pd.DataFrame,
    fee_redemption_df: pd.DataFrame,
    trade_rules_df: pd.DataFrame,
) -> dict | None:
    """解析 fund_fee_em（3个indicator）+ fund_individual_detail_info_xq"""
    # 检查是否全部为空
    all_empty = all(
        df is None or df.empty
        for df in [fee_status_df, fee_op_cost_df, fee_redemption_df, trade_rules_df]
    )
    if all_empty:
        return None

    # 解析交易状态
    status = {"purchase_status": None, "redemption_status": None, "auto_invest_status": None}
    if fee_status_df is not None and not fee_status_df.empty:
        for _, row in fee_status_df.iterrows():
            key = str(row.iloc[0]) if row.iloc[0] is not None else ""
            val = str(row.iloc[1]) if row.iloc[1] is not None else ""
            if "申购状态" in key:
                status["purchase_status"] = val
            elif "赎回状态" in key:
                status["redemption_status"] = val
            elif "定投状态" in key:
                status["auto_invest_status"] = val

    # 解析运作费用
    op_cost = {"management_fee_rate": None, "custodian_fee_rate": None, "sales_service_fee_rate": None}
    if fee_op_cost_df is not None and not fee_op_cost_df.empty:
        for _, row in fee_op_cost_df.iterrows():
            key = str(row.iloc[0]) if row.iloc[0] is not None else ""
            val = str(row.iloc[1]) if row.iloc[1] is not None else ""
            if "管理费率" in key:
                op_cost["management_fee_rate"] = val
            elif "托管费率" in key:
                op_cost["custodian_fee_rate"] = val
            elif "销售服务费率" in key:
                op_cost["sales_service_fee_rate"] = val

    # 解析赎回费率表
    redemption_table = None
    if fee_redemption_df is not None and not fee_redemption_df.empty:
        df = fee_redemption_df.copy()
        df = df.where(df.notna(), None)
        redemption_table = []
        for _, row in df.iterrows():
            redemption_table.append({
                "period": str(row["适用期限"]) if row["适用期限"] is not None else None,
                "rate": str(row["赎回费率"]) if row["赎回费率"] is not None else None,
            })

    # 解析买入/卖出规则
    purchase_rules = []
    redemption_rules = []
    other_fees = []
    if trade_rules_df is not None and not trade_rules_df.empty:
        for _, row in trade_rules_df.iterrows():
            fee_type = str(row["费用类型"]) if row["费用类型"] is not None else ""
            name = str(row["条件或名称"]) if row["条件或名称"] is not None else ""
            fee = row["费用"]
            fee_str = str(fee) if fee is not None else None
            if "买入规则" in fee_type:
                purchase_rules.append({
                    "amount_range": name,
                    "fee_rate": fee_str + "%" if fee_str else None,
                })
            elif "卖出规则" in fee_type:
                redemption_rules.append({
                    "holding_period": name,
                    "fee_rate": fee_str + "%" if fee_str else None,
                })
            elif "其他费用" in fee_type:
                other_fees.append({
                    "name": name,
                    "rate": fee_str + "%" if fee_str else None,
                })

    return {
        "purchase_status": status["purchase_status"],
        "redemption_status": status["redemption_status"],
        "auto_invest_status": status["auto_invest_status"],
        "management_fee_rate": op_cost["management_fee_rate"],
        "custodian_fee_rate": op_cost["custodian_fee_rate"],
        "sales_service_fee_rate": op_cost["sales_service_fee_rate"],
        "redemption_fee_table": redemption_table or [],
        "purchase_rules": purchase_rules,
        "redemption_rules": redemption_rules,
        "other_fees": other_fees,
    }


def parse_stock_holdings(df: pd.DataFrame) -> list[dict] | None:
    """解析 fund_portfolio_hold_em，仅保留最新季度数据"""
    if df is None or df.empty:
        return None
    # 取最新季度（按 quarter 分组，取行数最多的）
    if "季度" in df.columns:
        quarter_counts = df.groupby("季度").size()
        latest_quarter = quarter_counts.idxmax()
        df = df[df["季度"] == latest_quarter]
    return _df_to_records(df, {
        "股票代码": "stock_code",
        "股票名称": "stock_name",
        "占净值比例": "net_value_ratio",
        "持股数": "shares_held",
        "持仓市值": "market_value",
        "季度": "quarter",
    })


def parse_bond_holdings(df: pd.DataFrame) -> list[dict] | None:
    """解析 fund_portfolio_bond_hold_em，仅保留最新季度数据"""
    if df is None or df.empty:
        return None
    if "季度" in df.columns:
        quarter_counts = df.groupby("季度").size()
        if len(quarter_counts) > 0:
            latest_quarter = quarter_counts.idxmax()
            df = df[df["季度"] == latest_quarter]
    return _df_to_records(df, {
        "债券代码": "bond_code",
        "债券名称": "bond_name",
        "占净值比例": "net_value_ratio",
        "持仓市值": "market_value",
        "季度": "quarter",
    })


def parse_industry_allocation(df: pd.DataFrame) -> list[dict] | None:
    """解析 fund_portfolio_industry_allocation_em 返回值"""
    return _df_to_records(df, {
        "行业类别": "industry_name",
        "占净值比例": "net_value_ratio",
        "市值": "market_value",
        "截止时间": "report_date",
    })


# ---- 聚合 ----

def aggregate_result(
    code: str,
    overview: dict | None,
    nav: list[dict] | None,
    risk: list[dict] | None,
    profit: list[dict] | None,
    asset_alloc: list[dict] | None,
    fee: dict | None,
    stock_holdings: list[dict] | None,
    bond_holdings: list[dict] | None,
    industry: list[dict] | None,
    errors: list[dict],
) -> dict:
    """聚合所有 API 结果为一个顶层 JSON 对象"""
    now = datetime.now()
    ref_date = now.date()

    return {
        "meta": {
            "fund_code": code,
            "fetch_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "portfolio_year": str(determine_portfolio_year(ref_date)),
            "portfolio_date": determine_hold_date(ref_date),
            "nav_period": "成立来",
            "nav_indicator": "单位净值走势",
        },
        "overview": overview,
        "nav_history": nav,
        "risk_analysis": risk,
        "profit_probability": profit,
        "asset_allocation": asset_alloc,
        "fee_and_rules": fee,
        "stock_holdings": stock_holdings,
        "bond_holdings": bond_holdings,
        "industry_allocation": industry,
        "errors": errors,
    }


# ---- API 调用包装 ----

def _fetch_with_retry(fn, section: str, api_name: str, *args, **kwargs):
    """调用单个 API，失败时返回 error dict。成功返回 (section, data, None)。"""
    try:
        import akshare as ak
        func = getattr(ak, fn)
        df = func(*args, **kwargs)
        if df is None or (hasattr(df, "empty") and df.empty):
            return section, None, {
                "section": section,
                "error": "API returned empty data",
                "api": api_name,
            }
        return section, df, None
    except Exception as e:
        return section, None, {
            "section": section,
            "error": str(e),
            "api": api_name,
        }


# ---- 主函数 ----

def main() -> None:
    parser = argparse.ArgumentParser(description="公募基金综合信息查询")
    parser.add_argument("--code", required=True, help="6位基金代码，如 000001")
    args = parser.parse_args()

    # 校验参数
    try:
        validate_code(args.code)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(2)

    code = args.code
    ref_date = date.today()
    portfolio_year = determine_portfolio_year(ref_date)
    hold_date = determine_hold_date(ref_date)

    print(f"[INFO] 正在获取基金 {code} 的综合信息...", file=sys.stderr)
    print(f"[INFO] 持仓查询年份: {portfolio_year}, 配置查询日期: {hold_date}", file=sys.stderr)
    print(f"[INFO] 并发调用 API (5 workers)...", file=sys.stderr)

    # 定义 API 调用列表
    api_calls = [
        ("fund_overview_em", "overview", code),
        ("fund_open_fund_info_em", "nav_history", code, "单位净值走势", "成立来"),
        ("fund_individual_analysis_xq", "risk_analysis", code),
        ("fund_individual_profit_probability_xq", "profit_probability", code),
        ("fund_individual_detail_hold_xq", "asset_allocation", code, hold_date),
        # fee_and_rules 需要 4 个 API，单独处理
        ("fund_portfolio_hold_em", "stock_holdings", code, str(portfolio_year)),
        ("fund_portfolio_bond_hold_em", "bond_holdings", code, str(portfolio_year)),
        ("fund_portfolio_industry_allocation_em", "industry_allocation", code, str(portfolio_year)),
    ]

    import akshare as ak

    results = {}
    all_errors = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for fn_name, section, *args in api_calls:
            jitter = random.uniform(0.1, 0.3)
            time.sleep(jitter)
            futures[executor.submit(_fetch_with_retry, fn_name, section, fn_name, *args)] = section

        # fee_and_rules 需要 4 个 API
        fee_futures = {}
        fee_indicators = [
            ("fund_fee_em", "fee_status", code, "交易状态"),
            ("fund_fee_em", "fee_op_cost", code, "运作费用"),
            ("fund_fee_em", "fee_redemption", code, "赎回费率"),
            ("fund_individual_detail_info_xq", "fee_trade_rules", code),
        ]
        for fn_name, sub_key, *args in fee_indicators:
            time.sleep(random.uniform(0.1, 0.3))
            fee_futures[executor.submit(_fetch_with_retry, fn_name, sub_key, fn_name, *args)] = sub_key

        # 收集主 API 结果
        for future in as_completed(futures):
            section = futures[future]
            sec, data, error = future.result()
            if error:
                all_errors.append(error)
            results[sec] = data

        # 收集 fee API 结果
        fee_results = {}
        for future in as_completed(fee_futures):
            sub_key = fee_futures[future]
            sec, data, error = future.result()
            if error:
                all_errors.append({"section": "fee_and_rules", **error})
            fee_results[sub_key] = data

    # 解析各 API 结果
    overview = parse_overview(results.get("overview"))
    print(f"[INFO] overview: {'成功' if overview else '失败'}", file=sys.stderr)

    nav = parse_nav_history(results.get("nav_history"))
    nav_count = len(nav) if nav else 0
    print(f"[INFO] nav_history: {'成功' if nav else '失败'}{' (' + str(nav_count) + ' 条)' if nav_count else ''}", file=sys.stderr)

    risk = parse_risk_analysis(results.get("risk_analysis"))
    print(f"[INFO] risk_analysis: {'成功' if risk else '失败'}", file=sys.stderr)

    profit = parse_profit_probability(results.get("profit_probability"))
    print(f"[INFO] profit_probability: {'成功' if profit else '失败'}", file=sys.stderr)

    asset_alloc = parse_asset_allocation(results.get("asset_allocation"))
    print(f"[INFO] asset_allocation: {'成功' if asset_alloc else '失败'}", file=sys.stderr)

    fee = parse_fee_and_rules(
        fee_results.get("fee_status"),
        fee_results.get("fee_op_cost"),
        fee_results.get("fee_redemption"),
        fee_results.get("fee_trade_rules"),
    )
    print(f"[INFO] fee_and_rules: {'成功' if fee else '失败'}", file=sys.stderr)

    stock = parse_stock_holdings(results.get("stock_holdings"))
    stock_quarter = stock[0]["quarter"] if stock and stock[0].get("quarter") else ""
    stock_count = len(stock) if stock else 0
    print(f"[INFO] stock_holdings: {'成功' if stock else '失败'}{' (' + str(stock_count) + ' 条, ' + stock_quarter + ')' if stock_count else ''}", file=sys.stderr)

    bond = parse_bond_holdings(results.get("bond_holdings"))
    bond_count = len(bond) if bond else 0
    print(f"[INFO] bond_holdings: {'成功' if bond else '失败'}{' (' + str(bond_count) + ' 条)' if bond_count else ''}", file=sys.stderr)

    industry = parse_industry_allocation(results.get("industry_allocation"))
    print(f"[INFO] industry_allocation: {'成功' if industry else '失败'}", file=sys.stderr)

    # 聚合输出
    output = aggregate_result(
        code=code,
        overview=overview,
        nav=nav,
        risk=risk,
        profit=profit,
        asset_alloc=asset_alloc,
        fee=fee,
        stock_holdings=stock,
        bond_holdings=bond,
        industry=industry,
        errors=all_errors,
    )

    total_sections = len(SECTION_ORDER)
    failed = len([s for s in SECTION_ORDER if output[s] is None])
    print(f"[INFO] 完成: {total_sections - failed}/{total_sections} 成功, {len(all_errors)} 错误", file=sys.stderr)

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    print()  # 末尾换行

    # exit code
    if all(output[s] is None for s in SECTION_ORDER):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **步骤 2：运行单元测试验证全部通过**

```bash
uv run pytest akshare-fund-info/scripts/tests/test_fund_info.py -v
```
预期：全部 PASS (约 32+ tests)

- [ ] **步骤 3：Commit**

```bash
git add akshare-fund-info/
git commit -m "feat: implement fund-info core logic with TDD

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 4：集成测试

**文件：**
- 创建：`akshare-fund-info/scripts/tests/test_integration.py`

- [ ] **步骤 1：编写集成测试**

在 `akshare-fund-info/scripts/tests/test_integration.py` 中：

```python
"""集成测试 — 需要真实网络，标记为 integration"""
import os, sys, json, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "fund_info.py")


def run_cli(*args):
    result = subprocess.run(
        [sys.executable, SCRIPT_PATH] + list(args),
        capture_output=True, text=True,
        timeout=60,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.mark.integration
class TestRealAPI:
    def test_valid_code_returns_all_sections(self):
        rc, stdout, stderr = run_cli("--code", "000001")
        assert rc == 0
        data = json.loads(stdout)
        assert "meta" in data
        assert "overview" in data
        assert "nav_history" in data
        assert "risk_analysis" in data
        assert "profit_probability" in data
        assert "asset_allocation" in data
        assert "fee_and_rules" in data
        assert "stock_holdings" in data
        assert "bond_holdings" in data
        assert "industry_allocation" in data
        assert "errors" in data

    def test_overview_has_expected_fields(self):
        rc, stdout, stderr = run_cli("--code", "000001")
        data = json.loads(stdout)
        overview = data["overview"]
        assert overview is not None
        assert "fund_full_name" in overview
        assert "fund_type" in overview
        assert "fund_manager" in overview
        assert "benchmark" in overview

    def test_nav_history_is_list(self):
        rc, stdout, stderr = run_cli("--code", "000001")
        data = json.loads(stdout)
        nav = data["nav_history"]
        assert isinstance(nav, list)
        assert len(nav) > 100
        # 检查第一条记录结构
        first = nav[0]
        assert "date" in first
        assert "unit_net_value" in first
        assert "daily_return" in first

    def test_risk_analysis_has_three_periods(self):
        rc, stdout, stderr = run_cli("--code", "000001")
        data = json.loads(stdout)
        risk = data["risk_analysis"]
        assert risk is not None
        assert len(risk) == 3

    def test_fee_and_rules_structure(self):
        rc, stdout, stderr = run_cli("--code", "000001")
        data = json.loads(stdout)
        fee = data["fee_and_rules"]
        assert fee is not None
        assert "purchase_status" in fee
        assert "redemption_fee_table" in fee
        assert "purchase_rules" in fee
        assert "redemption_rules" in fee

    def test_stock_holdings_structure(self):
        rc, stdout, stderr = run_cli("--code", "000001")
        data = json.loads(stdout)
        stock = data["stock_holdings"]
        assert stock is not None
        assert isinstance(stock, list)
        if len(stock) > 0:
            assert "stock_code" in stock[0]
            assert "net_value_ratio" in stock[0]


@pytest.mark.integration
class TestCLIErrors:
    def test_missing_code_exit_code_2(self):
        rc, stdout, stderr = run_cli("--code", "12345")
        assert rc == 2

    def test_non_digit_code_exit_code_2(self):
        rc, stdout, stderr = run_cli("--code", "abcdef")
        assert rc == 2
```

- [ ] **步骤 2：运行集成测试**

```bash
uv run pytest akshare-fund-info/scripts/tests/test_integration.py -v -m integration
```
预期：全部 PASS

- [ ] **步骤 3：Commit**

```bash
git add akshare-fund-info/scripts/tests/test_integration.py
git commit -m "test: add integration tests for fund-info skill

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 5：最终验证

- [ ] **步骤 1：运行所有单元测试**

```bash
uv run pytest akshare-fund-info/scripts/tests/test_fund_info.py -v
```
预期：全部 PASS

- [ ] **步骤 2：运行集成测试**

```bash
uv run pytest akshare-fund-info/scripts/tests/test_integration.py -v -m integration
```
预期：全部 PASS

- [ ] **步骤 3：手动验证 CLI**

```bash
uv run python akshare-fund-info/scripts/fund_info.py --code 000001 | python -m json.tool | head -80
uv run python akshare-fund-info/scripts/fund_info.py --code 015641 | python -m json.tool | head -80
```
预期：完整 JSON 输出

- [ ] **步骤 4：最终 Commit**

```bash
git add -A
git commit -m "chore: finalize akshare-fund-info implementation

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
akshare-fund-info/
  SKILL.md
  scripts/
    __init__.py
    fund_info.py
    tests/
      __init__.py
      test_fund_info.py
      test_integration.py
```

**运行方式：**
```bash
uv pip install akshare pandas
uv run python akshare-fund-info/scripts/fund_info.py --code 000001
uv run pytest akshare-fund-info/scripts/tests/ -v
```
