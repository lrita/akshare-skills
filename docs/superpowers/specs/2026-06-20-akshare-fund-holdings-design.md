# 基金抱团 TopN 股票 — 设计规格

## 概述

基于 akshare 公募基金数据和持仓数据，计算股票型和混合型基金中持股市值最大的 TopN 股票（按持仓金额累计求和），并输出近 4 个季度趋势，帮助 AI 分析基金抱团方向。

## CLI 接口

```bash
uv run python scripts/fund_holdings.py \
  --top-n 100 \           # TopN 股票数，默认 100
  --min-scale 10.0 \      # 最低募集规模(亿元)，默认 10
  --fund-types 股票型基金,混合型基金 \  # 基金类型，默认两者
  --workers 8             # 并发数，默认 8
```

- JSON 输出到 stdout，日志/进度到 stderr
- **始终使用缓存**：自动按策略判断缓存有效性，无需手动指定
- exit code: 0 成功, 1 参数错误/无数据, 2 基金列表 API 不可用

## 核心流程

```
拉取基金列表(含缓存) → 去重 → 按规模过滤 → 并发拉取持仓(含缓存) → 聚合按股票求和 → 降序排序 → 输出 TopN JSON
```

### 1. 拉取基金列表

- 调用 `fund_scale_open_sina(symbol='股票型基金')` 和 `fund_scale_open_sina(symbol='混合型基金')`
- 按 `基金代码` 去重（先股票型、后混合型，以首次出现为准）
- 排除 `总募集规模` 为 NaN/0 的基金
- 按 `总募集规模` ≥ `min_scale`(亿元) 过滤
- 缓存到 `~/.cache/akshare-fund-holdings/fund_list.json`，TTL 7 天

### 2. 并发拉取持仓

对每只通过过滤的基金：

- 自动推断最近 4 个有数据的季度（如当前为 2026 年 6 月 → 2026 + 2025 两年数据，取最新的 4 个季度）
- 判断是否需要请求：若缓存中已有最新可用季度数据则跳过（按季度披露窗口智能过期）
- 最多重试 3 次（指数退避 2s/4s/8s）
- 请求成功：持仓数据写入缓存 `holdings/{基金代码}.json`，失败记录写入缓存 `failures.json`
- **失败重试机制**：每次运行时会读取 `failures.json` 中之前失败的基金，重新尝试拉取并更新缓存；成功后从 failures 中移除
- 本次运行失败的基金记录在输出 `errors` 中，同时写入 `failures.json` 供下次重试
- 并发：`ThreadPoolExecutor(max_workers=8)`，每次请求前随机 sleep 0.3-0.8s

### 3. 聚合计算

- 使用 `持仓市值` 字段（已包含基金对该股票的持仓金额），按 `股票代码` 累加求和
- `持仓市值` 为 NaN 时当 0 处理
- 按 `total_holding_amount` 降序排序，取 TopN
- 同时统计每个季度每只股票的持仓金额和持有基金数（quarterly_trend）

### 4. 季度推断逻辑

基金季报披露截止日约为季度结束后 15-20 个工作日。推定可用窗口：

| 季度 | 报告期 | 可获取起始日 |
|---|---|---|
| Q1 | 1/1 — 3/31 | 约 4 月 22 日 |
| Q2 | 4/1 — 6/30 | 约 7 月 22 日 |
| Q3 | 7/1 — 9/30 | 约 10 月 22 日 |
| Q4 | 10/1 — 12/31 | 约次年 1 月 22 日 |

推断逻辑：从当前日期出发，找出数据库中已有数据的最新 4 个季度。

## 输出格式

```json
{
  "meta": {
    "fetch_time": "2026-06-20 15:30:00",
    "fund_types": ["股票型基金", "混合型基金"],
    "min_scale_yi": 10.0,
    "total_funds_fetched": 3580,
    "success_funds": 3421,
    "failed_funds": 159,
    "quarters": ["2026Q1", "2025Q4", "2025Q3", "2025Q2"],
    "top_n": 100,
    "actual_top_n": 100
  },
  "top_stocks": [
    {
      "rank": 1,
      "stock_code": "600519",
      "stock_name": "贵州茅台",
      "total_holding_amount": 125800000000,
      "fund_count": 892,
      "quarterly_trend": [
        {"quarter": "2025Q2", "amount": 28100000000, "fund_count": 750},
        {"quarter": "2025Q3", "amount": 29500000000, "fund_count": 780},
        {"quarter": "2025Q4", "amount": 31200000000, "fund_count": 810},
        {"quarter": "2026Q1", "amount": 37000000000, "fund_count": 892}
      ]
    }
  ],
  "errors": [
    {"fund_code": "001234", "error": "timeout"}
  ]
}
```

- 金额单位：万元（与 akshare API 一致）
- top_n > 实际股票数时返回全部，`meta.actual_top_n` 注明实际数量

## 缓存策略

| 缓存 | 路径 | 过期策略 | 说明 |
|---|---|---|---|
| 基金列表 | `~/.cache/akshare-fund-holdings/fund_list.json` | 7 天 | 新基金发行不频繁 |
| 持仓数据 | `~/.cache/akshare-fund-holdings/holdings/{基金代码}.json` | 按季度智能过期 | 下次披露窗口前不重新请求 |
| 失败记录 | `~/.cache/akshare-fund-holdings/failures.json` | 持久保留 | 记录拉取失败的基金代码+失败原因，每次运行自动重试 |

缓存智能过期：读取缓存中最新的季度，若该季度已是"当前可获取的最新季度"，则缓存有效；否则到下一季度的披露窗口后才重新拉取。

## 错误处理

| 场景 | 处理 |
|---|---|
| 基金列表 API 失败 | 终止执行，stderr 输出错误，exit code 2 |
| 单只基金持仓 API 失败 | 记入 errors 数组和 `failures.json`，继续处理其他基金 |
| 某基金某年份无数据 | 正常，有多少季度用多少季度 |
| 某季度无持仓数据 | 跳过该基金该季度，不报错 |
| 全部基金持仓拉取失败 | 输出空结果 + 完整 errors，exit code 0 |
| 之前失败的基金本次成功 | 从 `failures.json` 中移除 |
| min_scale 过高导致 0 只基金 | 输出警告，exit code 1 |
| 缓存文件损坏 | 删除损坏文件，重新拉取 |
| `持仓市值` / `总募集规模` 为 NaN | 持仓市值当 0 处理；总募集规模为 NaN 排除该基金 |

## 文件结构

```
akshare-fund-holdings/
├── SKILL.md
└── scripts/
    ├── __init__.py
    ├── fund_holdings.py          # 主脚本
    └── tests/
        ├── __init__.py
        └── test_fund_holdings.py # 单元测试 + 集成测试
```

## 并发与反拦截

- `ThreadPoolExecutor(max_workers=8)`，默认 8 并发
- 每个请求前 random jitter 0.3-0.8s
- 失败指数退避：2s → 4s → 8s，最多 3 次

## 测试策略

### 单元测试（mock API）

- 日期工具：季度推断、披露窗口判断
- 缓存逻辑：写入/读取、TTL 过期
- 规模过滤：min_scale 参数
- 聚合计算：按股票累加、排序正确性
- 基金去重：多类型合并去重

### 集成测试（真实 API，标记 `@pytest.mark.integration`）

- API 可用性检查
- 端到端 JSON 输出格式正确
- 缓存二次运行不发起 API 请求
- 部分基金无持仓数据不影响整体

## 依赖

```bash
uv pip install akshare
```

## 使用方式

```bash
uv run python scripts/fund_holdings.py --top-n 50
```
