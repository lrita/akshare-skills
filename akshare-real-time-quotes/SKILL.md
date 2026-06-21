---
name: akshare-real-time-quotes
description: Use when the AI needs real-time A-stock quote data for trading decisions. Provides current price, volume, inner/outer disk, full 5-level order book (bid/ask), valuation metrics (PE, PB, market cap), and intraday minute-level K-line data. All output is structured JSON with Chinese-named fields and units.
---

# A股实时行情与日内K线

## 概述

获取A股实时行情快照（含完整盘口数据）和日内分钟K线，输出结构化 JSON 供 AI 交易决策消费。覆盖上海、深圳、北京三大交易所。

## 使用方式

```bash
# 实时行情 + 盘口
uv run python scripts/fetch_realtime.py quote --symbol 600183

# 日内分钟K线
uv run python scripts/fetch_realtime.py intraday --symbol 600183

# 指定输出文件
uv run python scripts/fetch_realtime.py quote --symbol 600183 --output quote.json
```

## 参数说明

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `quote / intraday` | 是 | - | 子命令：行情快照 或 分钟K线 |
| `--symbol` | 是 | - | 股票代码，6位纯数字 |
| `--output` | 否 | stdout | 输出 JSON 文件路径 |

## 输出格式

所有输出为纯 JSON 到 stdout，日志/错误输出到 stderr。

### quote 子命令

输出按语义分为 4 个分组：

```json
{
  "股票代码": "600183",
  "股票名称": "生益科技",
  "行情更新时间": "20260618161425",
  "行情数据": {
    "当前价格(元)": 183.87,
    "昨收价(元)": 180.15,
    "今开价(元)": 178.50,
    "最高价(元)": 187.35,
    "最低价(元)": 176.73,
    "涨跌额(元)": 3.72,
    "涨跌幅(%)": 2.06,
    "振幅(%)": 5.90,
    "日内均价(元)": 182.85
  },
  "成交数据": {
    "成交量(手)": 798770,
    "成交额(万元)": 1460514,
    "换手率(%)": 3.34,
    "量比": 0.90,
    "外盘(手)": 419569,
    "内盘(手)": 379201
  },
  "盘口数据": {
    "买一价(元)": 183.87, "买一量(手)": 1147,
    "买二价(元)": 183.86, "买二量(手)": 159,
    "买三价(元)": 183.85, "买三量(手)": 587,
    "买四价(元)": 183.84, "买四量(手)": 329,
    "买五价(元)": 183.83, "买五量(手)": 26,
    "卖一价(元)": 183.88, "卖一量(手)": 165,
    "卖二价(元)": 183.89, "卖二量(手)": 46,
    "卖三价(元)": 183.90, "卖三量(手)": 77,
    "卖四价(元)": 183.91, "卖四量(手)": 32,
    "卖五价(元)": 183.92, "卖五量(手)": 30,
    "委差": 1898
  },
  "估值数据": {
    "滚动市盈率": 113.69,
    "动态市盈率": 96.41,
    "市净率": 27.94,
    "流通市值(亿)": 4402.77,
    "总市值(亿)": 4466.42,
    "涨停价(元)": 198.17,
    "跌停价(元)": 162.14
  }
}
```

| 分组 | 用途 |
|------|------|
| `行情数据` | 价格判断——当前价、涨跌幅、日内均价等 |
| `成交数据` | 流动性/多空判断——成交量额、换手率、外盘内盘 |
| `盘口数据` | 盘口深度判断——买卖五档挂单价+量、委差 |
| `估值数据` | 估值/限制判断——PE、PB、市值、涨跌停价 |

### intraday 子命令

```json
{
  "股票代码": "600183",
  "股票名称": "生益科技",
  "交易日期": "20260618",
  "分钟K线": [
    {"时间": "0930", "价格(元)": 178.50, "成交量": 13747, "成交额(元)": 245383950.50},
    {"时间": "0931", "价格(元)": 178.80, "成交量": 8921, "成交额(元)": 159423180.00}
  ]
}
```

时间 `HHmm` 格式，成交量单位股，成交额单位元。

## 数据源

| 功能 | API | 说明 |
|------|-----|------|
| 实时行情 | `https://qt.gtimg.cn/q=` | 腾讯财经行情快照，gbk 编码 |
| 分钟K线 | `https://web.ifzq.gtimg.cn/appstock/app/minute/query` | 腾讯财经分钟K线，JSON |

## 速率限制

无内置限速，由调用方自行控频。

## 错误处理

- 网络异常：返回空 `{}` 或 `[]`，不崩溃
- 字段不足：防御性跳过，返回空 `{}`
- 参数非法：exit 2，stderr 输出原因
- API 返回空数据：输出 `{"股票代码": "...", "分钟K线": []}`

## 依赖

仅 Python 3 标准库（`argparse`, `json`, `urllib.request`），无需安装任何第三方包。

## exit code

| code | 含义 |
|------|------|
| 0 | 成功获取数据 |
| 1 | 数据源全部失败 |
| 2 | 参数非法 |

## 使用示例

```bash
# 获取实时行情
uv run python scripts/fetch_realtime.py quote --symbol 600183

# 通过 jq 提取盘口数据
uv run python scripts/fetch_realtime.py quote --symbol 600183 | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['盘口数据'], indent=2, ensure_ascii=False))"

# 获取分钟K线并保存
uv run python scripts/fetch_realtime.py intraday --symbol 000001 --output 000001_minutes.json
```
