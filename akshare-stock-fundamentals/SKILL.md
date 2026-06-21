---
name: akshare-stock-fundamentals
description: Use when the user wants to fetch fundamental data for a specific A-stock for AI analysis. Provides a comprehensive structured JSON covering basic info (quote + company profile), financials (5 tables + profit forecasts + revenue structure), risk signals (block trades, restricted releases, pledge), events (notices), and institutional research visits. Input a 6-digit stock symbol to get all dimensions at once.
---

# 个股基本面数据

## 概述

输入 A 股股票代码，一次性拉取 5 个板块的基本面数据，输出结构化 JSON 供大模型做个股基本面综合分析。

## 使用方式

```bash
uv run python scripts/fetch_fundamentals.py --symbol <code> [--date YYYYMMDD] [--output result.json]
```

脚本将 JSON 输出到 stdout，运行日志/错误输出到 stderr。

## 参数说明

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--symbol` | 是 | - | 股票代码，纯数字，如 600183 |
| `--date` | 否 | 今天 | 基准日期 YYYYMMDD，用于所有时间范围计算 |
| `--output` | 否 | stdout | 输出 JSON 文件路径 |

## 输出格式

```json
{
  "symbol": "600183",
  "stock_name": "生益科技",
  "fetch_time": "2026-06-21 15:30:00",
  "sections": {
    "basic_info": {
      "quote": { "name": "...", "price": 0, "pe_ttm": 0, "pb": 0, "..." : "..." },
      "profile": { "security_short_name": "...", "boards": ["..."], "business_products": [{"product": "...", "revenue_yi": 0, "ratio_pct": 0}] },
      "add_stock": [{"...": "..."}]
    },
    "fundamentals": {
      "financials": {
        "abstract": { "by_report": [{"...": "..."}], "by_year": [{"...": "..."}] },
        "benefit": [{"...": "..."}],
        "debt": [{"...": "..."}],
        "cashflow": [{"...": "..."}]
      },
      "profit_forecast": {
        "eps_forecast": [{"...": "..."}],
        "net_profit_forecast": [{"...": "..."}],
        "institution_detail": [{"...": "..."}],
        "indicator_detail": [{"...": "..."}]
      },
      "revenue_structure": [{"...": "..."}]
    },
    "risk_signals": {
      "block_trades": { "period": {"start": "...", "end": "..."}, "data": [{"...": "..."}] },
      "restricted_release_em": [{"...": "..."}],
      "restricted_release_sina": [{"...": "..."}],
      "pledge": { "unreleased_only": true, "data": [{"...": "..."}] }
    },
    "events": {
      "notices": { "period": {"start": "...", "end": "..."}, "data": [{"...": "..."}] }
    },
    "institutional": {
      "research_visits": { "period": {"start": "...", "end": "..."}, "data": [{"...": "..."}] }
    }
  },
  "errors": []
}
```

## 数据源概览

| 板块 | 数据源数 | 说明 |
|------|----------|------|
| basic_info | 3 | 腾讯行情 (实时报价+估值)、东财搜索 (公司档案+主营产品)、增发记录 (近2年) |
| fundamentals | 10 | 5张财报(近5年)、4维盈利预测、主营构成(近3年) |
| risk_signals | 4 | 大宗交易(近30日)、限售解禁(近2年+未执行, 东财+新浪双源)、股权质押(仅未解押) |
| events | 1 | 个股公告(近90日，全部类型) |
| institutional | 1 | 机构调研(近30日逐日遍历过滤) |
| **总计** | **19** | |

### 时间截取策略

| API | 截取窗口 | 理由 |
|-----|----------|------|
| stock_add_stock | 近2年 | 增发影响已消化 |
| 五大财报 | 近5年 | 一个完整经营周期 |
| stock_zygc_em | 近3年 | 够覆盖主营业务变化 |
| stock_dzjy_mrmx | 近30日 | 短期减持信号 |
| 限售解禁 | 近2年+未执行 | 近端+未来风险 |
| stock_individual_notice_report | 近90日 | 最新季报期 |
| stock_jgdy_tj_em | 近30日 | 短期关注度 |

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

## 速率限制

所有 API 调用受全局速率限制，每分钟最多 10 次。调用模式为顺序执行，间隔随机加入 0.3-1.0 秒抖动。

## 错误处理

- 单个数据源失败：记录到 `errors` 数组，对应 section 子字段置为 `null`，不阻断其他数据源
- 全部板块失败：exit 1，仅输出 errors
- 参数错误：exit 2，stderr 输出原因
- 同花顺 API 403：记录 `[BLOCKED]` 错误，跳过该 API 继续

## 依赖

```bash
uv pip install akshare pandas
```

## 使用示例

```bash
# 获取生益科技基本面，今日为基准日期
uv run python scripts/fetch_fundamentals.py --symbol 600183

# 指定基准日期并输出到文件
uv run python scripts/fetch_fundamentals.py --symbol 600183 --date 20260617 --output 600183_fundamentals.json

# 通过管道传给 jq 做快速查询
uv run python scripts/fetch_fundamentals.py --symbol 600183 | python3 -m json.tool | head -50
```
