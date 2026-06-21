# 个股基本面数据 Skill 设计规格

## 概述

基于 akshare API + 原生 HTTP 请求，为 AI 分析 A 股个股基本面提供一站式数据支持。输入股票代码，一次性拉取基础信息、财务报表、盈利预测、主营构成、风险信号、事件公告和机构动向 7 个维度，按 5 个板块输出结构化 JSON。

## 架构

```
akshare-stock-fundamentals/
├── SKILL.md                          # skill 定义
└── scripts/
    ├── fetch_fundamentals.py         # CLI 入口 (argparse, 板块调度)
    ├── data_sources.py               # 数据源层 (akshare API + 原生 HTTP 请求)
    └── tests/
        ├── __init__.py
        ├── test_data_sources.py      # 数据源单元测试 (mock)
        └── test_integration.py       # 端到端集成测试
```

**数据流向**：

```
CLI (argparse)
    │
    ▼
fetch_fundamentals.py
    │  按板块顺序调用
    ├── basic_info     → tencent_quote (HTTP) → eastmoney_search (HTTP) → stock_add_stock
    ├── fundamentals   → abstract×2 + benefit + debt + cash → profit_forecast×4 → zygc_em
    ├── risk_signals   → stock_dzjy_mrmx → 2×限售解禁 → pledge_ratio_detail_em
    ├── events         → stock_individual_notice_report
    └── institutional  → stock_jgdy_tj_em (逐日过滤)
    │
    ▼
结构化 JSON (stdout)
```

**依赖**：`akshare`, `pandas`，无其他第三方库。

---

## CLI 接口

```bash
uv run python scripts/fetch_fundamentals.py --symbol 600183 [--date 20260621] [--output result.json]
```

### 参数说明

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--symbol` | 是 | - | 股票代码，纯数字，如 600183 |
| `--date` | 否 | 今天 | 基准日期 YYYYMMDD，用于所有时间范围计算 |
| `--output` | 否 | stdout | 输出 JSON 文件路径 |

### exit code

| code | 含义 |
|------|------|
| 0 | 成功（全部数据源成功或部分失败） |
| 1 | 全部数据源失败 |
| 2 | 参数错误（symbol 格式非法等） |

---

## 速率限制

所有调用（含 akshare API 和原生 HTTP）受全局速率限制，**每分钟最多 10 次**。调用模式为顺序执行，调用间隔随机加入 0.3-1.0 秒抖动。

## 错误处理

- 单个数据源失败：记录到 `errors` 数组，对应 section 子字段置为 `null`，不阻断其他数据源
- 全部数据源失败：exit 1，仅输出 errors
- 参数错误：exit 2，stderr 输出原因
- 反爬虫拦截（同花顺 API 403）：记录 `[BLOCKED]` 错误，跳过该 API 继续其他调用

## 缓存策略

无缓存，实时查询。

---

## 输出格式

### 总结构

```json
{
  "symbol": "600183",
  "stock_name": "生益科技",
  "fetch_time": "2026-06-21 15:30:00",
  "sections": {
    "basic_info": { ... },
    "fundamentals": { ... },
    "risk_signals": { ... },
    "events": { ... },
    "institutional": { ... }
  },
  "errors": [
    {"section": "risk_signals", "source": "stock_dzjy_mrmx", "error": "timeout"}
  ]
}
```

---

### 📌 基础信息 (basic_info)

**数据源**: 腾讯行情 HTTP + 东财搜索 HTTP + stock_add_stock (共 3 次调用)

- `tencent_quote`: 原生 HTTP 请求 `qt.gtimg.cn`，GBK 解码，提取交易行情 + 估值指标
- `eastmoney_search`: 模拟 XMLHttpRequest 调用 `data.eastmoney.com/dataapi/search/company`，Referer 伪装，提取公司档案
- `stock_add_stock`: 增发记录，仅保留最近 2 年

```json
{
  "basic_info": {
    "quote": {
      "name": "生益科技",
      "price": 183.87,
      "change_pct": 2.06,
      "change_amt": 3.72,
      "open": 178.50,
      "high": 187.35,
      "low": 176.73,
      "volume_hands": 798770,
      "amount_wan": 1460514,
      "turnover_pct": 3.34,
      "amplitude_pct": 5.90,
      "vol_ratio": 0.90,
      "avg_price": 182.85,
      "limit_up": 198.17,
      "limit_down": 162.14,
      "pe_ttm": 113.69,
      "pe_dynamic": 96.41,
      "pb": 27.94,
      "total_mcap_yi": 4466.42,
      "float_mcap_yi": 4402.77,
      "update_time": "20260618161425",
      "outer_disc_hands": 419569,
      "inner_disc_hands": 379201
    },
    "profile": {
      "security_short_name": "生益科技",
      "listing_date": "1998-10-28",
      "total_capital": 2429119230,
      "circulation_capital": 2394501544,
      "total_market_value": 446642152820,
      "circulation_value": 440276998895,
      "pe_ttm": 113.69,
      "pe_dynamic": 96.41,
      "pb": 27.94,
      "close": 183.87,
      "change_pct": 2.06,
      "company_profile": "广东生益科技股份有限公司创始于1985年...",
      "main_business": "设计、生产和销售覆铜板和粘结片、印制线路板",
      "business_scope": "设计、生产和销售覆铜板和粘结片...",
      "company_history": "广东生益科技股份有限公司原为东莞生益敷铜板股份有限公司...",
      "boards": ["电子", "元件", "印制电路板", "5G概念", "华为概念", "HS300", ...],
      "business_products": [
        {"product": "覆铜板业务", "revenue_yi": 187.96, "ratio_pct": 66.11},
        {"product": "线路板业务", "revenue_yi": 94.85, "ratio_pct": 33.36},
        {"product": "其他业务收入", "revenue_yi": 9.01, "ratio_pct": 3.17},
        {"product": "地产业务收入", "revenue_yi": 0.94, "ratio_pct": 0.33},
        {"product": "分部间抵销收入", "revenue_yi": -8.46, "ratio_pct": -2.97}
      ]
    },
    "add_stock": [
      {"发行方式": "...", "发行价格": 0, "发行数量": 0, "上市日期": "..."}
    ]
  }
}
```

**字段来源映射**：
- `quote` 字段全部来自腾讯行情 `qt.gtimg.cn`，`~` 分隔，从索引 0 开始计数
- `profile.boards` 来自东财 `bk` 字段逗号切分
- `profile.business_products` 来自东财 `coreTheme` 中 `【主营产品】` 段落的解析
- `profile.company_history` 来自东财 `coreTheme` 中 `【公司沿革】` 段落的解析
- quote 与 profile 中的 pe_ttm/pe_dynamic/pb 存在交叉，二者来自独立数据源，可交叉验证

---

### 📊 基本面 (fundamentals)

**数据源**: 五大财报 API + stock_profit_forecast_ths + stock_zygc_em (共 10 次调用)

- 财报: `stock_financial_abstract_new_ths` (分别按报告期/按年度 2 次), `stock_financial_benefit_new_ths` (按报告期), `stock_financial_debt_new_ths` (按报告期), `stock_financial_cash_new_ths` (按报告期) — 均截取最近 5 年
- 盈利预测: `stock_profit_forecast_ths` × 4 种 indicator — 全量
- 主营构成: `stock_zygc_em` — 截取最近 3 年

```json
{
  "fundamentals": {
    "financials": {
      "abstract": {
        "by_report": [...],
        "by_year": [...]
      },
      "benefit": [...],
      "debt": [...],
      "cashflow": [...]
    },
    "profit_forecast": {
      "eps_forecast": [           // indicator: "预测年报每股收益"
        {"year": 2026, "机构名称": "中信证券", "每股收益": 2.15}
      ],
      "net_profit_forecast": [     // indicator: "预测年报净利润"
        {"year": 2026, "机构名称": "中信证券", "净利润": 52.3}
      ],
      "institution_detail": [...], // indicator: "业绩预测详表-机构"
      "indicator_detail": [...]    // indicator: "业绩预测详表-详细指标预测"
    },
    "revenue_structure": [        // 主营构成, 最近3年
      {"报告期": "2025-12-31", "主营收入": 284.4, "主营成本": ...}
    ]
  }
}
```

> 财报 DataFrame 全部转为 dict 列表，保留原始列名。注意同花顺财务 API 不同 indicator 返回的列结构不同（一季度/二季度/三季度/四季度/按年度/按报告期），默认使用"按报告期"。

---

### ⚠️ 风险信号 (risk_signals)

**数据源**: stock_dzjy_mrmx + 2×限售解禁 + stock_gpzy_individual_pledge_ratio_detail_em (共 4 次调用)

```json
{
  "risk_signals": {
    "block_trades": {
      "period": {"start": "20260522", "end": "20260621"},
      "data": [
        {"成交日期": "2026-06-20", "成交价": 182.00, "成交量": 500000, "成交额": 91000000}
      ]
    },
    "restricted_release": {
      "eastmoney": [...],
      "sina": [...]
    },
    "pledge": {
      "unreleased_only": true,
      "data": [...]
    }
  }
}
```

**数据源细节**：

| 子板块 | API | 参数 | 截取策略 | 备注 |
|--------|-----|------|----------|------|
| block_trades | `stock_dzjy_mrmx` | symbol='A股' | 近 30 日 | 全市场数据按 stock_name 或代码过滤目标个股 |
| restricted_release | `stock_restricted_release_queue_em` | symbol | 近 2 年 + 未执行 | 东财源 |
| restricted_release | `stock_restricted_release_queue_sina` | symbol | 近 2 年 + 未执行 | 新浪源，与东财互补校验 |
| pledge | `stock_gpzy_individual_pledge_ratio_detail_em` | symbol | 仅"未解押" | 按"质押状态"字段过滤 |

---

### 📋 事件驱动 (events)

**数据源**: stock_individual_notice_report (共 1 次调用)

```json
{
  "events": {
    "notices": {
      "period": {"start": "20260323", "end": "20260621"},
      "data": [
        {"公告日期": "2026-06-18", "公告标题": "2025年年度股东大会决议公告", "公告类型": "股东大会"}
      ]
    }
  }
}
```

- 默认近 90 日（约一个季度），覆盖最新季报期 + 期间重大事项
- 类型为"全部"，不按 `symbol` 细分

---

### 🏢 机构动向 (institutional)

**数据源**: stock_jgdy_tj_em (共 1 次调用)

```json
{
  "institutional": {
    "research_visits": {
      "period": {"start": "20260522", "end": "20260621"},
      "data": [
        {"调研日期": "2026-06-15", "调研机构": "中信证券", "调研人员": "张三"}
      ]
    }
  }
}
```

- 遍历近 30 天每日的 `stock_jgdy_tj_em(date=...)`，按 stock_name 或代码过滤目标个股
- 如果该日数据量为 0，跳过；如果某只股票多日被调研，多条记录并排

---

## API 调用汇总

| 板块 | 调用次数 | 数据源 |
|------|----------|--------|
| basic_info | 3 | `tencent_quote` (HTTP), `eastmoney_search` (HTTP), `stock_add_stock` |
| fundamentals | 10 | `stock_financial_abstract_new_ths` (×2), `stock_financial_benefit_new_ths`, `stock_financial_debt_new_ths`, `stock_financial_cash_new_ths`, `stock_profit_forecast_ths` (×4), `stock_zygc_em` |
| risk_signals | 4 | `stock_dzjy_mrmx`, `stock_restricted_release_queue_em`, `stock_restricted_release_queue_sina`, `stock_gpzy_individual_pledge_ratio_detail_em` |
| events | 1 | `stock_individual_notice_report` |
| institutional | 1 | `stock_jgdy_tj_em` (最多 30 次 date 遍历) |
| **总计** | **19** | |

> 机构动向板块 `stock_jgdy_tj_em` 按天遍历近 30 日，单次 date 调用计 1 次 API（30 次日级调用仍遵守 10 次/分钟速率限制）。

---

## 分析 Prompt

拿到 JSON 输出后，将 `sections` 中的内容与以下 prompt 一起提交给大模型：

> 以下是股票 <symbol> <stock_name> 的基本面数据，请从以下维度综合分析该股票的投资价值：
> 
> 1. **估值水平**：基于 PE(TTM)、PE(动态)、PB、总市值、流通市值分析当前估值是否合理
> 2. **盈利能力与成长性**：基于近 5 年财务数据和盈利预测，分析收入/利润趋势、毛利率、ROE 变化
> 3. **业务结构**：基于主营构成，分析核心业务竞争力和收入集中度
> 4. **风险信号**：大宗交易折溢价趋势、限售解禁压力、股权质押比例是否危险
> 5. **重大事项**：近期公告中是否有资产重组、业绩预告、风险提示等重要事项
> 6. **机构关注度**：机构调研频率和参与机构质量
> 
> 最后给出综合评分（1-10 分）和主要风险提示。

---

## 前置协议补充

- 所有数据接口变化参考 akshare 官方文档
- 因为是按个股单次调用，skill 本身不涉及到额外的缓存逻辑
