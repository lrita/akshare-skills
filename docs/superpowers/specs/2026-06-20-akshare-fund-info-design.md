# 公募基金综合信息 — 设计规格

## 概述

基于 akshare 的多个基金相关 API，输入单个基金代码（6 位），并发获取基本概况、净值走势、风险分析、盈利概率、费率规则、股票持仓、债券持仓、行业配置等全部维度数据，聚合为结构化 JSON 输出，供 AI Agent 进行基金分析。

## CLI 接口

```bash
uv run python scripts/fund_info.py --code 000001
```

- JSON 输出到 stdout，日志/进度到 stderr
- 无缓存，每次实时查询
- exit code: 0 成功, 1 部分失败/无数据, 2 参数错误

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `--code` | str | (必需) | 6 位基金代码，如 `000001` |

**合法性校验**：必须为 6 位纯数字字符串。

## 核心流程

```
main()
  ├── parse_args()                                      # argparse 解析 --code
  ├── validate_code()                                    # 校验基金代码格式（6 位数字）
  ├── determine_year/date params                         # 根据当前日期推断持仓查询年份
  │     └── 若当前月 > 4月，取当前年份-1；否则取当前年份-2
  ├── 并发调用多个 API (ThreadPoolExecutor, 5 workers)
  │     ├── fund_overview_em(code)
  │     ├── fund_open_fund_info_em(code, "单位净值走势", "成立来")
  │     ├── fund_individual_analysis_xq(code)
  │     ├── fund_individual_profit_probability_xq(code)
  │     ├── fund_individual_detail_hold_xq(code, YYYY1231)
  │     ├── fund_fee_em(code, "交易状态") + fund_fee_em(code, "运作费用") + fund_fee_em(code, "赎回费率")
  │     ├── fund_individual_detail_info_xq(code)
  │     ├── fund_portfolio_hold_em(code, year)
  │     ├── fund_portfolio_bond_hold_em(code, year)
  │     └── fund_portfolio_industry_allocation_em(code, year)
  ├── 聚合各 API 结果 → 结构化 dict
  │     └── 失败 API 记录到 errors，对应 section 为 null
  ├── NaN → null 转换
  └── json.dump 到 stdout
```

### 年份与日期推断

- **`fund_individual_detail_hold_xq`** 的 `date` 参数：用 `YYYYMMDD` 格式，取最近一个 Q4 的 12 月 31 日（如当前 2026 年 6 月 20 日 → `20251231`）
- **持仓/行业配置** 的 `date` 参数（年份）：若当前日期已过当年 Q1 披露截止日（4 月 22 日），取当前年份 - 1；否则取当前年份 - 2。例如：
  - 当前日期 2026 年 6 月 20 日 → 已过 4/22 → 取 `2025`
  - 当前日期 2026 年 3 月 1 日 → 未过 4/22 → 取 `2024`

### 并发与反拦截

- `ThreadPoolExecutor(max_workers=5)`
- 每个请求前 random jitter 0.1-0.3s

## 输出格式

### 输出字段总览

输出为一个顶层 JSON 对象，包含 `meta`、9 个数据 section、`errors`。

### meta

| 字段 | 类型 | 说明 |
|---|---|---|
| `fund_code` | string | 查询的基金代码 |
| `fetch_time` | string | 数据获取时间 (YYYY-MM-DD HH:MM:SS) |
| `portfolio_year` | string | 持仓查询年份（用于 stock/bond/industry） |
| `portfolio_date` | string | 资产配置查询日期 (YYYYMMDD) |
| `nav_period` | string | 净值走势时间段（固定 "成立来"） |
| `nav_indicator` | string | 净值走势指标（固定 "单位净值走势"） |

### overview（API: fund_overview_em）

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `fund_full_name` | string | - | 基金全称 |
| `fund_name` | string | - | 基金简称 |
| `fund_code` | string | - | 基金代码 |
| `fund_type` | string | - | 基金类型（股票型/混合型等） |
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

注：`fund_overview_em` 返回的费率、规模字段包含文本描述（如"1.20%（每年）"、"3.97亿元（截止至：2026年03月31日）"），为保留完整语义直接输出原始文本。

### nav_history（API: fund_open_fund_info_em）

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `date` | string | - | 净值日期 (YYYY-MM-DD) |
| `unit_net_value` | float/null | 元 | 单位净值 |
| `daily_return` | float/null | % | 日增长率 |

- 固定 period = "成立来"，indicator = "单位净值走势"

### risk_analysis（API: fund_individual_analysis_xq）

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `period` | string | - | 周期（近1年/近3年/近5年） |
| `risk_return_rank` | int/null | 百分位 | 较同类风险收益比（0-100，越高越好） |
| `risk_resilience_rank` | int/null | 百分位 | 较同类抗风险波动（0-100，越高越好） |
| `annualized_volatility` | float/null | % | 年化波动率 |
| `annualized_sharpe` | float/null | - | 年化夏普比率 |
| `max_drawdown` | float/null | % | 最大回撤 |

### profit_probability（API: fund_individual_profit_probability_xq）

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `holding_period` | string | - | 持有时长（满6个月/满1年/满2年/满3年） |
| `profit_probability` | float/null | % | 盈利概率 |
| `avg_return` | float/null | % | 平均收益 |

### asset_allocation（API: fund_individual_detail_hold_xq）

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `asset_type` | string | - | 资产类型（股票/现金/债券/其他） |
| `allocation_ratio` | float/null | % | 仓位占比 |

### fee_and_rules（API: fund_fee_em + fund_individual_detail_info_xq）

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `purchase_status` | string | - | 申购状态（开放申购/暂停申购等） |
| `redemption_status` | string | - | 赎回状态 |
| `auto_invest_status` | string | - | 定投状态（支持/不支持） |
| `management_fee_rate` | string | - | 管理费率（每年） |
| `custodian_fee_rate` | string | - | 托管费率（每年） |
| `sales_service_fee_rate` | string | - | 销售服务费率（每年） |
| `redemption_fee_table` | array | - | 赎回费率表：[{period: string, rate: string}]，rate 单位为 % |
| `purchase_rules` | array | - | 买入规则：[{amount_range: string, fee_rate: string, fee: string}] |
| `redemption_rules` | array | - | 卖出规则：[{holding_period: string, fee_rate: string}] |
| `other_fees` | array | - | 其他费用：[{name: string, rate: string}] |

### stock_holdings（API: fund_portfolio_hold_em）

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `stock_code` | string | - | 股票代码 |
| `stock_name` | string | - | 股票名称 |
| `net_value_ratio` | float/null | % | 占净值比例 |
| `shares_held` | float/null | 万股 | 持股数 |
| `market_value` | float/null | 万元 | 持仓市值 |
| `quarter` | string | - | 报告期（如 "2025年4季度股票投资明细"） |

- 默认取该年份中最新季度的数据（按 quarter 列过滤，取行数最多的季度）。注意此 API 返回多季度数据，取最新可用季度。

### bond_holdings（API: fund_portfolio_bond_hold_em）

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `bond_code` | string | - | 债券代码 |
| `bond_name` | string | - | 债券名称 |
| `net_value_ratio` | float/null | % | 占净值比例 |
| `market_value` | float/null | 万元 | 持仓市值 |
| `quarter` | string | - | 报告期 |

- 默认取最新季度数据。

### industry_allocation（API: fund_portfolio_industry_allocation_em）

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

- NaN 值统一输出为 JSON `null`
- `nav_history` 数组为全量历史数据（成立来全部交易日），通常数千条；AI Agent 可根据需要进行截取或统计

### 完整输出示例

```json
{
  "meta": {
    "fund_code": "000001",
    "fetch_time": "2026-06-20 15:30:00",
    "portfolio_year": "2025",
    "portfolio_date": "20251231",
    "nav_period": "成立来",
    "nav_indicator": "单位净值走势"
  },
  "overview": {
    "fund_full_name": "银华数字经济股票型发起式证券投资基金",
    "fund_name": "银华数字经济股票发起式A",
    "fund_code": "015641",
    "fund_type": "股票型",
    "issue_date": "2022-05-12",
    "establishment_date": "2022-05-20",
    "establishment_scale": "0.137亿份",
    "net_asset_value": "3.97亿元（截止至：2026年03月31日）",
    "share_size": "2.2465亿份（截止至：2026年03月31日）",
    "fund_manager": "银华基金",
    "fund_custodian": "浦发银行",
    "portfolio_manager": "王晓川",
    "dividends_since_inception": "每份累计0.00元（0次）",
    "management_fee_rate": "1.20%（每年）",
    "custodian_fee_rate": "0.20%（每年）",
    "sales_service_fee_rate": "0.00%（每年）",
    "max_subscription_fee_rate": "1.20%（前端）",
    "benchmark": "中证数字经济主题全收益指数收益率*60%+...",
    "tracking_target": "该基金无跟踪标的"
  },
  "nav_history": [
    {"date": "2001-12-18", "unit_net_value": 1.0, "daily_return": 0.0}
  ],
  "risk_analysis": [
    {"period": "近1年", "risk_return_rank": 73, "risk_resilience_rank": 39, "annualized_volatility": 26.71, "annualized_sharpe": 2.79, "max_drawdown": 15.89}
  ],
  "profit_probability": [
    {"holding_period": "满6个月", "profit_probability": 55.0, "avg_return": 6.15}
  ],
  "asset_allocation": [
    {"asset_type": "股票", "allocation_ratio": 51.95}
  ],
  "fee_and_rules": {
    "purchase_status": "开放申购",
    "redemption_status": "开放赎回",
    "auto_invest_status": "支持",
    "management_fee_rate": "1.20%（每年）",
    "custodian_fee_rate": "0.20%（每年）",
    "sales_service_fee_rate": "0.00%（每年）",
    "redemption_fee_table": [
      {"period": "小于7天", "rate": "1.50%"}
    ],
    "purchase_rules": [
      {"amount_range": "0.0万<买入金额<100.0万", "fee_rate": "1.5%", "fee": "1.5"}
    ],
    "redemption_rules": [
      {"holding_period": "0.0天<持有期限<7.0天", "fee_rate": "1.5%"}
    ],
    "other_fees": [
      {"name": "基金管理费", "rate": "1.2%"}
    ]
  },
  "stock_holdings": [
    {"stock_code": "002025", "stock_name": "航天电器", "net_value_ratio": 3.46, "shares_held": 209.92, "market_value": 7947.67, "quarter": "2024年1季度股票投资明细"}
  ],
  "bond_holdings": [
    {"bond_code": "230304", "bond_name": "23进出04", "net_value_ratio": 4.59, "market_value": 11114.27, "quarter": "2023年4季度债券投资明细"}
  ],
  "industry_allocation": [
    {"industry_name": "制造业", "net_value_ratio": 56.58, "market_value": 136966.39, "report_date": "2023-12-31"}
  ],
  "errors": []
}
```

## stderr 日志格式

```
[INFO] 正在获取基金 000001 的综合信息...
[INFO] 并发调用 API (5 workers)...
[INFO] overview: 成功
[INFO] nav_history: 成功 (5945 条)
[INFO] risk_analysis: 成功
[INFO] profit_probability: 成功
[INFO] asset_allocation: 成功
[INFO] fee_and_rules: 成功
[INFO] stock_holdings: 成功 (15 条, 2024年1季度)
[INFO] bond_holdings: 成功 (5 条)
[INFO] industry_allocation: 成功
[INFO] 完成: 9/9 成功, 0 失败
```

## 错误处理

| 场景 | 处理 |
|---|---|
| `--code` 格式非法（非 6 位数字） | stderr 提示，exit code 2 |
| 单个 API 调用失败（超时/网络/返回空） | 记录到 `errors` 数组，该 section 为 `null`，继续处理其他 API |
| 单个 API 返回空 DataFrame | 该 section 输出为 `null`，不报错 |
| 全部 API 调用失败 | stderr 输出错误汇总，exit code 1 |
| `fund_portfolio_hold_em` 无该年份数据 | 该 section 为 `null`，不报错 |

## 文件结构

```
akshare-fund-info/
├── SKILL.md
└── scripts/
    ├── __init__.py
    ├── fund_info.py
    └── tests/
        ├── __init__.py
        ├── test_fund_info.py
        └── test_integration.py
```

## 测试策略

### 单元测试（mock 全部 akshare API）

- 基金代码校验：合法 6 位通过，非 6 位/含字母拒绝
- 全部 API 成功时，聚合 JSON 结构正确（含所有 9 个 section）
- 部分 API 失败时，对应 section 为 `null`，errors 数组记录正确
- NaN → null 转换正确
- 日期/年份推断：不同月份的正确推断值
- 持仓季度筛选：多季度数据中取最新季度
- 费率解析：fund_fee_em 多 indicator 调用的正确聚合

### 集成测试（真实 API）

- 真实基金代码调用成功，输出 JSON 可解析
- 结构完整（含 all 9 sections）
- exit code 正确
- 无效代码场景

## 依赖

```bash
uv pip install akshare pandas
```

## 不做的功能

- 无缓存（每次实时查询）
- 不支持多基金批量查询（仅单基金）
- 不支持自选维度（始终返回全部 9 个 section）
- NAV 走势不支持缩放到短周期（始终成立来全量）
- 无 `--output` 参数切换格式（固定 JSON 对象输出）

## 使用示例

```bash
# 查询基金 000001 的完整信息
uv run python scripts/fund_info.py --code 000001

# 查询基金 015641
uv run python scripts/fund_info.py --code 015641
```
