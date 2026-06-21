# 技术指标选股 Skill 设计规格

## 概述

基于 akshare 的 20 个技术指标/选股 API，构建全功能技术选股工作台。支持 4 种工作模式：单指标查询、多指标交集筛选、综合技术面扫描、全量分析。

## 架构

```
akshare-tech-selection/
├── SKILL.md                          # skill 定义
└── scripts/
    ├── tech_selection.py             # CLI 入口 (argparse, 模式路由)
    ├── fetcher.py                    # API 调用 + 解析层 (20 个 fetcher 函数)
    ├── engine.py                     # 4 种模式逻辑
    └── tests/
        ├── __init__.py
        ├── conftest.py
        ├── test_fetcher.py           # fetcher 单元测试 (mock)
        ├── test_engine.py            # engine 单元测试 (mock)
        └── test_integration.py       # 端到端集成测试
```

**数据流向**：

```
CLI (argparse)
    │
    ▼
engine.py (按 mode 分发)
    │
    ├── single   → 调用 1 个 fetcher → 直接输出
    ├── intersect → 调用 N 个 fetcher → 取股票代码交集 → 输出
    ├── scan     → 并发调用全部 20 个 fetcher → 按股票聚合信号 → 输出
    └── full     → scan + 详细指标级汇总统计 → 输出
    │
    ▼
fetcher.py (每个函数: 调 akshare API → 列名标准化 → NaN处理)
```

**依赖**：`akshare`, `pandas`，无其他第三方库。

---

## API 清单（20 个，分 3 大类）

### 第 1 类：同花顺技术指标 (12 个)

| # | API | 描述 | 默认 symbol | 参数 |
|---|-----|------|-------------|------|
| 1 | `stock_rank_cxg_ths` | 创新高 | 创月新高 | symbol: 创月/半年/一年/历史新高 |
| 2 | `stock_rank_cxd_ths` | 创新低 | 创月新低 | symbol: 创月/半年/一年/历史新低 |
| 3 | `stock_rank_lxsz_ths` | 连续上涨 | - | 无 |
| 4 | `stock_rank_lxxd_ths` | 连续下跌 | - | 无 |
| 5 | `stock_rank_cxfl_ths` | 持续放量 | - | 无 |
| 6 | `stock_rank_cxsl_ths` | 持续缩量 | - | 无 |
| 7 | `stock_rank_xstp_ths` | 向上突破均线 | 500日均线 | symbol: 5/10/20/30/60/90/250/500日均线 |
| 8 | `stock_rank_xxtp_ths` | 向下突破均线 | 500日均线 | symbol: 5/10/20/30/60/90/250/500日均线 |
| 9 | `stock_rank_ljqs_ths` | 量价齐升 | - | 无 |
| 10 | `stock_rank_ljqd_ths` | 量价齐跌 | - | 无 |
| 11 | `stock_rank_xzjp_ths` | 险资举牌 | - | 无 |
| 12 | `stock_rank_forecast_cninfo` | 机构评级预测 | - | date: YYYYMMDD |

### 第 2 类：涨停板分析 (6 个)

| # | API | 描述 | 参数 |
|---|-----|------|------|
| 13 | `stock_zt_pool_strong_em` | 强势涨停池 | date: YYYYMMDD |
| 14 | `stock_zt_pool_em` | 涨停池（全量涨停板） | date: YYYYMMDD |
| 15 | `stock_zt_pool_dtgc_em` | 跌停股池 | date: YYYYMMDD |
| 16 | `stock_zt_pool_sub_new_em` | 次新股池 | date: YYYYMMDD |
| 17 | `stock_zt_pool_previous_em` | 昨日涨停今日表现 | date: YYYYMMDD |
| 18 | `stock_zt_pool_zbgc_em` | 炸板股池 | date: YYYYMMDD |

### 第 3 类：异动监控 (2 个)

| # | API | 描述 | 默认 symbol | 参数 |
|---|-----|------|-------------|------|
| 19 | `stock_board_change_em` | 板块异动排名 | - | 无 |
| 20 | `stock_changes_em` | 个股盘口异动 | 大笔买入 | symbol: 22种异动类型 |

---

## Fetcher 层设计

`fetcher.py`，约 250 行。

### Fetcher 命名映射

| akshare API | fetcher 函数名 | 简称 |
|-------------|---------------|------|
| `stock_rank_cxg_ths` | `fetch_cxg_ths` | 创新高 |
| `stock_rank_cxd_ths` | `fetch_cxd_ths` | 创新低 |
| `stock_rank_lxsz_ths` | `fetch_lxsz_ths` | 连续上涨 |
| `stock_rank_lxxd_ths` | `fetch_lxxd_ths` | 连续下跌 |
| `stock_rank_cxfl_ths` | `fetch_cxfl_ths` | 持续放量 |
| `stock_rank_cxsl_ths` | `fetch_cxsl_ths` | 持续缩量 |
| `stock_rank_xstp_ths` | `fetch_xstp_ths` | 向上突破 |
| `stock_rank_xxtp_ths` | `fetch_xxtp_ths` | 向下突破 |
| `stock_rank_ljqs_ths` | `fetch_ljqs_ths` | 量价齐升 |
| `stock_rank_ljqd_ths` | `fetch_ljqd_ths` | 量价齐跌 |
| `stock_rank_xzjp_ths` | `fetch_xzjp_ths` | 险资举牌 |
| `stock_rank_forecast_cninfo` | `fetch_forecast_cninfo` | 机构评级 |
| `stock_zt_pool_strong_em` | `fetch_zt_pool_strong` | 强势涨停 |
| `stock_zt_pool_em` | `fetch_zt_pool` | 涨停池 |
| `stock_zt_pool_dtgc_em` | `fetch_zt_pool_dtgc` | 跌停股池 |
| `stock_zt_pool_sub_new_em` | `fetch_zt_pool_sub_new` | 次新股池 |
| `stock_zt_pool_previous_em` | `fetch_zt_pool_previous` | 昨日涨停表现 |
| `stock_zt_pool_zbgc_em` | `fetch_zt_pool_zbgc` | 炸板股池 |
| `stock_board_change_em` | `fetch_board_change` | 板块异动 |
| `stock_changes_em` | `fetch_changes` | 个股异动 |

### 函数签名

```python
def fetch_xxx(symbol: str | None = None, date: str | None = None) -> dict | None:
    """
    调用 akshare API，返回标准化结构:
    {
        "indicator": "fetch_xxx",
        "category": "创新高",
        "categories": ["同花顺技术指标", "趋势类"],
        "count": 68,
        "data": [{...}, ...]
    }
    失败返回 None
    """
```

**设计原则**：
- 原始列名保持中文（减少信息丢失）
- 股票代码统一去除 `SZ`/`SH` 等前缀（方便交集计算）
- NaN → `null`
- 每个 fetcher 独立，互不依赖

---

## Engine 层设计

`engine.py`，约 200 行。对外暴露 4 个入口函数：

```python
def run_single(indicator: str, **params) -> dict
def run_intersect(indicators: list[str], **params_per_indicator) -> dict
def run_scan(date: str) -> dict
def run_full(date: str) -> dict
```

### 并发策略

- `ThreadPoolExecutor`，max_workers 默认 8（可通过 `--workers` 调整）
- 每个 API 调用间 0.1-0.3s 随机 jitter
- 单个 API 失败不阻断其他 API

### 交集计算

- 按标准化后的 `stock_code`（6位纯数字）取集合交集
- 某指标返回空数据 → 交集必然为空 → 在 errors 中显式告警

### 信号聚合（scan/full 核心）

- 全量 stock_code 为 key，聚合每个指标命中的 signal
- signal 包含：`indicator`, `category`（如"连续上涨"）, `detail`（该行原始数据）
- 按 `signal_count` 降序排列
- 无信号的股票不出现在 `data` 中

---

## 输出格式

统一 JSON 输出到 stdout，日志/错误到 stderr。

### 通用字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `mode` | string | single / intersect / scan / full |
| `fetch_time` | string | 数据获取时间 (YYYY-MM-DD HH:MM:SS) |
| `errors` | array | 失败列表 [{indicator, error, api_name}] |

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
      "最高价": 27.87,
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
  "fetch_time": "2026-06-21 15:30:00",
  "total_indicators": 2,
  "succeeded_indicators": 2,
  "intersect_count": 8,
  "indicator_counts": {
    "fetch_lxsz_ths": 62,
    "fetch_cxfl_ths": 114
  },
  "data": [
    {
      "stock_code": "000423",
      "stock_name": "东阿阿胶",
      "matched_indicators": ["fetch_lxsz_ths", "fetch_cxfl_ths"],
      "indicator_details": {
        "fetch_lxsz_ths": { "序号": 10, "收盘价": 55.25, "连涨天数": 3 },
        "fetch_cxfl_ths": { "序号": 5, "放量天数": 5, "阶段涨跌幅": 14.51 }
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
  "fetch_time": "2026-06-21 15:30:00",
  "total_indicators": 20,
  "succeeded_indicators": 18,
  "signal_summary": {
    "total_stocks_with_signals": 2341,
    "top_signals": [
      {"indicator": "fetch_lxsz_ths", "count": 62},
      {"indicator": "fetch_ljqs_ths", "count": 45}
    ]
  },
  "data": [
    {
      "stock_code": "000423",
      "stock_name": "东阿阿胶",
      "signals": [
        {"indicator": "fetch_lxsz_ths", "category": "连续上涨", "detail": {}},
        {"indicator": "fetch_cxfl_ths", "category": "持续放量", "detail": {}},
        {"indicator": "fetch_ljqs_ths", "category": "量价齐升", "detail": {}}
      ],
      "signal_count": 3
    }
  ],
  "errors": []
}
```

### full 模式

在 scan 全部字段基础上，`signal_summary` 升级为详细版：

```json
{
  "mode": "full",
  "fetch_time": "2026-06-21 15:30:00",
  "total_indicators": 20,
  "succeeded_indicators": 18,
  "signal_summary": {
    "total_stocks_with_signals": 2341,
    "indicators": [
      {
        "indicator": "fetch_lxsz_ths",
        "category": "连续上涨",
        "status": "success",
        "total_rows": 62
      },
      {
        "indicator": "fetch_cxg_ths",
        "category": "创新高",
        "status": "success",
        "total_rows": 68
      },
      {
        "indicator": "fetch_xxx",
        "category": "某指标",
        "status": "null_data",
        "total_rows": 0
      }
    ]
  },
  "data": [...],
  "errors": []
}
```

`data` 结构与 scan 完全相同。full 就是 scan + 更详细的指标健康度。

---

## CLI 参数

```bash
uv run python scripts/tech_selection.py [options]
```

| 参数 | 必需 | 类型 | 说明 |
|------|------|------|------|
| `--mode` | ✅ | str | `single` / `intersect` / `scan` / `full` |
| `--indicator` | single/intersect 必需 | str | single: 单个 indicator 名；intersect: 逗号分隔多个 |
| `--date` | 可选 | str | 日期 `YYYYMMDD`，默认今天；作用于涨停板类(6)+机构评级(1)。其他 13 个指标忽略此参数 |
| `--symbol` | 可选 | str | 格式 `indicator_name=value`，可重复多次；覆盖默认 symbol |
| `--signal-threshold` | 可选 | int | scan/full 中只返回 signal_count >= N 的股票，默认 1 |
| `--top-n` | 可选 | int | 只返回前 N 条结果，默认全量 |
| `--workers` | 可选 | int | 并发数，默认 8 |
| `--output` | 可选 | path | 输出 JSON 文件路径，默认 stdout |

### 默认 symbol 表

| indicator | 默认 symbol |
|-----------|-------------|
| `fetch_cxg_ths` | 创月新高 |
| `fetch_cxd_ths` | 创月新低 |
| `fetch_xstp_ths` | 500日均线 |
| `fetch_xxtp_ths` | 500日均线 |
| `fetch_changes` | 大笔买入 |

### 使用示例

```bash
# single: 查连续上涨
uv run python scripts/tech_selection.py \
  --mode single --indicator fetch_lxsz_ths

# single: 查一年新高
uv run python scripts/tech_selection.py \
  --mode single --indicator fetch_cxg_ths \
  --symbol fetch_cxg_ths=一年新高

# intersect: 连续上涨 AND 持续放量 AND 向上突破60日均线
uv run python scripts/tech_selection.py \
  --mode intersect \
  --indicator fetch_lxsz_ths,fetch_cxfl_ths,fetch_xstp_ths \
  --symbol fetch_xstp_ths=60日均线

# scan: 全量扫描，只看 3 个信号以上的股票
uv run python scripts/tech_selection.py \
  --mode scan \
  --date 20260620 \
  --signal-threshold 3

# scan: 只看 top 20
uv run python scripts/tech_selection.py \
  --mode scan \
  --top-n 20

# full: 全量分析输出到文件
uv run python scripts/tech_selection.py \
  --mode full \
  --date 20260620 \
  --output result.json
```

---

## 错误处理

### 三级容错

```
单个 API 失败
  → 记录 error dict {indicator, error, api_name}
  → 不阻断其他 API
  → scan/full 模式下跳过该指标继续聚合

全部 API 失败
  → exit code 1
  → 输出仅含 errors 列表

参数错误（非法 mode / 缺少必要参数 / 非法 symbol）
  → exit code 2
  → stderr 输出错误原因
```

### 空数据处理

- fetcher 返回 None 或空 DataFrame → 不算成功，在 `errors` 中记录为 null_data
- intersect 模式：某指标为空 → 交集必然为空 → 在 errors 中显式告警

### exit code

| code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 部分失败（至少部分成功）或全部 API 失败 |
| 2 | 参数错误 |

---

## 测试策略

遵循 TDD，与 `akshare-fund-info` 测试结构对齐。

| 层级 | 文件 | 覆盖内容 | mock 策略 |
|------|------|---------|-----------|
| 单元 | `test_fetcher.py` | 每个 fetch 函数的解析、None/空处理 | mock akshare 返回预设 DataFrame |
| 单元 | `test_engine.py` | single/intersect/scan/full 分发、聚合、排序、阈值过滤 | mock fetcher 返回预设数据 |
| 集成 | `test_integration.py` | 真实 API 连通性，至少 3 个指标端到端 | 无 mock，真实调用 |

## 缓存策略

无缓存，每次实时查询，保证数据最新。

## 依赖

```bash
uv pip install akshare pandas
```
