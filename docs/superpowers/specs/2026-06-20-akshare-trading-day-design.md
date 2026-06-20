# A股交易日判断 (akshare-trading-day) SKILL 设计规格

**日期**: 2026-06-20
**状态**: 已确认

---

## 1. 概述

构建一个名为 `akshare-trading-day` 的 SKILL，供外部 AI Agent 通过 GitHub 安装使用。该 skill 基于 akshare 的 `tool_trade_date_hist_sina` API，提供交易日判断、下一交易日查询、范围内交易日统计三个功能。

## 2. 目录结构

```
akshare-trading-day/
  SKILL.md
  scripts/
    trading_day.py              # 核心脚本，CLI 子命令模式
    tests/
      __init__.py
      test_trading_day.py       # 单元测试 (mock akshare)
      test_integration.py       # 集成测试 (真实网络)
```

## 3. 数据源

| API | 数据量 | 数据类型 |
|-----|--------|---------|
| `tool_trade_date_hist_sina()` | ~8800 条 | `datetime.date` |

数据来源：新浪财经交易日历，覆盖 1990-12-19 至今后约半年。

## 4. CLI 接口

三个子命令，全部输出 JSON 到 stdout，错误信息到 stderr。

### check — 判断是否为交易日

```bash
uv run python scripts/trading_day.py check 2026-06-22
```

输出：
```json
{"is_trading_day": true}
```

### next — 查询下一个交易日

输入日期本身若是交易日，返回当日；否则返回最近的下一个交易日。

```bash
uv run python scripts/trading_day.py next 2026-06-20
```

输出：
```json
{"next_trading_day": "2026-06-22"}
```

如果输入日期超出数据范围，返回 null 并附带 error：
```json
{"next_trading_day": null, "error": "out_of_range"}
```

### count — 统计范围内交易日数量

包含起止日期。

```bash
uv run python scripts/trading_day.py count 2026-06-01 2026-06-30
```

输出：
```json
{"count": 20}
```

## 5. 脚本内部设计

### 核心策略

一次性从 akshare 加载全部交易日到 `set[date]`，后续所有操作都是 O(1) 查集合。Set 懒加载，首次调用时初始化，进程内缓存。

```python
_trade_dates: set[date] = set()

def _load_trade_dates():
    import akshare as ak
    df = ak.tool_trade_date_hist_sina()
    _trade_dates.update(df["trade_date"].tolist())
```

### 三个操作

| 命令 | 核心逻辑 | 说明 |
|------|---------|------|
| `check` | `date in _trade_dates` | O(1) |
| `next` | `min(d for d in _trade_dates if d >= input_date)` | 含当日 |
| `count` | `sum(1 for d in _trade_dates if start <= d <= end)` | 含起止日 |

## 6. 错误处理

| 错误场景 | 退出码 | 输出示例 |
|---------|--------|---------|
| 日期格式非法 | 1 | `{"error": "invalid_date_format", "detail": "期望 YYYY-MM-DD，收到 abc"}` |
| akshare 加载失败 | 2 | `{"error": "data_load_error", "detail": "..."}` |
| next 超出范围 | 0 | `{"next_trading_day": null, "error": "out_of_range"}` |

## 7. 依赖

- Python ≥ 3.10
- `akshare`

```bash
uv pip install akshare
```

## 8. 测试策略

| 测试文件 | 内容 | 类型 |
|----------|------|------|
| `test_trading_day.py` | mock `tool_trade_date_hist_sina()` 返回 10 天固定数据，覆盖 check/next/count 所有边界 | 单元测试 |
| `test_integration.py` | 真实网络调用 akshare，验证实际数据可用 | 集成测试 |

### 单元测试关键用例

- check: 交易日返回 true，非交易日返回 false，非法日期格式报错
- next: 输入交易日返回自身，输入非交易日返回下一个，超出范围返回 null
- count: 正常范围统计，空范围返回 0，起止相等且为交易日返回 1
- 错误处理: 非法日期格式、API 加载失败

## 9. SKILL.md 触发条件

当用户提到以下关键词或场景时触发：
- 判断某日期是否是A股交易日
- 查找下一个交易日
- 统计交易日数量
- 交易日历查询
- 股市开市/休市日期判断

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-20 | 初始版本 |
