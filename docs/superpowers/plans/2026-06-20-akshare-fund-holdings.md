# akshare-fund-holdings 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建一个 CLI 脚本，从 akshare 拉取公募基金持仓数据，按股票聚合计算基金抱团 TopN，支持缓存和自动失败重试。

**架构：** 单片 Python 脚本 `fund_holdings.py`，包含纯函数模块（季度推断、缓存、聚合）和一个 CLI 入口函数。输出 JSON 到 stdout，日志到 stderr。缓存存放在 `~/.cache/akshare-fund-holdings/`。

**技术栈：** Python 3, akshare, 标准库 (argparse, json, concurrent.futures, pathlib, datetime), pytest

---

### 任务 1：项目骨架搭建

**文件：**
- 创建：`akshare-fund-holdings/scripts/__init__.py`
- 创建：`akshare-fund-holdings/scripts/tests/__init__.py`
- 修改：`.gitignore`

- [ ] **步骤 1：创建目录结构和空文件**

```bash
mkdir -p akshare-fund-holdings/scripts/tests
touch akshare-fund-holdings/scripts/__init__.py
touch akshare-fund-holdings/scripts/tests/__init__.py
```

- [ ] **步骤 2：更新 .gitignore 排除缓存目录**

读取 `.gitignore` 文件，追加 `**/.cache/` 规则。

- [ ] **步骤 3：Commit**

```bash
git add akshare-fund-holdings/ .gitignore
git commit -m "chore: scaffold akshare-fund-holdings skill directory"
```

---

### 任务 2：季度推断模块（TDD）

**文件：**
- 创建：`akshare-fund-holdings/scripts/fund_holdings.py`（骨架 + 季度函数）
- 创建：`akshare-fund-holdings/scripts/tests/test_fund_holdings.py`（季度测试）

- [ ] **步骤 1：编写季度推断的失败测试**

写入 `akshare-fund-holdings/scripts/tests/test_fund_holdings.py`：

```python
"""基金持仓分析测试"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from datetime import date
from unittest.mock import patch, MagicMock
import json
import fund_holdings


class TestQuarterInference:
    """可获取季度推断测试"""

    def test_quarters_for_june_2026(self):
        """2026年6月 → 应推断 [2026Q1, 2025Q4, 2025Q3, 2025Q2]"""
        quarters = fund_holdings.infer_target_quarters(
            today=date(2026, 6, 20)
        )
        assert quarters == [
            ("2026Q1", "2026"),
            ("2025Q4", "2025"),
            ("2025Q3", "2025"),
            ("2025Q2", "2025"),
        ]

    def test_quarters_for_jan_2026(self):
        """2026年1月 → Q4尚未披露，应推断 [2025Q4?, 2025Q3, 2025Q2, 2025Q1]
        实际：1月时Q4也未披露，需要推断4个可获取季度
        2025Q4 披露窗口为次年1/22，1月20日时尚未披露
        所以应为 [2025Q3, 2025Q2, 2025Q1, 2024Q4]
        """
        quarters = fund_holdings.infer_target_quarters(
            today=date(2026, 1, 20)
        )
        assert quarters == [
            ("2025Q3", "2025"),
            ("2025Q2", "2025"),
            ("2025Q1", "2025"),
            ("2024Q4", "2024"),
        ]

    def test_quarters_for_aug_2025(self):
        """2025年8月 → Q2刚披露，应推断 [2025Q2, 2025Q1, 2024Q4, 2024Q3]"""
        quarters = fund_holdings.infer_target_quarters(
            today=date(2025, 8, 10)
        )
        assert quarters == [
            ("2025Q2", "2025"),
            ("2025Q1", "2025"),
            ("2024Q4", "2024"),
            ("2024Q3", "2024"),
        ]

    def test_quarters_for_apr_2026(self):
        """2026年4月25日 → Q1刚披露，应推断 [2026Q1, 2025Q4, 2025Q3, 2025Q2]"""
        quarters = fund_holdings.infer_target_quarters(
            today=date(2026, 4, 25)
        )
        assert quarters == [
            ("2026Q1", "2026"),
            ("2025Q4", "2025"),
            ("2025Q3", "2025"),
            ("2025Q2", "2025"),
        ]

    def test_quarters_format(self):
        """验证返回格式: [(quarter_label, year), ...]"""
        quarters = fund_holdings.infer_target_quarters(
            today=date(2025, 12, 15)
        )
        assert len(quarters) == 4
        for q, y in quarters:
            assert q.startswith("202")  # 以年份开头
            assert q[4:6] == "Q"  # 包含 Q
            assert y in ("2024", "2025")
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py::TestQuarterInference -v
```

预期：全部 FAIL，`ModuleNotFoundError` 或 `AttributeError: module 'fund_holdings' has no attribute 'infer_target_quarters'`

- [ ] **步骤 3：编写 `infer_target_quarters` 实现**

写入 `akshare-fund-holdings/scripts/fund_holdings.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基金抱团 TopN 股票分析脚本
基于新浪财经公募基金数据，聚合基金持仓，按股票持仓金额排名
"""
import sys
import json
import argparse
import time
import random
import os
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


# ---- 季度推断 ----

# 每个季度预计可获取的日期 (月份, 日)
QUARTER_AVAILABLE = {
    1: (4, 22),   # Q1 在 4/22 后可获取
    2: (7, 22),   # Q2 在 7/22 后可获取
    3: (10, 22),  # Q3 在 10/22 后可获取
    4: (1, 22),   # Q4 在次年 1/22 后可获取
}


def _quarter_available(q: int, year: int, today: date) -> bool:
    """判断某个季度数据在当前日期是否可获取"""
    avail_month, avail_day = QUARTER_AVAILABLE[q]
    if q == 4:
        # Q4 的披露日期是次年 1 月
        return today >= date(year + 1, avail_month, avail_day)
    else:
        return today >= date(year, avail_month, avail_day)


def infer_target_quarters(today: date) -> list[tuple[str, str]]:
    """推断最近 4 个可获取数据的季度

    从当前季度开始回溯，取 4 个可获取的季度。

    参数:
        today: 当前日期

    返回:
        list[tuple[str, str]]: [(季度标签如 "2026Q1", 年份如 "2026"), ...]
    """
    quarters = []
    # 从当前季度开始回溯
    current_year = today.year
    current_quarter = (today.month - 1) // 3 + 1

    # 从最近的可能季度开始尝试
    for offset in range(8):  # 最多回溯 8 个季度（2 年）
        y = current_year
        q = current_quarter - offset
        while q < 1:
            q += 4
            y -= 1

        if _quarter_available(q, y, today):
            quarters.append((f"{y}Q{q}", str(y)))

        if len(quarters) >= 4:
            break

    return quarters
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py::TestQuarterInference -v
```

预期：5 个测试全部 PASS。

- [ ] **步骤 5：Commit**

```bash
git add akshare-fund-holdings/scripts/fund_holdings.py akshare-fund-holdings/scripts/tests/test_fund_holdings.py
git commit -m "feat: implement infer_target_quarters with TDD"
```

---

### 任务 3：缓存管理模块（TDD）

**文件：**
- 修改：`akshare-fund-holdings/scripts/fund_holdings.py`
- 修改：`akshare-fund-holdings/scripts/tests/test_fund_holdings.py`

- [ ] **步骤 1：编写缓存模块的失败测试**

在 `test_fund_holdings.py` 中追加 `TestCacheManagement` 类：

```python
class TestCacheManagement:
    """缓存读写和过期测试"""

    def test_fund_list_cache_write_and_read(self, tmp_path):
        """写入基金列表缓存后能正确读取"""
        data = {
            "fetch_time": "2026-06-20 10:00:00",
            "funds": [{"基金代码": "510300", "总募集规模": 3296860.0}],
        }
        cache_path = tmp_path / "fund_list.json"
        fund_holdings.save_cache(cache_path, data)
        assert cache_path.exists()

        loaded = fund_holdings.load_cache(cache_path)
        assert loaded is not None
        assert loaded["funds"][0]["基金代码"] == "510300"

    def test_fund_list_cache_expired_7days(self, tmp_path):
        """缓存超过 7 天视为过期"""
        data = {"fetch_time": "2026-06-10 10:00:00", "funds": []}  # 10 天前
        cache_path = tmp_path / "fund_list.json"
        fund_holdings.save_cache(cache_path, data)

        # 模拟今天为 2026-06-20
        today = date(2026, 6, 20)
        assert not fund_holdings.is_cache_valid(cache_path, ttl_hours=168, today=today)

    def test_fund_list_cache_valid_within_7days(self, tmp_path):
        """缓存 3 天前仍有效"""
        data = {"fetch_time": "2026-06-17 10:00:00", "funds": []}
        cache_path = tmp_path / "fund_list.json"
        fund_holdings.save_cache(cache_path, data)

        today = date(2026, 6, 20)
        assert fund_holdings.is_cache_valid(cache_path, ttl_hours=168, today=today)

    def test_load_cache_missing_file(self, tmp_path):
        """缓存文件不存在返回 None"""
        cache_path = tmp_path / "nonexistent.json"
        assert fund_holdings.load_cache(cache_path) is None

    def test_load_cache_corrupted(self, tmp_path):
        """缓存文件损坏，删除并返回 None"""
        cache_path = tmp_path / "corrupt.json"
        cache_path.write_text("not valid json{{{")
        result = fund_holdings.load_cache(cache_path)
        assert result is None
        assert not cache_path.exists()  # 损坏文件应被删除

    def test_holdings_cache_not_expired_when_stale(self, tmp_path):
        """持仓缓存的智能过期：缓存有最新季度则不过期"""
        from datetime import datetime
        cache_path = tmp_path / "510300.json"
        data = {
            "fetch_time": "2026-04-30 10:00:00",
            "quarters": ["2026Q1", "2025Q4", "2025Q3", "2025Q2"],
            "holdings": [],
        }
        fund_holdings.save_cache(cache_path, data)
        today = date(2026, 6, 20)
        latest_available_quarter = "2026Q1"
        assert fund_holdings.is_holdings_cache_valid(
            cache_path, today, latest_available_quarter
        )

    def test_holdings_cache_expired_when_new_quarter_available(self, tmp_path):
        """持仓缓存缺少最新季度则过期"""
        cache_path = tmp_path / "510300.json"
        data = {
            "fetch_time": "2026-03-15 10:00:00",
            "quarters": ["2025Q3", "2025Q2", "2025Q1", "2024Q4"],
            "holdings": [],
        }
        fund_holdings.save_cache(cache_path, data)
        today = date(2026, 6, 20)
        latest_available_quarter = "2026Q1"
        assert not fund_holdings.is_holdings_cache_valid(
            cache_path, today, latest_available_quarter
        )

    def test_failures_cache_read_write(self, tmp_path):
        """失败记录写入并读取"""
        cache_path = tmp_path / "failures.json"
        failures = {"001234": {"fund_code": "001234", "error": "timeout"}}
        fund_holdings.save_cache(cache_path, failures)
        loaded = fund_holdings.load_cache(cache_path)
        assert loaded["001234"]["error"] == "timeout"
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py::TestCacheManagement -v
```

预期：全部 FAIL，函数未定义。

- [ ] **步骤 3：实现缓存函数**

在 `fund_holdings.py` 中追加：

```python
# ---- 缓存管理 ----

CACHE_BASE = Path.home() / ".cache" / "akshare-fund-holdings"


def load_cache(cache_path: Path) -> dict | None:
    """读取 JSON 缓存文件

    参数:
        cache_path: 缓存文件路径

    返回:
        dict | None: 缓存数据，文件不存在或损坏返回 None
    """
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # 缓存损坏，删除
        cache_path.unlink(missing_ok=True)
        return None


def save_cache(cache_path: Path, data: dict) -> None:
    """写入 JSON 缓存文件

    参数:
        cache_path: 缓存文件路径
        data: 要缓存的数据
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def is_cache_valid(cache_path: Path, ttl_hours: int, today: date) -> bool:
    """基于 TTL 检查缓存是否有效

    参数:
        cache_path: 缓存文件路径
        ttl_hours: 有效期（小时）
        today: 当前日期

    返回:
        bool: 缓存有效返回 True
    """
    data = load_cache(cache_path)
    if data is None:
        return False
    fetch_time_str = data.get("fetch_time", "")
    if not fetch_time_str:
        return False
    try:
        from datetime import datetime
        fetch_time = datetime.strptime(fetch_time_str, "%Y-%m-%d %H:%M:%S")
        age = datetime.now() - fetch_time
        return age.total_seconds() < ttl_hours * 3600
    except (ValueError, TypeError):
        return False


def is_holdings_cache_valid(
    cache_path: Path, today: date, latest_available_quarter: str
) -> bool:
    """检查持仓缓存是否智能有效

    持有缓存有效条件：缓存中存在 latest_available_quarter 数据

    参数:
        cache_path: 缓存文件路径
        today: 当前日期（保留参数，兼容签名）
        latest_available_quarter: 当前可获取的最新季度

    返回:
        bool: 缓存有效返回 True
    """
    data = load_cache(cache_path)
    if data is None:
        return False
    cached_quarters = set(data.get("quarters", []))
    return latest_available_quarter in cached_quarters
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py::TestCacheManagement -v
```

预期：8 个测试全部 PASS。

- [ ] **步骤 5：Commit**

```bash
git add akshare-fund-holdings/scripts/fund_holdings.py akshare-fund-holdings/scripts/tests/test_fund_holdings.py
git commit -m "feat: implement cache management with TDD"
```

---

### 任务 4：基金列表拉取与过滤

**文件：**
- 修改：`akshare-fund-holdings/scripts/fund_holdings.py`
- 修改：`akshare-fund-holdings/scripts/tests/test_fund_holdings.py`

- [ ] **步骤 1：编写基金列表拉取的失败测试**

在 `test_fund_holdings.py` 中追加 `TestFundListFetch` 类：

```python
import pandas as pd


class TestFundListFetch:
    """基金列表拉取、去重和过滤测试"""

    @patch("fund_holdings.ak")
    def test_fetch_fund_list_merges_and_dedup(self, mock_ak):
        """两个基金类型合并后去重"""
        # 模拟股票型基金数据
        df_equity = pd.DataFrame([
            {"基金代码": "510300", "基金简称": "沪深300ETF", "总募集规模": 3296860.0},
            {"基金代码": "512960", "基金简称": "央企ETF", "总募集规模": 2522230.0},
            {"基金代码": "999999", "基金简称": "重复基金", "总募集规模": 100000.0},
        ])
        # 模拟混合型基金数据 (含重复的 999999)
        df_mixed = pd.DataFrame([
            {"基金代码": "070011", "基金简称": "嘉实策略", "总募集规模": 4191700.0},
            {"基金代码": "999999", "基金简称": "重复基金", "总募集规模": 100000.0},
        ])
        mock_ak.fund_scale_open_sina.side_effect = [df_equity, df_mixed]

        result = fund_holdings.fetch_fund_list(["股票型基金", "混合型基金"])
        assert len(result) == 4  # 5 - 1 重复
        codes = [f["基金代码"] for f in result]
        assert codes.count("999999") == 1  # 只出现一次

    @patch("fund_holdings.ak")
    def test_filter_by_min_scale(self, mock_ak):
        """按规模过滤，排除 NaN 和低于门槛的基金"""
        df_equity = pd.DataFrame([
            {"基金代码": "510300", "基金简称": "大基金", "总募集规模": 500000.0},    # 50 亿
            {"基金代码": "000001", "基金简称": "小基金", "总募集规模": 50000.0},     # 5 亿
            {"基金代码": "000002", "基金简称": "空规模基金", "总募集规模": None},    # NaN
        ])
        df_mixed = pd.DataFrame([])
        mock_ak.fund_scale_open_sina.side_effect = [df_equity, df_mixed]

        result = fund_holdings.fetch_fund_list(
            ["股票型基金"], min_scale_yi=10.0
        )
        assert len(result) == 1
        assert result[0]["基金代码"] == "510300"

    @patch("fund_holdings.ak")
    def test_exclude_zero_scale(self, mock_ak):
        """总募集规模为 0 的基金被排除"""
        df = pd.DataFrame([
            {"基金代码": "000001", "基金简称": "零规模", "总募集规模": 0.0},
            {"基金代码": "000002", "基金简称": "正规模", "总募集规模": 100000.0},
        ])
        mock_ak.fund_scale_open_sina.return_value = df

        result = fund_holdings.fetch_fund_list(["股票型基金"], min_scale_yi=5.0)
        codes = [f["基金代码"] for f in result]
        assert "000001" not in codes
        assert "000002" in codes
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py::TestFundListFetch -v
```

预期：全部 FAIL，`fetch_fund_list` 未定义或 `import akshare` 作为模块属性不可访问。

- [ ] **步骤 3：实现 `fetch_fund_list` 函数**

在 `fund_holdings.py` 头部添加 akshare 导入，追加实现：

```python
# 在文件头部 import 区域追加:
# import akshare as ak  会自动在函数中 lazy import


def fetch_fund_list(
    fund_types: list[str],
    min_scale_yi: float = 10.0,
) -> list[dict]:
    """拉取基金列表，去重，按规模过滤

    参数:
        fund_types: 基金类型列表，如 ["股票型基金", "混合型基金"]
        min_scale_yi: 最低总募集规模（亿元），默认 10

    返回:
        list[dict]: 过滤后的基金列表，每个元素含基金代码和规模信息
    """
    import akshare as ak

    min_scale = min_scale_yi * 10000  # 亿元 → 万元

    seen_codes: set[str] = set()
    funds: list[dict] = []

    for ftype in fund_types:
        df = ak.fund_scale_open_sina(symbol=ftype)
        for _, row in df.iterrows():
            code = str(row["基金代码"])
            if code in seen_codes:
                continue
            seen_codes.add(code)

            scale = row.get("总募集规模")
            if scale is None or (isinstance(scale, float) and (scale != scale)):
                continue
            scale = float(scale)
            if scale <= 0 or scale < min_scale:
                continue

            funds.append({
                "基金代码": code,
                "基金简称": str(row.get("基金简称", "")),
                "总募集规模": scale,
                "单位净值": (
                    float(row["单位净值"]) if row.get("单位净值") is not None
                    and not (isinstance(row["单位净值"], float) and row["单位净值"] != row["单位净值"])
                    else 0.0
                ),
            })

    return funds
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py::TestFundListFetch -v
```

预期：3 个测试全部 PASS。

- [ ] **步骤 5：Commit**

```bash
git add akshare-fund-holdings/scripts/fund_holdings.py akshare-fund-holdings/scripts/tests/test_fund_holdings.py
git commit -m "feat: implement fetch_fund_list with dedup and scale filter"
```

---

### 任务 5：持仓数据拉取（TDD）

**文件：**
- 修改：`akshare-fund-holdings/scripts/fund_holdings.py`
- 修改：`akshare-fund-holdings/scripts/tests/test_fund_holdings.py`

- [ ] **步骤 1：编写持仓拉取和失败重试的失败测试**

在 `test_fund_holdings.py` 中追加 `TestHoldingsFetch` 类：

```python
class TestHoldingsFetch:
    """持仓数据拉取测试"""

    @patch("fund_holdings.ak")
    def test_fetch_single_fund_holdings(self, mock_ak):
        """拉取单只基金持仓，返回最近4个季度的数据"""
        mock_df = pd.DataFrame([
            {"序号": 1, "股票代码": "600519", "股票名称": "贵州茅台",
             "占净值比例": 4.74, "持仓市值": 1606717.16,
             "季度": "2026年1季度股票投资明细"},
            {"序号": 1, "股票代码": "600519", "股票名称": "贵州茅台",
             "占净值比例": 5.89, "持仓市值": 1150782.02,
             "季度": "2025年4季度股票投资明细"},
        ])
        mock_ak.fund_portfolio_hold_em.side_effect = [mock_df, pd.DataFrame()]

        result = fund_holdings.fetch_fund_holdings(
            "510300",
            target_quarters=[("2026Q1", "2026"), ("2025Q4", "2025")],
        )
        assert "600519" in result
        # 应该有两个季度的数据聚合
        holdings = result["600519"]
        assert len(holdings["quarters"]) >= 1
        assert holdings["stock_name"] == "贵州茅台"

    @patch("fund_holdings.ak")
    def test_fetch_holdings_with_api_failure(self, mock_ak):
        """API 调用失败返回空字典"""
        mock_ak.fund_portfolio_hold_em.side_effect = Exception("Network error")

        result = fund_holdings.fetch_fund_holdings(
            "001234",
            target_quarters=[("2026Q1", "2026")],
        )
        assert result is None  # 返回 None 表示拉取失败

    def test_parse_quarter_label(self):
        """解析季度标签，如 '2025年1季度股票投资明细' → '2025Q1'"""
        assert fund_holdings.parse_quarter_label("2025年1季度股票投资明细") == "2025Q1"
        assert fund_holdings.parse_quarter_label("2025年4季度股票投资明细") == "2025Q4"
        assert fund_holdings.parse_quarter_label("2024年3季度股票投资明细") == "2024Q3"

    def test_aggregate_holdings_by_stock(self):
        """按股票聚合持仓：跨基金累加持仓市值"""
        holdings_data = {
            # 基金 510300 的持仓
            "510300": {
                "600519": {
                    "stock_name": "贵州茅台",
                    "quarters": {"2026Q1": 1600000.0},
                },
                "300750": {
                    "stock_name": "宁德时代",
                    "quarters": {"2026Q1": 1000000.0},
                },
            },
            # 基金 070011 的持仓
            "070011": {
                "600519": {
                    "stock_name": "贵州茅台",
                    "quarters": {"2026Q1": 500000.0},
                },
            },
        }

        top_stocks, trend = fund_holdings.aggregate_holdings(
            holdings_data, top_n=2
        )
        assert len(top_stocks) == 2
        # 贵州茅台应排第一：1600000 + 500000 = 2100000
        assert top_stocks[0]["stock_code"] == "600519"
        assert top_stocks[0]["total_holding_amount"] == 2100000.0
        assert top_stocks[0]["fund_count"] == 2
        # 宁德时代应排第二：1000000
        assert top_stocks[1]["stock_code"] == "300750"
        assert top_stocks[1]["fund_count"] == 1
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py::TestHoldingsFetch -v
```

预期：全部 FAIL，函数未定义。

- [ ] **步骤 3：实现持仓拉取和聚合函数**

在 `fund_holdings.py` 中追加：

```python
# ---- 持仓数据拉取 ----

def parse_quarter_label(raw: str) -> str:
    """解析 akshare 季度标签

    参数:
        raw: 如 "2025年1季度股票投资明细"

    返回:
        str: 如 "2025Q1"
    """
    parts = raw.split("年")
    year = parts[0].strip()
    quarter_str = parts[1].split("季度")[0].strip()
    return f"{year}Q{quarter_str}"


def fetch_fund_holdings(
    fund_code: str,
    target_quarters: list[tuple[str, str]],
    retries: int = 3,
) -> dict | None:
    """拉取单只基金的持仓数据（带重试）

    参数:
        fund_code: 基金代码
        target_quarters: [(季度标签, 年份), ...]
        retries: 最大重试次数

    返回:
        dict | None: {股票代码: {stock_name, quarters: {季度: 金额}}}, 失败返回 None
    """
    import akshare as ak

    # 按年份去重，每个年份调用一次 API
    years = list(dict.fromkeys(y for _, y in target_quarters))

    stock_map: dict[str, dict] = {}

    for year in years:
        for attempt in range(retries):
            try:
                # 随机间隔防拦截
                time.sleep(random.uniform(0.3, 0.8))
                df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)
                break
            except Exception:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt * 2)
                else:
                    return None  # 全部重试失败

        if df is None or len(df) == 0:
            continue

        for _, row in df.iterrows():
            stock_code = str(row["股票代码"])
            stock_name = str(row.get("股票名称", ""))
            raw_quarter = str(row.get("季度", ""))
            quarter = parse_quarter_label(raw_quarter)

            # 只看目标季度
            if quarter not in [q for q, _ in target_quarters]:
                continue

            holding_value = row.get("持仓市值")
            if holding_value is None or (isinstance(holding_value, float) and holding_value != holding_value):
                holding_value = 0.0
            else:
                holding_value = float(holding_value)

            if stock_code not in stock_map:
                stock_map[stock_code] = {"stock_name": stock_name, "quarters": {}}
            stock_map[stock_code]["quarters"][quarter] = (
                stock_map[stock_code]["quarters"].get(quarter, 0.0) + holding_value
            )

    return stock_map


# ---- 聚合计算 ----

def aggregate_holdings(
    all_holdings: dict[str, dict],
    top_n: int,
) -> tuple[list[dict], dict[str, dict]]:
    """跨基金聚合持仓，按股票代码累加持仓市值

    参数:
        all_holdings: {基金代码: {股票代码: {stock_name, quarters: {季度: 金额}}}}
        top_n: 返回 TopN 股票

    返回:
        (top_stocks, quarterly_trend):
            top_stocks: TopN 股票列表，按 total_holding_amount 降序
            quarterly_trend: {股票代码: {季度: {amount, fund_count}}}
    """
    # 累加：{股票代码: {total_amount, fund_count, stock_name, 季度→金额}}
    stock_agg: dict[str, dict] = {}
    # 季度趋势：{股票代码: {季度: {amount, fund_count}}}
    quarterly: dict[str, dict] = {}

    for fund_code, holdings in all_holdings.items():
        for stock_code, info in holdings.items():
            if stock_code not in stock_agg:
                stock_agg[stock_code] = {
                    "total_amount": 0.0,
                    "fund_count": 0,
                    "stock_name": info["stock_name"],
                }
                quarterly[stock_code] = {}
            stock_agg[stock_code]["fund_count"] += 1

            for q, amt in info.get("quarters", {}).items():
                stock_agg[stock_code]["total_amount"] += amt

                if q not in quarterly[stock_code]:
                    quarterly[stock_code][q] = {"amount": 0.0, "fund_count": 0}
                quarterly[stock_code][q]["amount"] += amt
                quarterly[stock_code][q]["fund_count"] += 1

    # 排序取 TopN
    sorted_stocks = sorted(
        stock_agg.items(),
        key=lambda x: x[1]["total_amount"],
        reverse=True,
    )
    top = sorted_stocks[:top_n]

    top_stocks = [
        {
            "rank": i + 1,
            "stock_code": code,
            "stock_name": info["stock_name"],
            "total_holding_amount": info["total_amount"],
            "fund_count": info["fund_count"],
            "quarterly_trend": [
                {
                    "quarter": q,
                    "amount": quarterly[code][q]["amount"],
                    "fund_count": quarterly[code][q]["fund_count"],
                }
                for q in sorted(quarterly.get(code, {}).keys())
            ],
        }
        for i, (code, info) in enumerate(top)
    ]

    return top_stocks, quarterly
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py::TestHoldingsFetch -v
```

预期：5 个测试全部 PASS。

- [ ] **步骤 5：Commit**

```bash
git add akshare-fund-holdings/scripts/fund_holdings.py akshare-fund-holdings/scripts/tests/test_fund_holdings.py
git commit -m "feat: implement fetch_fund_holdings and aggregate_holdings"
```

---

### 任务 6：CLI 入口与主流程编排

**文件：**
- 修改：`akshare-fund-holdings/scripts/fund_holdings.py`
- 修改：`akshare-fund-holdings/scripts/tests/test_fund_holdings.py`

- [ ] **步骤 1：编写 CLI 调度逻辑的测试**

在 `test_fund_holdings.py` 中追加 `TestCLIAndMainLogic` 类：

```python
class TestCLIAndMainLogic:
    """CLI 入口和主流程测试"""

    @patch("fund_holdings.fetch_fund_list")
    @patch("fund_holdings.fetch_fund_holdings")
    def test_main_output_json_format(self, mock_fetch_holdings, mock_fetch_list):
        """端到端测试：输出正确的 JSON 格式"""
        from io import StringIO

        mock_fetch_list.return_value = [
            {"基金代码": "510300", "基金简称": "沪深300ETF", "总募集规模": 3296860.0, "单位净值": 4.97},
            {"基金代码": "070011", "基金简称": "嘉实策略", "总募集规模": 4191700.0, "单位净值": 0.916},
        ]
        mock_fetch_holdings.return_value = {
            "600519": {
                "stock_name": "贵州茅台",
                "quarters": {"2026Q1": 1600000.0, "2025Q4": 1150000.0},
            },
        }

        # 模拟 argparse Namespace
        args = argparse.Namespace(
            top_n=2,
            min_scale=10.0,
            fund_types="股票型基金,混合型基金",
            workers=2,
        )

        buf = StringIO()
        with patch("sys.stdout", buf):
            exit_code = fund_holdings.main_with_args(args)

        assert exit_code == 0
        output = json.loads(buf.getvalue())
        assert "meta" in output
        assert "top_stocks" in output
        assert "errors" in output
        assert output["meta"]["top_n"] == 2
        assert output["meta"]["total_funds_fetched"] == 2
        assert output["meta"]["success_funds"] == 2
        assert len(output["top_stocks"]) == 1

    @patch("fund_holdings.fetch_fund_list")
    def test_main_no_funds_exit_code_1(self, mock_fetch_list):
        """没有基金通过过滤时返回 exit code 1"""
        from io import StringIO

        mock_fetch_list.return_value = []

        args = argparse.Namespace(
            top_n=100,
            min_scale=1000.0,
            fund_types="股票型基金",
            workers=2,
        )

        buf = StringIO()
        err_buf = StringIO()
        with patch("sys.stdout", buf), patch("sys.stderr", err_buf):
            exit_code = fund_holdings.main_with_args(args)

        assert exit_code == 1

    @patch("fund_holdings.ak")
    def test_full_pipeline_with_mock_apis(self, mock_ak):
        """完整流程测试：从基金列表到 JSON 输出"""
        from io import StringIO
        import pandas as pd

        # Mock 基金列表
        df_list = pd.DataFrame([
            {"基金代码": "510300", "基金简称": "沪深300ETF", "总募集规模": 3296860.0, "单位净值": 4.97},
            {"基金代码": "070011", "基金简称": "嘉实策略", "总募集规模": 4191700.0, "单位净值": 0.916},
        ])
        mock_ak.fund_scale_open_sina.return_value = df_list

        # Mock 持仓数据
        df_holdings = pd.DataFrame([
            {"序号": 1, "股票代码": "600519", "股票名称": "贵州茅台",
             "占净值比例": 4.74, "持仓市值": 1606717.16,
             "季度": "2026年1季度股票投资明细"},
            {"序号": 2, "股票代码": "300750", "股票名称": "宁德时代",
             "占净值比例": 3.23, "持仓市值": 1092918.96,
             "季度": "2026年1季度股票投资明细"},
        ])
        mock_ak.fund_portfolio_hold_em.return_value = df_holdings

        args = argparse.Namespace(
            top_n=2,
            min_scale=10.0,
            fund_types="股票型基金",
            workers=2,
        )

        buf = StringIO()
        with patch("sys.stdout", buf):
            exit_code = fund_holdings.main_with_args(args)

        assert exit_code == 0
        output = json.loads(buf.getvalue())
        assert output["meta"]["success_funds"] == 2
        assert len(output["top_stocks"]) == 2
        assert output["top_stocks"][0]["stock_code"] == "600519"
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py::TestCLIAndMainLogic -v
```

预期：全部 FAIL，`main_with_args` 未定义。

- [ ] **步骤 3：实现 CLI 入口和主流程**

在 `fund_holdings.py` 中追加：

```python
# ---- 主流程 ----

def _run_holdings_pipeline(
    funds: list[dict],
    target_quarters: list[tuple[str, str]],
    max_workers: int,
    cache_dir: Path,
) -> tuple[dict[str, dict], list[dict]]:
    """并发拉取所有基金持仓数据

    参数:
        funds: 基金列表
        target_quarters: 目标季度列表
        max_workers: 最大并发数
        cache_dir: 持仓缓存目录

    返回:
        (all_holdings, errors):
            all_holdings: {基金代码: {股票代码: holdings}}
            errors: 失败记录列表
    """
    all_holdings: dict[str, dict] = {}
    errors: list[dict] = []

    # 加载之前的失败记录
    failures_path = cache_dir / "failures.json"
    prev_failures = load_cache(failures_path) or {}
    
    # 将之前失败的基金也加入拉取队列
    failed_codes = set(prev_failures.keys())
    if failed_codes:
        print(f"Retrying {len(failed_codes)} previously failed funds...", file=sys.stderr)
    
    # 合并待拉取的基金列表（当前过滤的 + 之前失败的）
    # 之前失败的基金可能不满足当前规模门槛，但仍需重试以清理 failures
    all_codes_to_fetch = list(funds)
    for fc in failed_codes:
        if fc not in {f["基金代码"] for f in funds}:
            # 重建最小信息以便拉取
            all_codes_to_fetch.append({"基金代码": fc, "基金简称": fc, "总募集规模": 0, "单位净值": 0})

    # 确定最新可用季度（用于缓存有效性判断）
    latest_quarter = target_quarters[0][0] if target_quarters else ""

    holdings_cache_dir = cache_dir / "holdings"
    holdings_cache_dir.mkdir(parents=True, exist_ok=True)

    # 分离需要拉取和已缓存的基金
    to_fetch: list[dict] = []
    for fund in all_codes_to_fetch:
        code = fund["基金代码"]
        cache_path = holdings_cache_dir / f"{code}.json"
        if is_holdings_cache_valid(cache_path, date.today(), latest_quarter):
            cached = load_cache(cache_path)
            if cached and "holdings" in cached:
                all_holdings[code] = cached["holdings"]
                # 如果是之前失败的，成功后从 failures 中移除
                prev_failures.pop(code, None)
                continue
        to_fetch.append(fund)

    if to_fetch:
        print(
            f"Fetching holdings for {len(to_fetch)} funds "
            f"({len(all_codes_to_fetch) - len(to_fetch)} from cache)...",
            file=sys.stderr,
        )

        fetched = 0

        def _fetch_one(fund: dict) -> tuple[str, dict | None, str | None]:
            code = fund["基金代码"]
            result = fetch_fund_holdings(code, target_quarters)
            if result is not None:
                # 写入缓存
                cache_path = holdings_cache_dir / f"{code}.json"
                save_cache(cache_path, {
                    "fetch_time": _now_str(),
                    "quarters": [q for q, _ in target_quarters],
                    "holdings": result,
                })
                return code, result, None
            else:
                error_msg = "failed_after_retries"
                return code, None, error_msg

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_one, f): f for f in to_fetch}
            for future in as_completed(futures):
                code, result, error = future.result()
                if result is not None:
                    all_holdings[code] = result
                    prev_failures.pop(code, None)  # 成功后从 failures 移除
                else:
                    errors.append({"fund_code": code, "error": error})
                    prev_failures[code] = {"fund_code": code, "error": error}

                fetched += 1
                if fetched % 50 == 0 or fetched == len(to_fetch):
                    print(
                        f"  Progress: {fetched}/{len(to_fetch)}",
                        file=sys.stderr,
                    )

    # 保存更新后的 failures
    if prev_failures:
        save_cache(failures_path, prev_failures)
    elif failures_path.exists():
        failures_path.unlink()

    return all_holdings, errors


def _now_str() -> str:
    """当前时间字符串"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main_with_args(args: argparse.Namespace) -> int:
    """主流程：基金列表 → 持仓拉取 → 聚合 → 输出

    参数:
        args: argparse 解析后的参数

    返回:
        int: exit code
    """
    fund_types = [t.strip() for t in args.fund_types.split(",")]
    min_scale_yi = float(args.min_scale)

    # 确保缓存目录存在
    cache_dir = CACHE_BASE
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 尝试从缓存加载基金列表
    fund_list_cache = cache_dir / "fund_list.json"
    funds = None
    if is_cache_valid(fund_list_cache, ttl_hours=168, today=date.today()):
        cached = load_cache(fund_list_cache)
        if cached and "funds" in cached:
            # 验证类型和门槛匹配
            cached_types = set(cached.get("fund_types", []))
            cached_min_yi = cached.get("min_scale_yi", 0)
            if cached_types == set(fund_types) and cached_min_yi <= min_scale_yi:
                all_cached = cached["funds"]
                funds = [f for f in all_cached if f["总募集规模"] >= min_scale_yi * 10000]

    if funds is None:
        try:
            all_funds = fetch_fund_list(fund_types, min_scale_yi)
        except Exception as e:
            print(f"FATAL: Failed to fetch fund list: {e}", file=sys.stderr)
            return 2
        # 写入缓存
        save_cache(fund_list_cache, {
            "fetch_time": _now_str(),
            "fund_types": fund_types,
            "min_scale_yi": min_scale_yi,
            "funds": all_funds,
        })
        funds = all_funds

    if not funds:
        print(
            f"Warning: No funds match min_scale={min_scale_yi}亿. "
            f"Try lowering --min-scale.",
            file=sys.stderr,
        )
        json.dump({
            "meta": {"total_funds_fetched": 0, "error": "no_matching_funds"},
            "top_stocks": [],
            "errors": [],
        }, sys.stdout, ensure_ascii=False)
        return 1

    # 推断目标季度
    target_quarters = infer_target_quarters(date.today())
    quarter_labels = [q for q, _ in target_quarters]

    # 并发拉取持仓
    total_funds = len(funds)
    all_holdings, errors = _run_holdings_pipeline(
        funds, target_quarters, args.workers, cache_dir
    )

    # 聚合
    top_stocks, quarterly = aggregate_holdings(all_holdings, args.top_n)

    # 构建输出
    output = {
        "meta": {
            "fetch_time": _now_str(),
            "fund_types": fund_types,
            "min_scale_yi": min_scale_yi,
            "total_funds_fetched": total_funds,
            "success_funds": len(all_holdings),
            "failed_funds": len(errors),
            "quarters": quarter_labels,
            "top_n": args.top_n,
            "actual_top_n": len(top_stocks),
        },
        "top_stocks": top_stocks,
        "errors": errors,
    }

    json.dump(output, sys.stdout, ensure_ascii=False)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="基金抱团 TopN 股票分析")
    parser.add_argument(
        "--top-n", type=int, default=100,
        help="返回 TopN 股票 (默认: 100)",
    )
    parser.add_argument(
        "--min-scale", type=float, default=10.0,
        help="最低募集规模/亿元 (默认: 10)",
    )
    parser.add_argument(
        "--fund-types", type=str, default="股票型基金,混合型基金",
        help="基金类型，逗号分隔 (默认: 股票型基金,混合型基金)",
    )
    parser.add_argument(
        "--workers", type=int, default=8,
        help="并发 worker 数 (默认: 8)",
    )

    args = parser.parse_args()
    exit_code = main_with_args(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py::TestCLIAndMainLogic -v
```

预期：3 个测试全部 PASS。

- [ ] **步骤 5：运行全部单元测试确认**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py -v --ignore-glob="*integration*"
```

预期：所有单元测试通过（~19 个）。

- [ ] **步骤 6：Commit**

```bash
git add akshare-fund-holdings/scripts/fund_holdings.py akshare-fund-holdings/scripts/tests/test_fund_holdings.py
git commit -m "feat: implement CLI entry point and main pipeline"
```

---

### 任务 7：集成测试

**文件：**
- 修改：`akshare-fund-holdings/scripts/tests/test_fund_holdings.py`

- [ ] **步骤 1：编写集成测试**

在 `test_fund_holdings.py` 末尾追加：

```python
@pytest.mark.integration
class TestIntegration:
    """真实 API 集成测试"""

    def test_api_availability(self):
        """验证 fund_scale_open_sina 和 fund_portfolio_hold_em 可用"""
        import akshare as ak

        # 基金列表 API
        df = ak.fund_scale_open_sina(symbol="股票型基金")
        assert len(df) > 100
        assert "基金代码" in df.columns

        # 持仓 API
        df2 = ak.fund_portfolio_hold_em(symbol="510300", date="2025")
        assert len(df2) > 0
        assert "股票代码" in df2.columns

    def test_end_to_end_mini(self):
        """端到端测试: min_scale=500亿, top_n=5 (小规模快速验证)"""
        import subprocess

        script = os.path.join(
            os.path.dirname(__file__), "..", "fund_holdings.py"
        )
        result = subprocess.run(
            [
                sys.executable, script,
                "--min-scale", "500",
                "--top-n", "5",
                "--workers", "2",
            ],
            capture_output=True, text=True,
        )
        assert result.returncode in (0, 1)  # 0 成功，1 无基金（合理）

        output = json.loads(result.stdout)
        assert "meta" in output
        assert "top_stocks" in output
        assert "errors" in output
        meta = output["meta"]
        assert meta["top_n"] == 5
        assert isinstance(meta["total_funds_fetched"], int)

    def test_cache_reuse(self):
        """二次运行使用缓存，不发起新 API 请求 (通过速度判断)"""
        import subprocess
        import time

        script = os.path.join(
            os.path.dirname(__file__), "..", "fund_holdings.py"
        )
        # 第一次运行（不使用缓存的最快方式：高门槛 + 小 top_n）
        start = time.time()
        result1 = subprocess.run(
            [
                sys.executable, script,
                "--min-scale", "500",
                "--top-n", "3",
                "--workers", "2",
            ],
            capture_output=True, text=True,
        )
        elapsed1 = time.time() - start

        # 第二次运行（应使用缓存，更快）
        start = time.time()
        result2 = subprocess.run(
            [
                sys.executable, script,
                "--min-scale", "500",
                "--top-n", "3",
                "--workers", "2",
            ],
            capture_output=True, text=True,
        )
        elapsed2 = time.time() - start

        # 第二次应该几乎瞬间完成
        assert result1.returncode in (0, 1)
        assert result2.returncode in (0, 1)
        # 第二次输出应该与第一次一致
        assert result1.stdout == result2.stdout
        print(f"  Run 1: {elapsed1:.1f}s, Run 2: {elapsed2:.1f}s")

    def test_end_to_end_defaults(self):
        """端到端测试：默认参数 (min_scale=10亿, top_n=100)"""
        import subprocess

        script = os.path.join(
            os.path.dirname(__file__), "..", "fund_holdings.py"
        )
        result = subprocess.run(
            [
                sys.executable, script,
                "--top-n", "5",
                "--workers", "4",
            ],
            capture_output=True, text=True,
            timeout=120,
        )
        assert result.returncode == 0

        output = json.loads(result.stdout)
        meta = output["meta"]
        assert meta["min_scale_yi"] == 10.0
        assert len(output["top_stocks"]) <= 5
        # 验证 top_stocks 结构
        if output["top_stocks"]:
            s = output["top_stocks"][0]
            assert "stock_code" in s
            assert "stock_name" in s
            assert "total_holding_amount" in s
            assert "fund_count" in s
            assert "quarterly_trend" in s
```

- [ ] **步骤 2：运行集成测试（需网络）**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py::TestIntegration -v -m integration
```

预期：4 个集成测试全部 PASS。

- [ ] **步骤 3：Commit**

```bash
git add akshare-fund-holdings/scripts/tests/test_fund_holdings.py
git commit -m "test: add integration tests for fund-holdings skill"
```

---

### 任务 8：SKILL.md 和最终验证

**文件：**
- 创建：`akshare-fund-holdings/SKILL.md`

- [ ] **步骤 1：编写 SKILL.md**

写入 `akshare-fund-holdings/SKILL.md`：

```markdown
---
name: akshare-fund-holdings
description: Use when the user needs to analyze fund "herding" by calculating the TopN stocks with the highest aggregated holding value across equity and mixed-type mutual funds. Supports configurable fund scale threshold and top-N count.
---

# 基金抱团 TopN 股票分析

## 概述

基于 akshare 新浪财经公募基金数据，拉取股票型和混合型基金的前十大持仓，按股票聚合计算各基金持仓市值的总和，输出持仓最集中的 TopN 股票及其近 4 个季度趋势，供 AI 分析基金抱团方向。

## 使用方式

```bash
# 默认参数：min_scale=10亿, Top100
uv run python scripts/fund_holdings.py

# 自定义 TopN 和规模门槛
uv run python scripts/fund_holdings.py --top-n 50 --min-scale 20.0

# 仅股票型基金
uv run python scripts/fund_holdings.py --fund-types 股票型基金

# 调整并发数
uv run python scripts/fund_holdings.py --workers 4
```

JSON 输出到 stdout，运行进度和错误日志到 stderr。

## 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--top-n` | 100 | 返回 TopN 股票 |
| `--min-scale` | 10.0 | 最低总募集规模（亿元） |
| `--fund-types` | 股票型基金,混合型基金 | 基金类型，逗号分隔 |
| `--workers` | 8 | 并发 worker 数 |

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

- 金额单位：万元
- `quarterly_trend` 按季度升序排列
- 缓存目录：`~/.cache/akshare-fund-holdings/`

## 缓存策略

脚本始终使用缓存，按以下策略自动判断有效性：

| 缓存 | 路径 | 过期策略 |
|---|---|---|
| 基金列表 | `fund_list.json` | 7 天 |
| 持仓数据 | `holdings/{基金代码}.json` | 季度智能过期（缺少最新季度则重新拉取） |
| 失败记录 | `failures.json` | 持久保留，每次运行自动重试 |

## 依赖

```bash
uv pip install akshare pandas
```
```

- [ ] **步骤 2：运行全部测试最终验证**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py -v
```

预期：所有测试 PASS。

- [ ] **步骤 3：验证 CLI 输出格式**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run python akshare-fund-holdings/scripts/fund_holdings.py --min-scale 1000 --top-n 5 --workers 2 | python -m json.tool | head -40
```

预期：输出格式正确的 JSON，包含 `meta`, `top_stocks`, `errors`。

- [ ] **步骤 4：Commit**

```bash
git add akshare-fund-holdings/SKILL.md
git commit -m "docs: add SKILL.md for akshare-fund-holdings"
```

---

### 任务 9：更新配置注册 skill

**文件：**
- 修改：`CLAUDE.md` (将 skill 加入可用 skill 列表)
- 修改：`.gitignore`（如 `**/.cache/` 未添加）

- [ ] **步骤 1：检查 CLAUDE.md 是否需要更新**

读取 `CLAUDE.md`，确认项目的 skill 注册方式（是手动列出还是自动发现）。

- [ ] **步骤 2：更新并 commit**

```bash
git add CLAUDE.md
git commit -m "chore: register akshare-fund-holdings skill"
```
