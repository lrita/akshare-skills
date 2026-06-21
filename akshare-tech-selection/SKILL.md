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
        "fetch_lxsz_ths": {"序号": 10, "收盘价": 55.25},
        "fetch_cxfl_ths": {"序号": 5, "放量天数": 5}
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
