# akshare-tech-selection 反爬虫适配与限流改造 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 去掉 akshare 库依赖，直接实现 20 个技术选股 API 的 HTTP 请求，引入全局 RateLimiter（每分钟 5 次），被反爬拦截时输出 AI 可读提示并 os._exit(1)

**架构：** ratelimit.py（滑动窗口限流器）→ engine.py（顺序调用，每次调用前 acquire）→ fetcher.py（20 个显式函数，每个独立 HTTP 请求 + 解析）。移除 ThreadPoolExecutor 和 --workers 参数。同花顺 11 个 API 需 _check_thx_blocked 反爬检测。

**技术栈：** Python 3, requests, BeautifulSoup, py_mini_racer, pandas

---

### 任务 1：ratelimit.py — 滑动窗口限流器 + 单元测试（TDD）

**文件：**
- 创建：`akshare-tech-selection/scripts/ratelimit.py`
- 创建：`akshare-tech-selection/scripts/tests/test_ratelimit.py`

- [ ] **步骤 1：编写失败的测试 — test_ratelimit.py**

```python
"""ratelimit 单元测试"""
import time
import pytest
from ratelimit import RateLimiter


class TestRateLimiter:
    def test_first_call_allowed_immediately(self):
        rl = RateLimiter(max_calls_per_minute=5)
        start = time.monotonic()
        rl.acquire(min_jitter=0, max_jitter=0)  # zero jitter for test
        elapsed = time.monotonic() - start
        assert elapsed < 0.01  # should be near-instant

    def test_exceed_limit_blocks(self):
        rl = RateLimiter(max_calls_per_minute=2)
        rl.acquire(min_jitter=0, max_jitter=0)
        rl.acquire(min_jitter=0, max_jitter=0)
        start = time.monotonic()
        rl.acquire(min_jitter=0, max_jitter=0)  # 3rd call, should block
        elapsed = time.monotonic() - start
        # should wait ~60s minus time since first call... at least 0.5s
        assert elapsed > 0.1

    def test_window_resets_after_60s(self):
        rl = RateLimiter(max_calls_per_minute=2)
        # Manually insert old timestamps
        rl._timestamps = [time.monotonic() - 70, time.monotonic() - 65]
        start = time.monotonic()
        rl.acquire(min_jitter=0, max_jitter=0)
        elapsed = time.monotonic() - start
        assert elapsed < 0.01  # old ones expired, no wait

    def test_cleans_expired_timestamps(self):
        rl = RateLimiter(max_calls_per_minute=5)
        rl._timestamps = [
            time.monotonic() - 120,
            time.monotonic() - 100,
            time.monotonic() - 80,
            time.monotonic() - 10,
        ]
        rl.acquire(min_jitter=0, max_jitter=0)
        # Only the one at -10s should remain + the new one
        assert len([t for t in rl._timestamps if t > time.monotonic() - 61]) == 2

    def test_zero_max_calls_always_blocks(self):
        rl = RateLimiter(max_calls_per_minute=0)
        start = time.monotonic()
        rl.acquire(min_jitter=0.01, max_jitter=0.01)  # non-zero to avoid infinite
        elapsed = time.monotonic() - start
        assert elapsed >= 0.01


class TestRateLimiterGlobalInstance:
    def test_global_instance_exists(self):
        from ratelimit import _RATE_LIMITER
        assert isinstance(_RATE_LIMITER, RateLimiter)
        assert _RATE_LIMITER._max_calls == 5
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_ratelimit.py -v 2>&1
```

预期：FAIL — `ratelimit` module 不存在

- [ ] **步骤 3：编写 ratelimit.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全局速率限制器 — 滑动窗口算法，每分钟最多 5 次 API 调用
"""
import time
import random


class RateLimiter:
    """滑动窗口限流器：每分钟最多 max_calls_per_minute 次调用"""

    def __init__(self, max_calls_per_minute: int = 5):
        self._max_calls = max_calls_per_minute
        self._timestamps: list[float] = []

    def acquire(self, min_jitter: float = 0.5, max_jitter: float = 2.0) -> None:
        """
        阻塞直到可以发起新调用。
        1. 清理 60 秒之前的记录
        2. 如果窗口内已有 _max_calls 次 → sleep(剩余时间 + 随机 jitter)
        3. 否则直接放行 + 记录当前时间戳
        """
        now = time.monotonic()
        # 清理过期记录
        cutoff = now - 60.0
        self._timestamps = [t for t in self._timestamps if t > cutoff]

        if self._max_calls <= 0:
            time.sleep(random.uniform(min_jitter, max_jitter))
            self._timestamps.append(time.monotonic())
            return

        if len(self._timestamps) >= self._max_calls:
            # 窗口已满，需要等待最老的记录过期
            oldest = min(self._timestamps)
            wait = 60.0 - (now - oldest)
            if wait > 0:
                jitter = random.uniform(min_jitter, max_jitter)
                time.sleep(wait + jitter)

        self._timestamps.append(time.monotonic())


# 全局单例，所有 API 调用共享
_RATE_LIMITER = RateLimiter(max_calls_per_minute=5)
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_ratelimit.py -v 2>&1
```

预期：PASS（注意 `TestRateLimiterGlobalInstance` 的 test 需要同目录下能 import ratelimit；如果失败，检查 `sys.path` 或直接用 `python -c "from ratelimit import _RATE_LIMITER"` 确认）

- [ ] **步骤 5：确认全局实例导入正常**

```bash
cd akshare-tech-selection/scripts && python -c "from ratelimit import _RATE_LIMITER; print(type(_RATE_LIMITER).__name__, _RATE_LIMITER._max_calls)"
```

预期：`RateLimiter 5`

- [ ] **步骤 6：提交**

```bash
cd akshare-tech-selection && git add scripts/ratelimit.py scripts/tests/test_ratelimit.py && git commit -m "feat: add RateLimiter with sliding window (max 5 calls/min)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 2：fetcher.py — 工具函数 + 反爬检测 + ALL_INDICATORS（保留现有）

**文件：**
- 修改：`akshare-tech-selection/scripts/fetcher.py`

这一步保留已有的工具函数和常量，删除 akshare 依赖和 `_make_fetcher` 闭包生成逻辑，添加反爬检测函数。

- [ ] **步骤 1：重写 fetcher.py（仅工具函数 + ALL_INDICATORS + 反爬检测，不含 20 个 fetcher 实现）**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
技术指标选股 — 数据获取层
直接 HTTP 请求 20 个技术选股 API，统一列名标准化和代码格式
"""
import os
import sys
import re
import time
from io import StringIO

import pandas as pd
import numpy as np
import requests
import py_mini_racer
from bs4 import BeautifulSoup

from akshare.datasets import get_ths_js


# ---- 常量 ----

ALL_INDICATORS = [
    # 第 1 类：同花顺技术指标 (11 个)
    {
        "name": "fetch_cxg_ths",
        "api": "stock_rank_cxg_ths",
        "category": "创新高",
        "categories": ["同花顺技术指标", "趋势类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": True,
        "default_symbol": "创月新高",
        "needs_date": False,
    },
    {
        "name": "fetch_cxd_ths",
        "api": "stock_rank_cxd_ths",
        "category": "创新低",
        "categories": ["同花顺技术指标", "趋势类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": True,
        "default_symbol": "创月新低",
        "needs_date": False,
    },
    {
        "name": "fetch_lxsz_ths",
        "api": "stock_rank_lxsz_ths",
        "category": "连续上涨",
        "categories": ["同花顺技术指标", "趋势类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_lxxd_ths",
        "api": "stock_rank_lxxd_ths",
        "category": "连续下跌",
        "categories": ["同花顺技术指标", "趋势类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_cxfl_ths",
        "api": "stock_rank_cxfl_ths",
        "category": "持续放量",
        "categories": ["同花顺技术指标", "量价类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_cxsl_ths",
        "api": "stock_rank_cxsl_ths",
        "category": "持续缩量",
        "categories": ["同花顺技术指标", "量价类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_xstp_ths",
        "api": "stock_rank_xstp_ths",
        "category": "向上突破",
        "categories": ["同花顺技术指标", "突破类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": True,
        "default_symbol": "500日均线",
        "needs_date": False,
    },
    {
        "name": "fetch_xxtp_ths",
        "api": "stock_rank_xxtp_ths",
        "category": "向下突破",
        "categories": ["同花顺技术指标", "突破类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": True,
        "default_symbol": "500日均线",
        "needs_date": False,
    },
    {
        "name": "fetch_ljqs_ths",
        "api": "stock_rank_ljqs_ths",
        "category": "量价齐升",
        "categories": ["同花顺技术指标", "量价类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_ljqd_ths",
        "api": "stock_rank_ljqd_ths",
        "category": "量价齐跌",
        "categories": ["同花顺技术指标", "量价类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_xzjp_ths",
        "api": "stock_rank_xzjp_ths",
        "category": "险资举牌",
        "categories": ["同花顺技术指标", "资金类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    # 第 2 类：巨潮资讯 (1 个)
    {
        "name": "fetch_forecast_cninfo",
        "api": "stock_rank_forecast_cninfo",
        "category": "机构评级",
        "categories": ["同花顺技术指标", "评级类"],
        "code_col": "证券代码",
        "name_col": "证券简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    # 第 3 类：涨停板分析 (6 个)
    {
        "name": "fetch_zt_pool_strong",
        "api": "stock_zt_pool_strong_em",
        "category": "强势涨停",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    {
        "name": "fetch_zt_pool",
        "api": "stock_zt_pool_em",
        "category": "涨停池",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    {
        "name": "fetch_zt_pool_dtgc",
        "api": "stock_zt_pool_dtgc_em",
        "category": "跌停股池",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    {
        "name": "fetch_zt_pool_sub_new",
        "api": "stock_zt_pool_sub_new_em",
        "category": "次新股池",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    {
        "name": "fetch_zt_pool_previous",
        "api": "stock_zt_pool_previous_em",
        "category": "昨日涨停表现",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    {
        "name": "fetch_zt_pool_zbgc",
        "api": "stock_zt_pool_zbgc_em",
        "category": "炸板股池",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    # 第 4 类：异动监控 (2 个)
    {
        "name": "fetch_board_change",
        "api": "stock_board_change_em",
        "category": "板块异动",
        "categories": ["异动监控"],
        "code_col": "板块异动最频繁个股及所属类型-股票代码",
        "name_col": "板块异动最频繁个股及所属类型-股票名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_changes",
        "api": "stock_changes_em",
        "category": "个股异动",
        "categories": ["异动监控"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": True,
        "default_symbol": "大笔买入",
        "needs_date": False,
    },
]

# 按名称快速查找
INDICATOR_MAP = {ind["name"]: ind for ind in ALL_INDICATORS}

# 导出列表
__all__ = [ind["name"] for ind in ALL_INDICATORS]


# ---- 同花顺 JS 解密 ----

def _get_file_content_ths(file: str = "ths.js") -> str:
    """获取同花顺 JS 文件内容"""
    setting_file_path = get_ths_js(file)
    with open(setting_file_path, encoding="utf-8") as f:
        file_data = f.read()
    return file_data


# ---- 反爬检测 ----

def _check_thx_blocked(response: requests.Response, api_name: str) -> None:
    """
    检测同花顺/巨潮 API 是否被反爬拦截。
    命中则输出 AI 可读提示并 os._exit(1)。
    """
    if response.status_code == 403:
        print(
            f"[BLOCKED] {api_name}: HTTP 403 Forbidden — "
            f"被反爬虫系统拦截，请等待 1 小时后重试",
            file=sys.stderr,
        )
        os._exit(1)
    # 部分情况返回 200 但内容是验证页面
    text_lower = response.text.lower()
    block_signals = ["验证", "滑块", "captcha", "请在下方输入"]
    if any(s in text_lower for s in block_signals) or len(response.text.strip()) < 200:
        print(
            f"[BLOCKED] {api_name}: 返回异常页面 — "
            f"被反爬虫系统拦截，请等待 1 小时后重试",
            file=sys.stderr,
        )
        os._exit(1)


# ---- 工具函数 ----

def normalize_stock_code(code: str | None) -> str | None:
    """标准化股票代码：去除 SZ/SH/BJ 等前缀，补零到 6 位"""
    if code is None:
        return None
    code = str(code).strip().upper()
    if code == "":
        return ""
    for prefix in ("SZ", "SH", "BJ"):
        if code.startswith(prefix):
            code = code[len(prefix):]
    code = code.zfill(6)
    return code


def _nan_to_none(obj):
    """递归将 NaN 转为 None（用于 JSON 序列化）"""
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _nan_to_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_nan_to_none(v) for v in obj]
    return obj


def standardize_output(
    df: pd.DataFrame | None,
    code_col: str,
    name_col: str,
    indicator: str,
    category: str,
    categories: list[str],
) -> dict | None:
    """将 DataFrame 转为标准化 dict。"""
    if df is None or df.empty:
        return None
    df = df.copy()
    df = df.where(df.notna(), None)
    records = df.to_dict(orient="records")
    for record in records:
        if code_col in record:
            record["stock_code"] = normalize_stock_code(record.get(code_col))
        else:
            record["stock_code"] = None
        record["stock_name"] = record.get(name_col)
    records = _nan_to_none(records)
    return {
        "indicator": indicator,
        "category": category,
        "categories": categories,
        "count": len(records),
        "data": records,
    }


# ---- 20 个 Fetcher 函数 ----
# （以下由后续任务填充）
```

- [ ] **步骤 2：确认 fetcher.py 可导入（此时 20 个函数尚不存在，engine 会报错）**

```bash
cd akshare-tech-selection/scripts && python -c "import fetcher; print(len(fetcher.ALL_INDICATORS)); print(fetcher.normalize_stock_code('SH600519'))"
```

预期：`20` 和 `600519`

- [ ] **步骤 3：运行现有测试确认基本工具函数仍可用**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_fetcher.py::TestNormalizeStockCode scripts/tests/test_fetcher.py::TestStandardizeOutput scripts/tests/test_fetcher.py::TestIndicatorRegistry scripts/tests/test_fetcher.py::TestStockCodeCompatibility -v 2>&1
```

预期：PASS

- [ ] **步骤 4：提交**

```bash
cd akshare-tech-selection && git add scripts/fetcher.py && git commit -m "refactor: rewrite fetcher.py skeleton — remove akshare dep, add anti-crawl, keep helpers

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 3：fetcher.py — 同花顺 11 个 fetcher 实现

**文件：**
- 修改：`akshare-tech-selection/scripts/fetcher.py`

在 fetcher.py 末尾的 "20 个 Fetcher 函数" 注释下方，添加 11 个同花顺 fetcher。从 akshare 源码复制逻辑，`exit()` 替换为 `_check_thx_blocked()`，去掉 tqdm。

- [ ] **步骤 1：在 fetcher.py 末尾追加 11 个同花顺 fetcher**

在 `# ---- 20 个 Fetcher 函数 ----` 注释之后追加以下代码。注意需要先确保 fetcher.py 顶部有 `from datetime import datetime`。

先确认 fetcher.py 顶部 import 齐全——需要在现有 import 中追加：

```python
from datetime import datetime
```

然后在 `# ---- 20 个 Fetcher 函数 ----` 之后追加：

```python
# ======== 同花顺技术指标 (11 个) ========

def fetch_cxg_ths(symbol: str = "创月新高", date: str | None = None) -> dict | None:
    """创新高"""
    symbol_map = {"创月新高": "4", "半年新高": "3", "一年新高": "2", "历史新高": "1"}
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = f"http://data.10jqka.com.cn/rank/cxg/board/{symbol_map[symbol]}/field/stockcode/order/asc/page/1/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_cxg_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/cxg/board/{symbol_map[symbol]}/field/stockcode/order/asc/page/{page}/ajax/1/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_cxg_ths")
        html_fixed = re.sub(r'\srowspan="\d+"', '', r.text)
        temp_df = pd.read_html(StringIO(html_fixed), header=0)[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "涨跌幅", "换手率", "最新价", "前期高点", "前期高点日期"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].str.strip("%")
    big_df["换手率"] = big_df["换手率"].str.strip("%")
    big_df["前期高点日期"] = pd.to_datetime(big_df["前期高点日期"], errors="coerce").dt.date
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["前期高点"] = pd.to_numeric(big_df["前期高点"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_cxg_ths", "创新高", ["同花顺技术指标", "趋势类"])


def fetch_cxd_ths(symbol: str = "创月新低", date: str | None = None) -> dict | None:
    """创新低"""
    symbol_map = {"创月新低": "4", "半年新低": "3", "一年新低": "2", "历史新低": "1"}
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = f"http://data.10jqka.com.cn/rank/cxd/board/{symbol_map[symbol]}/field/stockcode/order/asc/page/1/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_cxd_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/cxd/board/{symbol_map[symbol]}/field/stockcode/order/asc/page/{page}/ajax/1/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_cxd_ths")
        temp_df = pd.read_html(StringIO(r.text))[0].iloc[:, :-1]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "涨跌幅", "换手率", "最新价", "前期低点", "前期低点日期"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].str.strip("%")
    big_df["换手率"] = big_df["换手率"].str.strip("%")
    big_df["前期低点日期"] = pd.to_datetime(big_df["前期低点日期"], errors="coerce").dt.date
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["前期低点"] = pd.to_numeric(big_df["前期低点"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_cxd_ths", "创新低", ["同花顺技术指标", "趋势类"])


def fetch_lxsz_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """连续上涨"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/lxsz/field/lxts/order/desc/page/1/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_lxsz_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/lxsz/field/lxts/order/desc/page/{page}/ajax/1/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_lxsz_ths")
        temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "收盘价", "最高价", "最低价", "连涨天数", "连续涨跌幅", "累计换手率", "所属行业"]
    big_df["连续涨跌幅"] = big_df["连续涨跌幅"].str.strip("%")
    big_df["累计换手率"] = big_df["累计换手率"].str.strip("%")
    big_df["连续涨跌幅"] = pd.to_numeric(big_df["连续涨跌幅"], errors="coerce")
    big_df["累计换手率"] = pd.to_numeric(big_df["累计换手率"], errors="coerce")
    big_df["收盘价"] = pd.to_numeric(big_df["收盘价"], errors="coerce")
    big_df["最高价"] = pd.to_numeric(big_df["最高价"], errors="coerce")
    big_df["最低价"] = pd.to_numeric(big_df["最低价"], errors="coerce")
    big_df["连涨天数"] = pd.to_numeric(big_df["连涨天数"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_lxsz_ths", "连续上涨", ["同花顺技术指标", "趋势类"])


def fetch_lxxd_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """连续下跌"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/lxxd/field/lxts/order/desc/page/1/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_lxxd_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/lxxd/field/lxts/order/desc/page/{page}/ajax/1/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_lxxd_ths")
        temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "收盘价", "最高价", "最低价", "连涨天数", "连续涨跌幅", "累计换手率", "所属行业"]
    big_df["连续涨跌幅"] = big_df["连续涨跌幅"].str.strip("%")
    big_df["累计换手率"] = big_df["累计换手率"].str.strip("%")
    big_df["连续涨跌幅"] = pd.to_numeric(big_df["连续涨跌幅"], errors="coerce")
    big_df["累计换手率"] = pd.to_numeric(big_df["累计换手率"], errors="coerce")
    big_df["收盘价"] = pd.to_numeric(big_df["收盘价"], errors="coerce")
    big_df["最高价"] = pd.to_numeric(big_df["最高价"], errors="coerce")
    big_df["最低价"] = pd.to_numeric(big_df["最低价"], errors="coerce")
    big_df["连涨天数"] = pd.to_numeric(big_df["连涨天数"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_lxxd_ths", "连续下跌", ["同花顺技术指标", "趋势类"])


def fetch_cxfl_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """持续放量"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/cxfl/field/count/order/desc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_cxfl_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/cxfl/field/count/order/desc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_cxfl_ths")
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='m-table J-ajax-table')
        data = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 10:
                    item = {
                        '序号': cols[0].text.strip(),
                        '股票代码': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                        '股票简称': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                        '涨跌幅': cols[3].text.strip(),
                        '最新价': cols[4].text.strip(),
                        '成交量': cols[5].text.strip(),
                        '基准日成交量': cols[6].text.strip(),
                        '放量天数': cols[7].text.strip(),
                        '阶段涨跌幅': cols[8].text.strip(),
                        '所属行业': cols[9].find('a').text.strip() if cols[9].find('a') else cols[9].text.strip(),
                    }
                    data.append(item)
        temp_df = pd.DataFrame(data)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "涨跌幅", "最新价", "成交量", "基准日成交量", "放量天数", "阶段涨跌幅", "所属行业"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.strip("%")
    big_df["阶段涨跌幅"] = big_df["阶段涨跌幅"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["阶段涨跌幅"] = pd.to_numeric(big_df["阶段涨跌幅"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["放量天数"] = pd.to_numeric(big_df["放量天数"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_cxfl_ths", "持续放量", ["同花顺技术指标", "量价类"])


def fetch_cxsl_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """持续缩量"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/cxsl/field/count/order/desc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_cxsl_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/cxsl/field/count/order/desc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_cxsl_ths")
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='m-table J-ajax-table')
        data = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 10:
                    item = {
                        '序号': cols[0].text.strip(),
                        '股票代码': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                        '股票简称': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                        '涨跌幅': cols[3].text.strip(),
                        '最新价': cols[4].text.strip(),
                        '成交量': cols[5].text.strip(),
                        '基准日成交量': cols[6].text.strip(),
                        '放量天数': cols[7].text.strip(),
                        '阶段涨跌幅': cols[8].text.strip(),
                        '所属行业': cols[9].find('a').text.strip() if cols[9].find('a') else cols[9].text.strip(),
                    }
                    data.append(item)
        temp_df = pd.DataFrame(data)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "涨跌幅", "最新价", "成交量", "基准日成交量", "缩量天数", "阶段涨跌幅", "所属行业"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.strip("%")
    big_df["阶段涨跌幅"] = big_df["阶段涨跌幅"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["阶段涨跌幅"] = pd.to_numeric(big_df["阶段涨跌幅"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["缩量天数"] = pd.to_numeric(big_df["缩量天数"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_cxsl_ths", "持续缩量", ["同花顺技术指标", "量价类"])


def fetch_xstp_ths(symbol: str = "500日均线", date: str | None = None) -> dict | None:
    """向上突破均线"""
    symbol_map = {"5日均线": 5, "10日均线": 10, "20日均线": 20, "30日均线": 30, "60日均线": 60, "90日均线": 90, "250日均线": 250, "500日均线": 500}
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = f"http://data.10jqka.com.cn/rank/xstp/board/{symbol_map[symbol]}/order/asc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_xstp_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/xstp/board/{symbol_map[symbol]}/order/asc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_xstp_ths")
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='m-table J-ajax-table')
        data = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 8:
                    item = {
                        '序号': cols[0].text.strip(),
                        '股票代码': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                        '股票简称': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                        '最新价': cols[3].text.strip(),
                        '成交额': cols[4].text.strip(),
                        '成交量': cols[5].text.strip(),
                        '涨跌幅': cols[6].text.strip(),
                        '换手率': cols[7].text.strip(),
                    }
                    data.append(item)
        temp_df = pd.DataFrame(data)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "最新价", "成交额", "成交量", "涨跌幅", "换手率"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.strip("%")
    big_df["换手率"] = big_df["换手率"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_xstp_ths", "向上突破", ["同花顺技术指标", "突破类"])


def fetch_xxtp_ths(symbol: str = "500日均线", date: str | None = None) -> dict | None:
    """向下突破均线"""
    symbol_map = {"5日均线": 5, "10日均线": 10, "20日均线": 20, "30日均线": 30, "60日均线": 60, "90日均线": 90, "250日均线": 250, "500日均线": 500}
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = f"http://data.10jqka.com.cn/rank/xxtp/board/{symbol_map[symbol]}/order/asc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_xxtp_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/xxtp/board/{symbol_map[symbol]}/order/asc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_xxtp_ths")
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='m-table J-ajax-table')
        data = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 8:
                    item = {
                        '序号': cols[0].text.strip(),
                        '股票代码': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                        '股票简称': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                        '最新价': cols[3].text.strip(),
                        '成交额': cols[4].text.strip(),
                        '成交量': cols[5].text.strip(),
                        '涨跌幅': cols[6].text.strip(),
                        '换手率': cols[7].text.strip(),
                    }
                    data.append(item)
        temp_df = pd.DataFrame(data)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "最新价", "成交额", "成交量", "涨跌幅", "换手率"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.strip("%")
    big_df["换手率"] = big_df["换手率"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_xxtp_ths", "向下突破", ["同花顺技术指标", "突破类"])


def fetch_ljqs_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """量价齐升"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/ljqs/field/count/order/desc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_ljqs_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/ljqs/field/count/order/desc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_ljqs_ths")
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='m-table J-ajax-table')
        data = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 8:
                    item = {
                        '序号': cols[0].text.strip(),
                        '股票代码': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                        '股票简称': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                        '最新价': cols[3].text.strip(),
                        '量价齐升天数': cols[4].text.strip(),
                        '阶段涨幅': cols[5].text.strip(),
                        '累计换手率': cols[6].text.strip(),
                        '所属行业': cols[7].find('a').text.strip() if cols[7].find('a') else cols[7].text.strip(),
                    }
                    data.append(item)
        temp_df = pd.DataFrame(data)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "最新价", "量价齐升天数", "阶段涨幅", "累计换手率", "所属行业"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["阶段涨幅"] = big_df["阶段涨幅"].astype(str).str.strip("%")
    big_df["累计换手率"] = big_df["累计换手率"].astype(str).str.strip("%")
    big_df["阶段涨幅"] = pd.to_numeric(big_df["阶段涨幅"], errors="coerce")
    big_df["累计换手率"] = pd.to_numeric(big_df["累计换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["量价齐升天数"] = pd.to_numeric(big_df["量价齐升天数"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_ljqs_ths", "量价齐升", ["同花顺技术指标", "量价类"])


def fetch_ljqd_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """量价齐跌"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/ljqd/field/count/order/desc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_ljqd_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/ljqd/field/count/order/desc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_ljqd_ths")
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='m-table J-ajax-table')
        data = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 8:
                    item = {
                        '序号': cols[0].text.strip(),
                        '股票代码': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                        '股票简称': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                        '最新价': cols[3].text.strip(),
                        '量价齐跌天数': cols[4].text.strip(),
                        '阶段涨幅': cols[5].text.strip(),
                        '累计换手率': cols[6].text.strip(),
                        '所属行业': cols[7].find('a').text.strip() if cols[7].find('a') else cols[7].text.strip(),
                    }
                    data.append(item)
        temp_df = pd.DataFrame(data)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "最新价", "量价齐跌天数", "阶段涨幅", "累计换手率", "所属行业"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["阶段涨幅"] = big_df["阶段涨幅"].astype(str).str.strip("%")
    big_df["累计换手率"] = big_df["累计换手率"].astype(str).str.strip("%")
    big_df["阶段涨幅"] = pd.to_numeric(big_df["阶段涨幅"], errors="coerce")
    big_df["累计换手率"] = pd.to_numeric(big_df["累计换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["量价齐跌天数"] = pd.to_numeric(big_df["量价齐跌天数"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_ljqd_ths", "量价齐跌", ["同花顺技术指标", "量价类"])


def fetch_xzjp_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """险资举牌"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/ajax/xzjp/field/DECLAREDATE/order/desc/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_xzjp_ths")
    soup = BeautifulSoup(r.text, 'html.parser')
    table = soup.find('table', class_='m-table J-ajax-table')
    data = []
    if table:
        rows = table.find('tbody').find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 8:
                item = {
                    '序号': cols[0].text.strip(),
                    '举牌公告日': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                    '股票代码': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                    '股票简称': cols[3].text.strip(),
                    '现价': cols[4].text.strip(),
                    '涨跌幅': cols[5].text.strip(),
                    '举牌方': cols[6].text.strip(),
                    '增持数量': cols[7].find('a').text.strip() if cols[7].find('a') else cols[7].text.strip(),
                    '交易均价': cols[8].find('a').text.strip() if cols[8].find('a') else cols[8].text.strip(),
                    '增持数量占总股本比例': cols[9].find('a').text.strip() if cols[9].find('a') else cols[9].text.strip(),
                    '变动后持股总数': cols[10].find('a').text.strip() if cols[10].find('a') else cols[10].text.strip(),
                    '变动后持股比例': cols[11].find('a').text.strip() if cols[11].find('a') else cols[11].text.strip(),
                    '历史数据': cols[12].find('a').text.strip() if cols[12].find('a') else cols[12].text.strip(),
                }
                data.append(item)
    big_df = pd.DataFrame(data)
    big_df.columns = ["序号", "举牌公告日", "股票代码", "股票简称", "现价", "涨跌幅", "举牌方", "增持数量", "交易均价", "增持数量占总股本比例", "变动后持股总数", "变动后持股比例", "历史数据"]
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.zfill(6)
    big_df["增持数量占总股本比例"] = big_df["增持数量占总股本比例"].astype(str).str.strip("%")
    big_df["变动后持股比例"] = big_df["变动后持股比例"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["增持数量占总股本比例"] = pd.to_numeric(big_df["增持数量占总股本比例"], errors="coerce")
    big_df["变动后持股比例"] = pd.to_numeric(big_df["变动后持股比例"], errors="coerce")
    big_df["举牌公告日"] = pd.to_datetime(big_df["举牌公告日"], errors="coerce").dt.date
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["现价"] = pd.to_numeric(big_df["现价"], errors="coerce")
    big_df["交易均价"] = pd.to_numeric(big_df["交易均价"], errors="coerce")
    del big_df["历史数据"]
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_xzjp_ths", "险资举牌", ["同花顺技术指标", "资金类"])
```

- [ ] **步骤 2：验证 11 个同花顺 fetcher 函数存在并可导入**

```bash
cd akshare-tech-selection/scripts && python -c "
import fetcher
names = ['fetch_cxg_ths', 'fetch_cxd_ths', 'fetch_lxsz_ths', 'fetch_lxxd_ths', 'fetch_cxfl_ths', 'fetch_cxsl_ths', 'fetch_xstp_ths', 'fetch_xxtp_ths', 'fetch_ljqs_ths', 'fetch_ljqd_ths', 'fetch_xzjp_ths']
for n in names:
    fn = getattr(fetcher, n, None)
    print(f'{n}: {\"OK\" if fn else \"MISSING\"}')"
```

预期：所有 11 个显示 OK

- [ ] **步骤 3：提交**

```bash
cd akshare-tech-selection && git add scripts/fetcher.py && git commit -m "feat: add 11 ths fetcher implementations with anti-crawl checks

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 4：fetcher.py — 巨潮 1 个 + 东方财富 8 个 fetcher 实现

**文件：**
- 修改：`akshare-tech-selection/scripts/fetcher.py`

- [ ] **步骤 1：在 fetcher.py 末尾追加 9 个剩余 fetcher**

在 `fetch_xzjp_ths` 之后追加：

```python
# ======== 巨潮资讯 (1 个) ========

def fetch_forecast_cninfo(symbol: str | None = None, date: str = "20230817") -> dict | None:
    """机构评级预测"""
    # 巨潮 JS 解密
    def _get_file_content_cninfo(file: str = "cninfo.js") -> str:
        setting_file_path = get_ths_js(file)
        with open(setting_file_path, encoding="utf-8") as f:
            file_data = f.read()
        return file_data

    url = "http://webapi.cninfo.com.cn/api/sysapi/p_sysapi1089"
    params = {"tdate": "-".join([date[:4], date[4:6], date[6:]])}
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_cninfo("cninfo.js")
    js_code.eval(js_content)
    mcode = js_code.call("getResCode1")
    headers = {
        "Accept": "*/*",
        "Accept-Enckey": mcode,
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "0",
        "Host": "webapi.cninfo.com.cn",
        "Origin": "http://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "http://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.post(url, params=params, headers=headers)
    _check_thx_blocked(r, "fetch_forecast_cninfo")
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "证券简称", "发布日期", "前一次投资评级", "评级变化", "目标价格-上限",
        "是否首次评级", "投资评级", "研究员名称", "研究机构简称", "目标价格-下限", "证券代码",
    ]
    temp_df = temp_df[["证券代码", "证券简称", "发布日期", "研究机构简称", "研究员名称",
                        "投资评级", "是否首次评级", "评级变化", "前一次投资评级",
                        "目标价格-下限", "目标价格-上限"]]
    temp_df["目标价格-上限"] = pd.to_numeric(temp_df["目标价格-上限"], errors="coerce")
    temp_df["目标价格-下限"] = pd.to_numeric(temp_df["目标价格-下限"], errors="coerce")
    return standardize_output(temp_df, "证券代码", "证券简称", "fetch_forecast_cninfo", "机构评级", ["同花顺技术指标", "评级类"])


# ======== 东方财富涨停板 (6 个) ========

def fetch_zt_pool_strong(symbol: str | None = None, date: str = "20241231") -> dict | None:
    """强势涨停池"""
    url = "https://push2ex.eastmoney.com/getTopicQSPool"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "5000",
        "sort": "zdp:desc",
        "date": date,
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        if data_json["data"] is None:
            return None
        if len(data_json["data"]["pool"]) == 0:
            return None
        temp_df = pd.DataFrame(data_json["data"]["pool"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.columns = [
            "序号", "代码", "_", "名称", "最新价", "涨停价", "_", "涨跌幅", "成交额",
            "流通市值", "总市值", "换手率", "是否新高", "入选理由", "量比", "涨速", "涨停统计", "所属行业",
        ]
        temp_df["涨停统计"] = (
            temp_df["涨停统计"].apply(lambda x: dict(x)["days"]).astype(str)
            + "/" + temp_df["涨停统计"].apply(lambda x: dict(x)["ct"]).astype(str)
        )
        temp_df = temp_df[["序号", "代码", "名称", "涨跌幅", "最新价", "涨停价", "成交额",
                            "流通市值", "总市值", "换手率", "涨速", "是否新高", "量比",
                            "涨停统计", "入选理由", "所属行业"]]
        temp_df["最新价"] = temp_df["最新价"] / 1000
        temp_df["涨停价"] = temp_df["涨停价"] / 1000
        explained_map = {1: "60日新高", 2: "近期多次涨停", 3: "60日新高且近期多次涨停"}
        temp_df["入选理由"] = temp_df["入选理由"].apply(lambda x: explained_map[x])
        temp_df["是否新高"] = temp_df["是否新高"].apply(lambda x: "是" if x == 1 else "否")
        temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        temp_df["涨停价"] = pd.to_numeric(temp_df["涨停价"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
        temp_df["流通市值"] = pd.to_numeric(temp_df["流通市值"], errors="coerce")
        temp_df["总市值"] = pd.to_numeric(temp_df["总市值"], errors="coerce")
        temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
        temp_df["涨速"] = pd.to_numeric(temp_df["涨速"], errors="coerce")
        temp_df["量比"] = pd.to_numeric(temp_df["量比"], errors="coerce")
        return standardize_output(temp_df, "代码", "名称", "fetch_zt_pool_strong", "强势涨停", ["涨停板分析"])
    except Exception:
        return None


def fetch_zt_pool(symbol: str | None = None, date: str = "20241008") -> dict | None:
    """涨停池"""
    url = "https://push2ex.eastmoney.com/getTopicZTPool"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "10000",
        "sort": "fbt:asc",
        "date": date,
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        if data_json["data"] is None:
            return None
        if len(data_json["data"]["pool"]) == 0:
            return None
        temp_df = pd.DataFrame(data_json["data"]["pool"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.columns = [
            "序号", "代码", "_", "名称", "最新价", "涨跌幅", "成交额", "流通市值", "总市值",
            "换手率", "连板数", "首次封板时间", "最后封板时间", "封板资金", "炸板次数", "所属行业", "涨停统计",
        ]
        temp_df["涨停统计"] = (
            temp_df["涨停统计"].apply(lambda x: dict(x)["days"]).astype(str)
            + "/" + temp_df["涨停统计"].apply(lambda x: dict(x)["ct"]).astype(str)
        )
        temp_df = temp_df[["序号", "代码", "名称", "涨跌幅", "最新价", "成交额", "流通市值", "总市值",
                            "换手率", "封板资金", "首次封板时间", "最后封板时间", "炸板次数",
                            "涨停统计", "连板数", "所属行业"]]
        temp_df["首次封板时间"] = temp_df["首次封板时间"].astype(str).str.zfill(6)
        temp_df["最后封板时间"] = temp_df["最后封板时间"].astype(str).str.zfill(6)
        temp_df["最新价"] = temp_df["最新价"] / 1000
        temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
        temp_df["流通市值"] = pd.to_numeric(temp_df["流通市值"], errors="coerce")
        temp_df["总市值"] = pd.to_numeric(temp_df["总市值"], errors="coerce")
        temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
        temp_df["封板资金"] = pd.to_numeric(temp_df["封板资金"], errors="coerce")
        temp_df["炸板次数"] = pd.to_numeric(temp_df["炸板次数"], errors="coerce")
        temp_df["连板数"] = pd.to_numeric(temp_df["连板数"], errors="coerce")
        return standardize_output(temp_df, "代码", "名称", "fetch_zt_pool", "涨停池", ["涨停板分析"])
    except Exception:
        return None


def fetch_zt_pool_dtgc(symbol: str | None = None, date: str = "20241011") -> dict | None:
    """跌停股池"""
    thirty_days_ago = datetime.now() - pd.Timedelta(days=30)
    thirty_days_ago_str = thirty_days_ago.strftime("%Y%m%d")
    if int(date) < int(thirty_days_ago_str):
        raise ValueError("跌停股池只能获取最近 30 个交易日的数据")
    url = "https://push2ex.eastmoney.com/getTopicDTPool"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "10000",
        "sort": "fund:asc",
        "date": date,
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        if len(data_json["data"]["pool"]) == 0:
            return None
        temp_df = pd.DataFrame(data_json["data"]["pool"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.columns = [
            "序号", "代码", "_", "名称", "最新价", "涨跌幅", "成交额", "流通市值", "总市值",
            "动态市盈率", "换手率", "封单资金", "最后封板时间", "板上成交额", "连续跌停", "开板次数", "所属行业",
        ]
        temp_df = temp_df[["序号", "代码", "名称", "涨跌幅", "最新价", "成交额", "流通市值",
                            "总市值", "动态市盈率", "换手率", "封单资金", "最后封板时间",
                            "板上成交额", "连续跌停", "开板次数", "所属行业"]]
        temp_df["最新价"] = temp_df["最新价"] / 1000
        temp_df["最后封板时间"] = temp_df["最后封板时间"].astype(str).str.zfill(6)
        temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
        temp_df["流通市值"] = pd.to_numeric(temp_df["流通市值"], errors="coerce")
        temp_df["总市值"] = pd.to_numeric(temp_df["总市值"], errors="coerce")
        temp_df["动态市盈率"] = pd.to_numeric(temp_df["动态市盈率"], errors="coerce")
        temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
        temp_df["封单资金"] = pd.to_numeric(temp_df["封单资金"], errors="coerce")
        temp_df["板上成交额"] = pd.to_numeric(temp_df["板上成交额"], errors="coerce")
        temp_df["连续跌停"] = pd.to_numeric(temp_df["连续跌停"], errors="coerce")
        temp_df["开板次数"] = pd.to_numeric(temp_df["开板次数"], errors="coerce")
        return standardize_output(temp_df, "代码", "名称", "fetch_zt_pool_dtgc", "跌停股池", ["涨停板分析"])
    except Exception:
        return None


def fetch_zt_pool_sub_new(symbol: str | None = None, date: str = "20241231") -> dict | None:
    """次新股池"""
    url = "https://push2ex.eastmoney.com/getTopicCXPooll"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "5000",
        "sort": "ods:asc",
        "date": date,
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        if len(data_json["data"]["pool"]) == 0:
            return None
        temp_df = pd.DataFrame(data_json["data"]["pool"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.columns = [
            "序号", "代码", "_", "名称", "最新价", "涨停价", "_", "涨跌幅", "成交额",
            "流通市值", "总市值", "转手率", "开板几日", "开板日期", "上市日期", "_",
            "是否新高", "涨停统计", "所属行业",
        ]
        temp_df["涨停统计"] = (
            temp_df["涨停统计"].apply(lambda x: dict(x)["days"]).astype(str)
            + "/" + temp_df["涨停统计"].apply(lambda x: dict(x)["ct"]).astype(str)
        )
        temp_df = temp_df[["序号", "代码", "名称", "涨跌幅", "最新价", "涨停价", "成交额",
                            "流通市值", "总市值", "转手率", "开板几日", "开板日期",
                            "上市日期", "是否新高", "涨停统计", "所属行业"]]
        temp_df["最新价"] = temp_df["最新价"] / 1000
        temp_df["涨停价"] = temp_df["涨停价"] / 1000
        temp_df.loc[temp_df["涨停价"] > 100000, "涨停价"] = pd.NA
        temp_df["开板日期"] = pd.to_datetime(temp_df["开板日期"], format="%Y%m%d").dt.date
        temp_df["上市日期"] = pd.to_datetime(temp_df["上市日期"], format="%Y%m%d").dt.date
        temp_df.loc[temp_df["上市日期"] == 0, "上市日期"] = pd.NaT
        temp_df["是否新高"] = temp_df["是否新高"].apply(lambda x: "是" if x == 1 else "否")
        return standardize_output(temp_df, "代码", "名称", "fetch_zt_pool_sub_new", "次新股池", ["涨停板分析"])
    except Exception:
        return None


def fetch_zt_pool_previous(symbol: str | None = None, date: str = "20240415") -> dict | None:
    """昨日涨停表现"""
    url = "https://push2ex.eastmoney.com/getYesterdayZTPool"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "5000",
        "sort": "zs:desc",
        "date": date,
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        if data_json["data"] is None:
            return None
        if len(data_json["data"]["pool"]) == 0:
            return None
        temp_df = pd.DataFrame(data_json["data"]["pool"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.columns = [
            "序号", "代码", "_", "名称", "最新价", "涨停价", "涨跌幅", "成交额",
            "流通市值", "总市值", "换手率", "振幅", "涨速", "昨日封板时间", "昨日连板数", "所属行业", "涨停统计",
        ]
        temp_df["涨停统计"] = (
            temp_df["涨停统计"].apply(lambda x: dict(x)["days"]).astype(str)
            + "/" + temp_df["涨停统计"].apply(lambda x: dict(x)["ct"]).astype(str)
        )
        temp_df = temp_df[["序号", "代码", "名称", "涨跌幅", "最新价", "涨停价", "成交额",
                            "流通市值", "总市值", "换手率", "涨速", "振幅", "昨日封板时间",
                            "昨日连板数", "涨停统计", "所属行业"]]
        temp_df["最新价"] = temp_df["最新价"] / 1000
        temp_df["涨停价"] = temp_df["涨停价"] / 1000
        temp_df["昨日封板时间"] = temp_df["昨日封板时间"].astype(str).str.zfill(6)
        return standardize_output(temp_df, "代码", "名称", "fetch_zt_pool_previous", "昨日涨停表现", ["涨停板分析"])
    except Exception:
        return None


def fetch_zt_pool_zbgc(symbol: str | None = None, date: str = "20241011") -> dict | None:
    """炸板股池"""
    thirty_days_ago = datetime.now() - pd.Timedelta(days=30)
    thirty_days_ago_str = thirty_days_ago.strftime("%Y%m%d")
    if int(date) < int(thirty_days_ago_str):
        raise ValueError("炸板股池只能获取最近 30 个交易日的数据")
    url = "https://push2ex.eastmoney.com/getTopicZBPool"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "5000",
        "sort": "fbt:asc",
        "date": date,
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        if data_json["data"] is None:
            return None
        if len(data_json["data"]["pool"]) == 0:
            return None
        temp_df = pd.DataFrame(data_json["data"]["pool"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.columns = [
            "序号", "代码", "_", "名称", "最新价", "涨停价", "涨跌幅", "成交额",
            "流通市值", "总市值", "换手率", "首次封板时间", "炸板次数", "振幅", "涨速", "涨停统计", "所属行业",
        ]
        temp_df["涨停统计"] = (
            temp_df["涨停统计"].apply(lambda x: dict(x)["days"]).astype(str)
            + "/" + temp_df["涨停统计"].apply(lambda x: dict(x)["ct"]).astype(str)
        )
        temp_df = temp_df[["序号", "代码", "名称", "涨跌幅", "最新价", "涨停价", "成交额",
                            "流通市值", "总市值", "换手率", "涨速", "首次封板时间",
                            "炸板次数", "涨停统计", "振幅", "所属行业"]]
        temp_df["最新价"] = temp_df["最新价"] / 1000
        temp_df["涨停价"] = temp_df["涨停价"] / 1000
        temp_df["首次封板时间"] = temp_df["首次封板时间"].astype(str).str.zfill(6)
        return standardize_output(temp_df, "代码", "名称", "fetch_zt_pool_zbgc", "炸板股池", ["涨停板分析"])
    except Exception:
        return None


# ======== 东方财富异动监控 (2 个) ========

def fetch_board_change(symbol: str | None = None, date: str | None = None) -> dict | None:
    """板块异动排名"""
    url = "https://push2ex.eastmoney.com/getAllBKChanges"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wzchanges",
        "pageindex": "0",
        "pagesize": "5000",
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        data_df = pd.DataFrame(data_json["data"]["allbk"])
        data_df.columns = [
            "-", "-", "板块名称", "涨跌幅", "主力净流入", "板块异动总次数", "ms", "板块具体异动类型列表及出现次数",
        ]
        data_df["板块异动最频繁个股及所属类型-买卖方向"] = [item["m"] for item in data_df["ms"]]
        data_df["板块异动最频繁个股及所属类型-股票代码"] = [item["c"] for item in data_df["ms"]]
        data_df["板块异动最频繁个股及所属类型-股票名称"] = [item["n"] for item in data_df["ms"]]
        data_df["板块异动最频繁个股及所属类型-买卖方向"] = data_df["板块异动最频繁个股及所属类型-买卖方向"].map({0: "大笔买入", 1: "大笔卖出"})
        data_df = data_df[["板块名称", "涨跌幅", "主力净流入", "板块异动总次数",
                            "板块异动最频繁个股及所属类型-股票代码",
                            "板块异动最频繁个股及所属类型-股票名称",
                            "板块异动最频繁个股及所属类型-买卖方向",
                            "板块具体异动类型列表及出现次数"]]
        data_df["涨跌幅"] = pd.to_numeric(data_df["涨跌幅"], errors="coerce")
        data_df["主力净流入"] = pd.to_numeric(data_df["主力净流入"], errors="coerce")
        data_df["板块异动总次数"] = pd.to_numeric(data_df["板块异动总次数"], errors="coerce")
        return standardize_output(data_df, "板块异动最频繁个股及所属类型-股票代码",
                                  "板块异动最频繁个股及所属类型-股票名称",
                                  "fetch_board_change", "板块异动", ["异动监控"])
    except Exception:
        return None


def fetch_changes(symbol: str = "大笔买入", date: str | None = None) -> dict | None:
    """个股盘口异动"""
    symbol_map = {
        "火箭发射": "8201", "快速反弹": "8202", "大笔买入": "8193", "封涨停板": "4",
        "打开跌停板": "32", "有大买盘": "64", "竞价上涨": "8207", "高开5日线": "8209",
        "向上缺口": "8211", "60日新高": "8213", "60日大幅上涨": "8215", "加速下跌": "8204",
        "高台跳水": "8203", "大笔卖出": "8194", "封跌停板": "8", "打开涨停板": "16",
        "有大卖盘": "128", "竞价下跌": "8208", "低开5日线": "8210", "向下缺口": "8212",
        "60日新低": "8214", "60日大幅下跌": "8216",
    }
    reversed_symbol_map = {v: k for k, v in symbol_map.items()}
    params = {
        "type": symbol_map[symbol],
        "pageindex": "0",
        "pagesize": "5000",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wzchanges",
    }
    try:
        r = requests.get("https://push2ex.eastmoney.com/getAllStockChanges", params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["allstock"])
        temp_df["tm"] = pd.to_datetime(temp_df["tm"], format="%H%M%S").dt.time
        temp_df.columns = ["时间", "代码", "_", "名称", "板块", "相关信息"]
        temp_df = temp_df[["时间", "代码", "名称", "板块", "相关信息"]]
        temp_df["板块"] = temp_df["板块"].astype(str)
        temp_df["板块"] = temp_df["板块"].map(reversed_symbol_map)
        return standardize_output(temp_df, "代码", "名称", "fetch_changes", "个股异动", ["异动监控"])
    except Exception:
        return None
```

- [ ] **步骤 2：验证所有 20 个 fetcher 函数存在**

```bash
cd akshare-tech-selection/scripts && python -c "
import fetcher
all_names = fetcher.__all__
print(f'Total: {len(all_names)}')
for n in all_names:
    fn = getattr(fetcher, n, None)
    status = 'OK' if callable(fn) else 'MISSING'
    print(f'  {n}: {status}')"
```

预期：`Total: 20`，所有显示 OK

- [ ] **步骤 3：提交**

```bash
cd akshare-tech-selection && git add scripts/fetcher.py && git commit -m "feat: add cninfo + 8 eastmoney fetcher implementations

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 5：test_fetcher.py — 新增反爬检测测试

**文件：**
- 修改：`akshare-tech-selection/scripts/tests/test_fetcher.py`

- [ ] **步骤 1：在现有 test_fetcher.py 末尾追加反爬检测测试**

```python
class TestAntiCrawlCheck:
    """测试 _check_thx_blocked 反爬检测"""

    def test_http_403_triggers_exit(self, monkeypatch):
        """HTTP 403 应触发 os._exit(1)"""
        import fetcher as ft
        import requests as rq

        class MockResponse:
            status_code = 403
            text = ""

        monkeypatch.setattr("os._exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
        with pytest.raises(SystemExit) as excinfo:
            ft._check_thx_blocked(MockResponse(), "test_api")
        assert excinfo.value.code == 1

    def test_captcha_page_triggers_exit(self, monkeypatch):
        """验证页面应触发 os._exit(1)"""
        import fetcher as ft

        class MockResponse:
            status_code = 200
            text = "请在下方输入验证码"

        monkeypatch.setattr("os._exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
        with pytest.raises(SystemExit) as excinfo:
            ft._check_thx_blocked(MockResponse(), "test_api")
        assert excinfo.value.code == 1

    def test_short_response_triggers_exit(self, monkeypatch):
        """短响应（<200字符）应被视为异常页面"""
        import fetcher as ft

        class MockResponse:
            status_code = 200
            text = "short"

        monkeypatch.setattr("os._exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
        with pytest.raises(SystemExit) as excinfo:
            ft._check_thx_blocked(MockResponse(), "test_api")
        assert excinfo.value.code == 1

    def test_normal_response_passes_through(self):
        """正常 HTML 页面不应触发 exit"""
        import fetcher as ft

        class MockResponse:
            status_code = 200
            text = "<html><body>" + "x" * 200 + "</body></html>"

        # 不应该抛出异常
        ft._check_thx_blocked(MockResponse(), "test_api")
```

- [ ] **步骤 2：运行反爬测试验证通过**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_fetcher.py::TestAntiCrawlCheck -v 2>&1
```

预期：PASS

- [ ] **步骤 3：运行全部 fetcher 测试**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_fetcher.py -v 2>&1
```

预期：全部 PASS

- [ ] **步骤 4：提交**

```bash
cd akshare-tech-selection && git add scripts/tests/test_fetcher.py && git commit -m "test: add anti-crawl detection tests for _check_thx_blocked

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 6：engine.py — 并发改顺序，集成 RateLimiter

**文件：**
- 修改：`akshare-tech-selection/scripts/engine.py`

- [ ] **步骤 1：修改 engine.py**

对 engine.py 做以下改动：

1. 删除 `from concurrent.futures import ThreadPoolExecutor, as_completed`
2. 新增 `from ratelimit import _RATE_LIMITER`
3. 删除 `_call_fetchers_concurrent` 函数
4. 新增 `_call_fetchers_sequential` 函数
5. 所有入口函数签名去掉 `max_workers`
6. 所有内部调用 `_call_fetchers_concurrent` → `_call_fetchers_sequential`
7. 删除 `_call_fetcher` 函数末尾的 `import time, random` 不再需要（保留 `_now_str` 中的 `datetime`）

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
技术指标选股 — 引擎层
实现 4 种工作模式：single / intersect / scan / full
"""
import time
import random
from datetime import date, datetime

import fetcher
from ratelimit import _RATE_LIMITER


# ---- 工具 ----

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _call_fetcher(ind_name: str, symbol: str | None = None, date: str | None = None):
    """调用单个 fetcher，返回 (ind_name, result_dict_or_None, error_dict_or_None)"""
    fn = getattr(fetcher, ind_name, None)
    if fn is None:
        return ind_name, None, {"indicator": ind_name, "error": f"Unknown indicator: {ind_name}", "api": ind_name}
    try:
        result = fn(symbol=symbol, date=date)
        if result is None:
            return ind_name, None, {"indicator": ind_name, "error": "API returned null/empty data", "api": ind_name}
        return ind_name, result, None
    except Exception as e:
        return ind_name, None, {"indicator": ind_name, "error": str(e), "api": ind_name}


def _call_fetchers_sequential(
    ind_names: list[str],
    symbols: dict[str, str] | None = None,
    date: str | None = None,
):
    """顺序调用多个 fetcher（受全局 RateLimiter 管控），返回 (results_dict, errors_list)"""
    if symbols is None:
        symbols = {}
    results = {}
    errors = []

    for ind_name in ind_names:
        _RATE_LIMITER.acquire()
        sym = symbols.get(ind_name)
        ind_name, result, error = _call_fetcher(ind_name, sym, date)
        if error:
            errors.append(error)
        if result:
            results[ind_name] = result

    return results, errors


# ---- 模式 1: single ----

def run_single(
    indicator: str,
    symbol: str | None = None,
    date: str | None = None,
    _fetcher_callable=None,
) -> dict:
    """单指标查询"""
    params = {}
    if symbol:
        params["symbol"] = symbol
    if date:
        params["date"] = date

    if _fetcher_callable:
        result = _fetcher_callable(symbol=symbol, date=date)
        errors = []
        if result is None:
            errors.append({"indicator": indicator, "error": "API returned null/empty data", "api": indicator})
            data = []
            count = 0
        else:
            data = result.get("data", [])
            count = result.get("count", len(data))
            errors = []
    else:
        _RATE_LIMITER.acquire()
        ind_name, result, error = _call_fetcher(indicator, symbol=symbol, date=date)
        errors = [error] if error else []
        if result:
            data = result.get("data", [])
            count = result.get("count", len(data))
        else:
            data = []
            count = 0

    return {
        "mode": "single",
        "indicator": indicator,
        "params": params,
        "fetch_time": _now_str(),
        "count": count,
        "data": data,
        "errors": errors,
    }


# ---- 模式 2: intersect ----

def run_intersect(
    indicators: list[str],
    symbol: str | None = None,
    date: str | None = None,
) -> dict:
    """多指标交集查询"""
    results, errors = _call_fetchers_sequential(indicators, date=date)

    indicator_counts = {}
    for ind_name in indicators:
        if ind_name in results:
            indicator_counts[ind_name] = results[ind_name].get("count", len(results[ind_name].get("data", [])))
        else:
            indicator_counts[ind_name] = 0

    if len(results) == 0:
        return {
            "mode": "intersect",
            "indicators": indicators,
            "params": {"date": date} if date else {},
            "fetch_time": _now_str(),
            "intersect_count": 0,
            "indicator_counts": indicator_counts,
            "succeeded_indicators": 0,
            "failed_indicators": len(indicators),
            "data": [],
            "errors": errors,
        }

    # Build stock_code index for each indicator
    code_to_indicators = {}
    code_to_details = {}
    for ind_name, result in results.items():
        for item in result.get("data", []):
            code = item.get("stock_code", "")
            if code not in code_to_indicators:
                code_to_indicators[code] = set()
                code_to_details[code] = {}
            code_to_indicators[code].add(ind_name)
            code_to_details[code][ind_name] = {k: v for k, v in item.items() if k not in ("stock_code", "stock_name")}

    required_count = len(indicators)
    intersect_data = []
    for code, matched in code_to_indicators.items():
        if len(matched) == required_count:
            stock_name = ""
            for mat_ind in matched:
                for item in results[mat_ind].get("data", []):
                    if item.get("stock_code") == code and item.get("stock_name"):
                        stock_name = item["stock_name"]
                        break
                if stock_name:
                    break
            intersect_data.append({
                "stock_code": code,
                "stock_name": stock_name,
                "matched_indicators": sorted(matched),
                "indicator_details": code_to_details[code],
            })

    return {
        "mode": "intersect",
        "indicators": indicators,
        "params": {"date": date} if date else {},
        "fetch_time": _now_str(),
        "intersect_count": len(intersect_data),
        "indicator_counts": indicator_counts,
        "succeeded_indicators": len(results),
        "failed_indicators": len(indicators) - len(results),
        "data": intersect_data,
        "errors": errors,
    }


# ---- 模式 3: scan ----

def run_scan(
    symbol: str | None = None,
    date: str | None = None,
    signal_threshold: int = 1,
    top_n: int | None = None,
) -> dict:
    """全量扫描: 遍历 ALL_INDICATORS，按 stock_code 聚合信号"""
    ind_names = [ind["name"] for ind in fetcher.ALL_INDICATORS]
    results, errors = _call_fetchers_sequential(ind_names, date=date)

    ind_meta = {ind["name"]: ind for ind in fetcher.ALL_INDICATORS}

    code_to_signals = {}
    indicator_counts = {}
    for ind_name in ind_names:
        result = results.get(ind_name)
        if result is None:
            indicator_counts[ind_name] = 0
            continue
        data = result.get("data", [])
        indicator_counts[ind_name] = len(data)
        meta = ind_meta.get(ind_name, {})
        for item in data:
            code = item.get("stock_code", "")
            name = item.get("stock_name", "")
            if code not in code_to_signals:
                code_to_signals[code] = {
                    "stock_name": name,
                    "signals": [],
                }
            elif name and not code_to_signals[code]["stock_name"]:
                code_to_signals[code]["stock_name"] = name
            signal = {
                "indicator": meta.get("name", ind_name),
                "category": meta.get("category", ""),
                "categories": meta.get("categories", []),
            }
            detail = {k: v for k, v in item.items() if k not in ("stock_code", "stock_name")}
            if detail:
                signal["detail"] = detail
            code_to_signals[code]["signals"].append(signal)

    agg_data = []
    for code, info in code_to_signals.items():
        signal_count = len(info["signals"])
        if signal_count >= signal_threshold:
            agg_data.append({
                "stock_code": code,
                "stock_name": info["stock_name"],
                "signal_count": signal_count,
                "signals": info["signals"],
            })

    agg_data.sort(key=lambda x: x["signal_count"], reverse=True)

    if top_n is not None:
        agg_data = agg_data[:top_n]

    signal_stats = {}
    for code, info in code_to_signals.items():
        for sig in info["signals"]:
            ind = sig["indicator"]
            if ind not in signal_stats:
                signal_stats[ind] = {
                    "indicator": ind,
                    "category": sig["category"],
                    "hit_count": 0,
                }
            signal_stats[ind]["hit_count"] += 1

    top_signals = sorted(signal_stats.values(), key=lambda x: x["hit_count"], reverse=True)
    total_stocks = len(set(code_to_signals.keys()))

    return {
        "mode": "scan",
        "indicators": ind_names,
        "params": {"date": date, "signal_threshold": signal_threshold, "top_n": top_n} if any([date, signal_threshold != 1, top_n is not None]) else {},
        "fetch_time": _now_str(),
        "total_stocks_with_signals": total_stocks,
        "indicator_counts": indicator_counts,
        "succeeded_indicators": len(results),
        "failed_indicators": len(ind_names) - len(results),
        "data": agg_data,
        "signal_summary": {
            "total_stocks_with_signals": total_stocks,
            "top_signals": top_signals,
        },
        "errors": errors,
    }


# ---- 模式 4: full ----

def run_full(
    symbol: str | None = None,
    date: str | None = None,
    signal_threshold: int = 1,
    top_n: int | None = None,
) -> dict:
    """全量扫描(详细版): 与 scan 类似，但 signal_summary 包含每个指标的详细健康状况"""
    ind_names = [ind["name"] for ind in fetcher.ALL_INDICATORS]
    results, errors = _call_fetchers_sequential(ind_names, date=date)

    ind_meta = {ind["name"]: ind for ind in fetcher.ALL_INDICATORS}

    code_to_signals = {}
    indicator_counts = {}
    for ind_name in ind_names:
        result = results.get(ind_name)
        if result is None:
            indicator_counts[ind_name] = 0
            continue
        data = result.get("data", [])
        indicator_counts[ind_name] = len(data)
        meta = ind_meta.get(ind_name, {})
        for item in data:
            code = item.get("stock_code", "")
            name = item.get("stock_name", "")
            if code not in code_to_signals:
                code_to_signals[code] = {
                    "stock_name": name,
                    "signals": [],
                }
            elif name and not code_to_signals[code]["stock_name"]:
                code_to_signals[code]["stock_name"] = name
            signal = {
                "indicator": meta.get("name", ind_name),
                "category": meta.get("category", ""),
                "categories": meta.get("categories", []),
            }
            detail = {k: v for k, v in item.items() if k not in ("stock_code", "stock_name")}
            if detail:
                signal["detail"] = detail
            code_to_signals[code]["signals"].append(signal)

    agg_data = []
    for code, info in code_to_signals.items():
        signal_count = len(info["signals"])
        if signal_count >= signal_threshold:
            agg_data.append({
                "stock_code": code,
                "stock_name": info["stock_name"],
                "signal_count": signal_count,
                "signals": info["signals"],
            })

    agg_data.sort(key=lambda x: x["signal_count"], reverse=True)

    if top_n is not None:
        agg_data = agg_data[:top_n]

    total_stocks = len(set(code_to_signals.keys()))

    summary_indicators = []
    for ind_name in ind_names:
        if ind_name in results:
            result = results[ind_name]
            total_rows = result.get("count", len(result.get("data", [])))
            summary_indicators.append({
                "indicator": ind_name,
                "status": "success",
                "total_rows": total_rows,
            })
        else:
            summary_indicators.append({
                "indicator": ind_name,
                "status": "error",
                "total_rows": 0,
            })

    return {
        "mode": "full",
        "total_indicators": len(ind_names),
        "indicators": ind_names,
        "params": {"date": date, "signal_threshold": signal_threshold, "top_n": top_n} if any([date, signal_threshold != 1, top_n is not None]) else {},
        "fetch_time": _now_str(),
        "total_stocks_with_signals": total_stocks,
        "indicator_counts": indicator_counts,
        "succeeded_indicators": len(results),
        "failed_indicators": len(ind_names) - len(results),
        "data": agg_data,
        "signal_summary": {
            "indicators": summary_indicators,
            "total_stocks_with_signals": total_stocks,
        },
        "errors": errors,
    }
```

- [ ] **步骤 2：验证 engine.py 可导入**

```bash
cd akshare-tech-selection/scripts && python -c "import engine; print('OK')"
```

预期：`OK`

- [ ] **步骤 3：提交**

```bash
cd akshare-tech-selection && git add scripts/engine.py && git commit -m "refactor: replace ThreadPoolExecutor with sequential calls + RateLimiter integration

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 7：test_engine.py — 适配新的 engine 接口

**文件：**
- 修改：`akshare-tech-selection/scripts/tests/test_engine.py`

- [ ] **步骤 1：删除 `test_parse_workers_default` 测试**

从 `TestCLIParsing` 中删除该方法。

- [ ] **步骤 2：更新所有传入 `max_workers=` 的测试**

以下行需要将 `max_workers=1` 删除：
- Line 98: `result = engine.run_intersect(["fetch_a", "fetch_b"], max_workers=1)`
- Line 121: `result = engine.run_intersect(["fetch_a", "fetch_b"], max_workers=1)`
- Line 137: `result = engine.run_intersect(["fetch_a", "fetch_b"], max_workers=1)`
- Line 151: `result = engine.run_intersect(["fetch_a"], max_workers=1)`
- Line 195: `result = engine.run_scan(max_workers=1)`
- Line 233: `result = engine.run_scan(max_workers=1, signal_threshold=2)`
- Line 256: `result = engine.run_scan(max_workers=1, top_n=3)`
- Line 286: `result = engine.run_scan(max_workers=1)`
- Line 388: `result = engine.run_full(max_workers=1)`

改为去掉 `max_workers=1`。

- [ ] **步骤 3：运行 engine 测试验证通过**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_engine.py -v -k "not TestCLIParsing" 2>&1
```

预期：PASS

- [ ] **步骤 4：提交**

```bash
cd akshare-tech-selection && git add scripts/tests/test_engine.py && git commit -m "test: update engine tests — remove max_workers params, delete workers CLI test

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 8：CLI + SKILL.md — 移除 --workers 参数

**文件：**
- 修改：`akshare-tech-selection/scripts/tech_selection.py`
- 修改：`akshare-tech-selection/SKILL.md`

- [ ] **步骤 1：修改 tech_selection.py — 删除 --workers 参数**

删除以下内容：
- `parser.add_argument("--workers", ...)` 整个块
- `args.workers` 的所有引用（传给 engine 的调用）
- `tqdm` monkey-patch 可以保留（无害）或删除。保留更安全。

具体改动：

```python
# 删除 (约 lines 82-87):
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="并发数，默认 8",
    )

# 修改 engine.run_intersect 调用 (约 line 133):
# 旧: result = engine.run_intersect(indicators, date=args.date, max_workers=args.workers,)
# 新:
result = engine.run_intersect(indicators, date=args.date)

# 修改 engine.run_scan 调用 (约 line 140):
# 旧: result = engine.run_scan(date=args.date, signal_threshold=..., top_n=..., max_workers=args.workers,)
# 新:
result = engine.run_scan(date=args.date, signal_threshold=args.signal_threshold, top_n=args.top_n)

# 修改 engine.run_full 调用 (约 line 149):
# 旧: result = engine.run_full(date=args.date, signal_threshold=..., top_n=..., max_workers=args.workers,)
# 新:
result = engine.run_full(date=args.date, signal_threshold=args.signal_threshold, top_n=args.top_n)
```

- [ ] **步骤 2：修改 SKILL.md**

删除 `--workers` 参数说明（约 line 82-85），新增限流和反爬说明。

在 "参数说明" 最后（`--output` 之前）新增一节：

```markdown
### --signal-threshold（可选，默认 1）
...
### --top-n（可选）
...
### --output（可选）
...
```

在 "错误处理" 之前新增：

```markdown
## 速率限制

所有 API 调用受全局速率限制，每分钟最多 5 次。调用间隔随机加入 0.5-2.0 秒抖动。调用模式从并发改为顺序执行。

## 反爬虫

同花顺 API（`data.10jqka.com.cn`）具有反爬虫机制。当遇到 HTTP 403 或验证页面时，程序会输出以下提示并退出（exit code 1）：
> [BLOCKED] <api_name>: 被反爬虫系统拦截，请等待 1 小时后重试
```

- [ ] **步骤 3：验证 CLI 参数解析**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/test_engine.py::TestCLIParsing -v 2>&1
```

预期：PASS（删除 `test_parse_workers_default` 后剩余测试通过）

- [ ] **步骤 4：提交**

```bash
cd akshare-tech-selection && git add scripts/tech_selection.py SKILL.md && git commit -m "refactor: remove --workers CLI param, add rate-limit docs to SKILL.md

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 9：最终验证

- [ ] **步骤 1：运行全部单元测试**

```bash
cd akshare-tech-selection && uv run pytest scripts/tests/ -v -k "not integration" 2>&1
```

预期：全部 PASS

- [ ] **步骤 2：确认没有 ak share 残余依赖引用**

```bash
grep -r "import akshare\|from akshare" akshare-tech-selection/scripts/fetcher.py akshare-tech-selection/scripts/engine.py akshare-tech-selection/scripts/tech_selection.py 2>&1
```

预期：只有 `tech_selection.py` 中的 `from akshare import tqdm` monkey-patch 可能匹配（如果有）。fetcher.py 和 engine.py 不应该有。

- [ ] **步骤 3：检查 TODO / 占位符**

```bash
grep -r "TODO\|待定\|FIXME\|XXX" akshare-tech-selection/scripts/ratelimit.py akshare-tech-selection/scripts/fetcher.py akshare-tech-selection/scripts/engine.py akshare-tech-selection/scripts/tech_selection.py akshare-tech-selection/SKILL.md 2>&1
```

预期：无输出

- [ ] **步骤 4：最终提交**

```bash
cd akshare-tech-selection && git add -A && git commit -m "chore: finalize anti-crawl and rate-limiting implementation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 文件清单汇总

| 操作 | 文件 |
|------|------|
| 新建 | `akshare-tech-selection/scripts/ratelimit.py` |
| 新建 | `akshare-tech-selection/scripts/tests/test_ratelimit.py` |
| 重写 | `akshare-tech-selection/scripts/fetcher.py`（去除 akshare 依赖，20 个显式 fetcher，反爬检测） |
| 修改 | `akshare-tech-selection/scripts/engine.py`（并发 → 顺序，+RateLimiter，去除 max_workers） |
| 修改 | `akshare-tech-selection/scripts/tech_selection.py`（去除 --workers） |
| 修改 | `akshare-tech-selection/scripts/tests/test_fetcher.py`（新增反爬检测测试） |
| 修改 | `akshare-tech-selection/scripts/tests/test_engine.py`（去除 max_workers 参数，删除 workers 测试） |
| 修改 | `akshare-tech-selection/SKILL.md`（去除 --workers，新增限流/反爬说明） |
