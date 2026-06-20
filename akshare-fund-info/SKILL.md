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
| `nav_period` | string | 净值时间段（固定 "成立来"） |
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
