# akshare-trading-day 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建一个 A 股交易日判断 SKILL，支持 check/next/count 三个 CLI 子命令，基于 akshare `tool_trade_date_hist_sina` API。

**架构：** SKILL.md + `scripts/trading_day.py`。脚本一次性将交易日历加载到 `set[date]` 实现 O(1) 查找，通过 CLI 参数区分三个子命令，全部输出 JSON 到 stdout。

**技术栈：** Python ≥ 3.10, akshare, argparse (stdlib), datetime (stdlib)

---

### 任务 1：创建目录结构与 SKILL.md

**文件：**
- 创建：`akshare-trading-day/SKILL.md`
- 创建：`akshare-trading-day/scripts/__init__.py`
- 创建：`akshare-trading-day/scripts/tests/__init__.py`

- [ ] **步骤 1：创建 SKILL.md**

```markdown
---
name: akshare-trading-day
description: Use when the user needs to check if a specific date is an A-stock trading day, find the next trading day, or count trading days in a date range. Based on Sina finance trading calendar data.
---

# A股交易日判断

## 概述

基于新浪财经交易日历数据（通过 akshare `tool_trade_date_hist_sina`），提供交易日相关查询。

## 使用方式

```bash
# 判断是否为交易日
uv run python scripts/trading_day.py check 2026-06-22

# 查询下一个交易日（含当日）
uv run python scripts/trading_day.py next 2026-06-20

# 统计范围内交易日数量（含起止日）
uv run python scripts/trading_day.py count 2026-06-01 2026-06-30
```

## 输出格式

所有命令输出 JSON 到 stdout，错误信息到 stderr。

### check
```json
{"is_trading_day": true}
```

### next
```json
{"next_trading_day": "2026-06-22"}
```

### count
```json
{"count": 20}
```

## 依赖

```bash
uv pip install akshare
```
```

- [ ] **步骤 2：创建空文件**

```bash
mkdir -p akshare-trading-day/scripts/tests
touch akshare-trading-day/scripts/__init__.py
touch akshare-trading-day/scripts/tests/__init__.py
```

- [ ] **步骤 3：Commit**

```bash
git add akshare-trading-day/
git commit -m "feat: add akshare-trading-day SKILL.md and directory structure

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 2：交易日期判断核心逻辑（TDD）

**文件：**
- 创建：`akshare-trading-day/scripts/tests/test_trading_day.py`
- 创建：`akshare-trading-day/scripts/trading_day.py`（完整脚本）

- [ ] **步骤 1：编写失败的测试**

在 `akshare-trading-day/scripts/tests/test_trading_day.py` 中：

```python
"""交易日判断测试 (mock akshare)"""
from datetime import date
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch
import trading_day


# 固定的 mock 交易日集合（10天）
MOCK_DATES = {
    date(2026, 6, 15),  # Monday
    date(2026, 6, 16),  # Tuesday
    date(2026, 6, 17),  # Wednesday
    date(2026, 6, 18),  # Thursday
    date(2026, 6, 19),  # Friday
    date(2026, 6, 22),  # Monday next week
    date(2026, 6, 23),  # Tuesday
    date(2026, 6, 24),  # Wednesday
    date(2026, 6, 25),  # Thursday
    date(2026, 6, 26),  # Friday
}


class TestIsTradingDay:
    """is_trading_day 测试"""

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_trading_day_returns_true(self):
        assert trading_day.is_trading_day(date(2026, 6, 15)) is True

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_non_trading_day_returns_false(self):
        # Saturday
        assert trading_day.is_trading_day(date(2026, 6, 20)) is False

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_sunday_not_trading_day(self):
        assert trading_day.is_trading_day(date(2026, 6, 21)) is False


class TestNextTradingDay:
    """next_trading_day 测试"""

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_input_is_trading_day_returns_self(self):
        result = trading_day.next_trading_day(date(2026, 6, 15))
        assert result == date(2026, 6, 15)

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_saturday_returns_monday(self):
        result = trading_day.next_trading_day(date(2026, 6, 20))
        assert result == date(2026, 6, 22)

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_sunday_returns_monday(self):
        result = trading_day.next_trading_day(date(2026, 6, 21))
        assert result == date(2026, 6, 22)

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_friday_after_hours_returns_friday(self):
        result = trading_day.next_trading_day(date(2026, 6, 19))
        assert result == date(2026, 6, 19)

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_beyond_last_trading_day_returns_none(self):
        result = trading_day.next_trading_day(date(2026, 6, 27))
        assert result is None

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_before_first_trading_day_returns_first(self):
        result = trading_day.next_trading_day(date(2026, 6, 10))
        assert result == date(2026, 6, 15)


class TestCountTradingDays:
    """count_trading_days 测试"""

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_full_workweek(self):
        result = trading_day.count_trading_days(
            date(2026, 6, 15), date(2026, 6, 19)
        )
        assert result == 5

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_range_includes_weekend(self):
        result = trading_day.count_trading_days(
            date(2026, 6, 15), date(2026, 6, 22)
        )
        assert result == 6  # 5 weekdays + Monday

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_single_trading_day(self):
        result = trading_day.count_trading_days(
            date(2026, 6, 15), date(2026, 6, 15)
        )
        assert result == 1

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_single_weekend_day(self):
        result = trading_day.count_trading_days(
            date(2026, 6, 20), date(2026, 6, 20)
        )
        assert result == 0

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_empty_range(self):
        result = trading_day.count_trading_days(
            date(2026, 6, 22), date(2026, 6, 19)
        )
        assert result == 0

    @patch.object(trading_day, '_trade_dates', MOCK_DATES)
    def test_beyond_data_range(self):
        result = trading_day.count_trading_days(
            date(2026, 6, 27), date(2026, 6, 30)
        )
        assert result == 0
```

- [ ] **步骤 2：运行测试验证失败**

```bash
uv run pytest akshare-trading-day/scripts/tests/test_trading_day.py -v
```
预期：全部 FAIL（模块未定义）

- [ ] **步骤 3：编写实现代码**

在 `akshare-trading-day/scripts/trading_day.py` 中：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A股交易日判断脚本
基于新浪财经交易日历，提供 check/next/count 三个查询功能
"""
import sys
import json
import argparse
from datetime import date, datetime


# 交易日集合（懒加载，首次调用时从 akshare 初始化）
_trade_dates: set[date] = set()
_loaded: bool = False


def _load_trade_dates() -> None:
    """从 akshare 加载交易日历到内存集合"""
    global _trade_dates, _loaded
    if _loaded:
        return
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        _trade_dates.update(df["trade_date"].tolist())
        _loaded = True
    except Exception as e:
        raise RuntimeError(f"无法加载交易日历数据: {e}")


def is_trading_day(d: date) -> bool:
    """判断给定日期是否为 A 股交易日

    参数:
        d: 待判断的日期

    返回:
        bool: 是交易日返回 True，否则 False
    """
    _load_trade_dates()
    return d in _trade_dates


def next_trading_day(d: date) -> date | None:
    """获取下一个交易日（含当日）

    参数:
        d: 参考日期

    返回:
        date | None: 最近的下一个交易日，超出数据范围返回 None
    """
    _load_trade_dates()
    candidates = [td for td in _trade_dates if td >= d]
    if not candidates:
        return None
    return min(candidates)


def count_trading_days(start: date, end: date) -> int:
    """统计给定范围内的交易日数量（含起止日）

    参数:
        start: 开始日期
        end: 结束日期

    返回:
        int: 交易日数量
    """
    _load_trade_dates()
    if start > end:
        return 0
    return sum(1 for td in _trade_dates if start <= td <= end)


def parse_date(s: str) -> date:
    """解析 YYYY-MM-DD 日期字符串

    参数:
        s: 日期字符串

    返回:
        date: 解析结果

    异常:
        ValueError: 格式不合法
    """
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def cmd_check(args: argparse.Namespace) -> None:
    """check 子命令"""
    try:
        d = parse_date(args.date)
        _load_trade_dates()
    except ValueError:
        json.dump({"error": "invalid_date_format", "detail": f"期望 YYYY-MM-DD，收到 {args.date}"},
                  sys.stdout, ensure_ascii=False)
        sys.exit(1)
    except RuntimeError as e:
        json.dump({"error": "data_load_error", "detail": str(e)},
                  sys.stdout, ensure_ascii=False)
        sys.exit(2)

    json.dump({"is_trading_day": is_trading_day(d)}, sys.stdout, ensure_ascii=False)


def cmd_next(args: argparse.Namespace) -> None:
    """next 子命令"""
    try:
        d = parse_date(args.date)
        _load_trade_dates()
    except ValueError:
        json.dump({"error": "invalid_date_format", "detail": f"期望 YYYY-MM-DD，收到 {args.date}"},
                  sys.stdout, ensure_ascii=False)
        sys.exit(1)
    except RuntimeError as e:
        json.dump({"error": "data_load_error", "detail": str(e)},
                  sys.stdout, ensure_ascii=False)
        sys.exit(2)

    result = next_trading_day(d)
    if result is None:
        json.dump({"next_trading_day": None, "error": "out_of_range"},
                  sys.stdout, ensure_ascii=False)
    else:
        json.dump({"next_trading_day": result.strftime("%Y-%m-%d")},
                  sys.stdout, ensure_ascii=False)


def cmd_count(args: argparse.Namespace) -> None:
    """count 子命令"""
    try:
        start = parse_date(args.start)
        end = parse_date(args.end)
        _load_trade_dates()
    except ValueError:
        json.dump({"error": "invalid_date_format", "detail": "期望 YYYY-MM-DD 格式"},
                  sys.stdout, ensure_ascii=False)
        sys.exit(1)
    except RuntimeError as e:
        json.dump({"error": "data_load_error", "detail": str(e)},
                  sys.stdout, ensure_ascii=False)
        sys.exit(2)

    json.dump({"count": count_trading_days(start, end)}, sys.stdout, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="A股交易日查询")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_check = subparsers.add_parser("check", help="判断是否为交易日")
    p_check.add_argument("date", help="日期 (YYYY-MM-DD)")
    p_check.set_defaults(func=cmd_check)

    p_next = subparsers.add_parser("next", help="查询下一个交易日")
    p_next.add_argument("date", help="参考日期 (YYYY-MM-DD)")
    p_next.set_defaults(func=cmd_next)

    p_count = subparsers.add_parser("count", help="统计范围内交易日数量")
    p_count.add_argument("start", help="开始日期 (YYYY-MM-DD)")
    p_count.add_argument("end", help="结束日期 (YYYY-MM-DD)")
    p_count.set_defaults(func=cmd_count)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **步骤 4：运行测试验证通过**

```bash
uv run pytest akshare-trading-day/scripts/tests/test_trading_day.py -v
```
预期：全部 PASS (15 tests)

- [ ] **步骤 5：Commit**

```bash
git add akshare-trading-day/
git commit -m "feat: add trading day check/next/count logic with tests

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 3：集成测试

**文件：**
- 创建：`akshare-trading-day/scripts/tests/test_integration.py`

- [ ] **步骤 1：编写集成测试**

在 `akshare-trading-day/scripts/tests/test_integration.py` 中：

```python
"""集成测试 — 需要真实网络，标记为 integration"""
from datetime import date
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
import trading_day


@pytest.mark.integration
class TestIntegration:
    """真实网络集成测试"""

    def test_load_succeeds(self):
        """验证数据加载成功"""
        trading_day._trade_dates.clear()
        trading_day._loaded = False
        trading_day._load_trade_dates()
        assert len(trading_day._trade_dates) > 5000

    def test_known_trading_day(self):
        """验证已知交易日"""
        trading_day._trade_dates.clear()
        trading_day._loaded = False
        assert trading_day.is_trading_day(date(2026, 6, 22)) is True  # Monday

    def test_known_non_trading_day(self):
        """验证已知非交易日"""
        assert trading_day.is_trading_day(date(2026, 6, 20)) is False  # Saturday

    def test_next_from_weekend(self):
        """验证周末返回周一"""
        result = trading_day.next_trading_day(date(2026, 6, 20))
        assert result is not None
        assert result.weekday() < 5  # Must be a weekday
        assert result >= date(2026, 6, 20)

    def test_count_workweek(self):
        """验证一周内有5个交易日"""
        # Use a recent full workweek
        result = trading_day.count_trading_days(
            date(2026, 6, 15), date(2026, 6, 19)
        )
        assert result == 5

    def test_cli_check_command(self):
        """验证 CLI check 命令"""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "trading_day", "check", "2026-06-22"],
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            capture_output=True, text=True,
        )
        # Fallback if -m fails, try direct script path
        if result.returncode != 0:
            script_path = os.path.join(os.path.dirname(__file__), "..", "trading_day.py")
            result = subprocess.run(
                [sys.executable, script_path, "check", "2026-06-22"],
                capture_output=True, text=True,
            )
        import json
        data = json.loads(result.stdout)
        assert "is_trading_day" in data
        assert isinstance(data["is_trading_day"], bool)
```

- [ ] **步骤 2：运行集成测试**

```bash
uv run pytest akshare-trading-day/scripts/tests/test_integration.py -v -m integration
```
预期：PASS

- [ ] **步骤 3：Commit**

```bash
git add akshare-trading-day/scripts/tests/test_integration.py
git commit -m "test: add integration tests for trading-day skill

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 4：最终验证

- [ ] **步骤 1：运行所有单元测试**

```bash
uv run pytest akshare-trading-day/scripts/tests/ -v --ignore=akshare-trading-day/scripts/tests/test_integration.py
```
预期：15 tests PASS

- [ ] **步骤 2：运行集成测试**

```bash
uv run pytest akshare-trading-day/scripts/tests/test_integration.py -v -m integration
```

- [ ] **步骤 3：手动验证三个 CLI 命令**

```bash
uv run python akshare-trading-day/scripts/trading_day.py check 2026-06-22
uv run python akshare-trading-day/scripts/trading_day.py next 2026-06-20
uv run python akshare-trading-day/scripts/trading_day.py count 2026-06-15 2026-06-19
```

- [ ] **步骤 4：最终 Commit**

```bash
git add -A
git commit -m "chore: finalize akshare-trading-day implementation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 总结

| 任务 | 内容 | 文件 |
|------|------|------|
| 任务 1 | 目录结构与 SKILL.md | 3 |
| 任务 2 | 核心逻辑 (TDD) | 2 |
| 任务 3 | 集成测试 | 1 |
| 任务 4 | 最终验证 | — |

**最终文件结构：**
```
akshare-trading-day/
  SKILL.md
  scripts/
    __init__.py
    trading_day.py
    tests/
      __init__.py
      test_trading_day.py
      test_integration.py
```

**运行方式：**
```bash
uv pip install akshare
uv run python akshare-trading-day/scripts/trading_day.py check 2026-06-22
uv run python akshare-trading-day/scripts/trading_day.py next 2026-06-20
uv run python akshare-trading-day/scripts/trading_day.py count 2026-06-01 2026-06-30
uv run pytest akshare-trading-day/scripts/tests/ -v
```
