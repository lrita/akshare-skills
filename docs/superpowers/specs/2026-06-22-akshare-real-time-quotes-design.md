# akshare-real-time-quotes 设计规格

## 概述

为 AI 交易决策提供 A 股实时行情快照和日内分钟 K 线数据，覆盖上海、深圳、北京三大交易所。

## 功能

### 1. 实时行情 + 盘口 (`quote` 子命令)

获取给定股票的当前价格、涨跌幅、成交量、内外盘、买卖五档盘口及估值数据。

**数据源**: 腾讯财经行情 API (`https://qt.gtimg.cn/q=`)

**CLI**:
```bash
uv run python scripts/fetch_realtime.py quote --symbol 600183
```

**输出结构** — 按语义分组为 4 个子对象：

| 分组 | 包含字段 | 用途 |
|------|---------|------|
| `行情数据` | 当前价格、昨收、今开、最高、最低、涨跌额、涨跌幅、振幅、日内均价 | 价格判断 |
| `成交数据` | 成交量、成交额、换手率、量比、外盘、内盘 | 流动性/多空判断 |
| `盘口数据` | 买一~买五（价+量）、卖一~卖五（价+量）、委差 | 盘口深度判断 |
| `估值数据` | 滚动PE、动态PE、PB、流通市值、总市值、涨停价、跌停价 | 估值/限制判断 |

根级字段：`股票代码`、`股票名称`、`行情更新时间`。

所有数值字段中文命名带单位（与 `stock-fundamentals` 保持一致）。无成交时数值为 0。

### 2. 日内分钟 K 线 (`intraday` 子命令)

获取当日分钟级 K 线数据，用于日内趋势分析和短线决策。

**数据源**: 腾讯财经分钟 K 线 API (`https://web.ifzq.gtimg.cn/appstock/app/minute/query`)

**CLI**:
```bash
uv run python scripts/fetch_realtime.py intraday --symbol 600183
```

**输出结构**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `股票代码` | string | 6 位数字 |
| `股票名称` | string | 从 qt 快照提取 |
| `交易日期` | string | YYYYMMDD 格式 |
| `分钟K线` | list[dict] | 每分钟一条 |

每条分钟数据：

| 字段 | 类型 | 单位 |
|------|------|------|
| `时间` | string | HHmm 格式（4位） |
| `价格(元)` | float | 元 |
| `成交量` | int | 股 |
| `成交额(元)` | float | 元 |

数据已按时间升序排列，可直接用于绘制日内走势图或计算分时指标。

## 技术方案

### 文件结构

```
akshare-real-time-quotes/
├── SKILL.md            # 技能描述、用法、AI 使用指南
└── scripts/
    └── fetch_realtime.py   # 唯一脚本 (~200行)
```

### 依赖

仅 Python 标准库：`argparse`、`json`、`urllib.request`。不依赖 akshare 包，不依赖 RateLimiter。

### 代码实现要点

**`fetch_tencent_quote_verbose(code: str) -> dict`**

与 `stock-fundamentals` 中的 `fetch_tencent_quote` 类似但输出完整盘口数据：
- 解析腾讯行情 API 返回的 `~` 分隔字符串，提取全部 53 个字段
- 按语义分为 `行情数据`、`成交数据`、`盘口数据`、`估值数据` 四个子 dict
- 数值类型转换：价格为 `float`，成交量为 `int`（手），比率类为 `float`
- 失败返回 `{}`

**`fetch_intraday_minute(code: str) -> dict`**

- 根据代码前导数字构造 prefixed code（6→sh, 0/3→sz, 8/4→bj）
- 请求分钟 K 线 API，解析 JSON
- 遍历 `data.<code>.data.data` 数组，将 `"HHmm 价格 成交量 成交额"` 字符串解析为结构化 dict
- 失败返回 `{}`

**CLI**

- 使用 `argparse` subparser 模式：`quote` 和 `intraday` 两个子命令
- `--symbol` 必选参数，校验为 6 位数字
- `--output` 可选，指定输出文件路径；默认 stdout
- 输出纯 JSON，`ensure_ascii=False`，`indent=2`

### 错误处理

- 所有网络请求带 10 秒超时和 User-Agent 头
- 异常统一捕获，返回空 `{}` 或 `[]`，不影响脚本退出
- API 返回空数据时输出 `{"股票代码": "600183", "分钟K线": []}` 而非报错
- 解析字段不足时返回空 `{}`（防御性编程）

## 范围边界

- **仅 A 股**（上海/深圳/北京），不包含港股、美股
- **仅实时快照**，不包含历史行情回溯
- **仅日内分钟线**，不包含日线/周线/月线
- **不包含限速器**，由调用方自行控频
