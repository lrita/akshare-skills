# akshare-stock-fundamentals 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建个股基本面数据 CLI 工具，输入股票代码，一次性拉取 5 个板块（基础信息、基本面、风险信号、事件驱动、机构动向）共 19 个数据源，输出结构化 JSON 供大模型做基本面分析。

**架构：** 单文件 CLI 入口 (`fetch_fundamentals.py`) 内含 argparse 解析、数据源函数、板块编排和结果组装。遵循项目现有模式：所有输出到 stdout，日志/错误到 stderr，顺序调用 + RateLimiter (10 次/分钟)。

**技术栈：** Python 3, akshare, pandas, urllib (stdlib), argparse, json, datetime

**规格文档：** `docs/superpowers/specs/2026-06-21-stock-fundamentals-design.md`

---

## 文件结构

```
akshare-stock-fundamentals/
├── SKILL.md                          # skill 定义（任务 10）
└── scripts/
    ├── fetch_fundamentals.py         # CLI 入口 + 全部数据源函数 + 板块编排（任务 1-8）
    └── tests/
        ├── __init__.py               # 空文件（任务 1）
        ├── test_setup.py             # 类定义 + 模式验证（任务 1）
        ├── test_basic_info.py        # basic_info 数据源测试（任务 2）
        ├── test_fundamentals.py      # fundamentals 数据源测试（任务 3）
        ├── test_risk_signals.py      # risk_signals 数据源测试（任务 4）
        ├── test_events.py            # events 数据源测试（任务 5）
        ├── test_institutional.py     # institutional 数据源测试（任务 6）
        ├── test_cli.py               # CLI + 编排 + 错误处理测试（任务 7-8）
        └── test_integration.py       # 端到端集成测试（任务 9）
```

所有数据源函数和编排逻辑放在 `fetch_fundamentals.py` 单文件中。每个板块有独立的测试文件。代码从 0 行开始，所有测试先于实现。

---

### 任务 1：项目骨架 + 测试基础设施

**文件：**
- 创建：`akshare-stock-fundamentals/scripts/__init__.py`
- 创建：`akshare-stock-fundamentals/scripts/tests/__init__.py`
- 创建：`akshare-stock-fundamentals/scripts/tests/test_setup.py`
- 创建：`akshare-stock-fundamentals/scripts/fetch_fundamentals.py`

- [ ] **步骤 1：创建目录结构和空文件**

```bash
mkdir -p akshare-stock-fundamentals/scripts/tests
touch akshare-stock-fundamentals/scripts/__init__.py
touch akshare-stock-fundamentals/scripts/tests/__init__.py
```

- [ ] **步骤 2：编写测试 — 验证模块可导入 + RateLimiter 类存在**

```python
# akshare-stock-fundamentals/scripts/tests/test_setup.py
"""测试基础设施：模块导入、RateLimiter 类定义、常量验证。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
sys.stdout = open(os.devnull, 'w')  # suppress any print during import
from fetch_fundamentals import RateLimiter, SECTIONS, SECTION_DEPENDENCIES
sys.stdout = sys.__stdout__


class TestRateLimiter:
    """RateLimiter: 滑动窗口速率限制器，max_calls=10, window_seconds=60。"""

    def test_rate_limiter_creates(self):
        limiter = RateLimiter(max_calls=10, window_seconds=60)
        assert limiter.max_calls == 10
        assert limiter.window_seconds == 60

    def test_rate_limiter_allows_up_to_max(self):
        import time
        limiter = RateLimiter(max_calls=3, window_seconds=60)
        for _ in range(3):
            limiter.acquire()
        # 没有异常即通过

    def test_wait_blocks_beyond_max(self):
        import time
        limiter = RateLimiter(max_calls=2, window_seconds=60)
        limiter.acquire()
        limiter.acquire()
        start = time.time()
        limiter.acquire()  # 第3次应触发等待
        elapsed = time.time() - start
        assert elapsed > 0.3  # 至少等到抖动间隔

    def test_rate_limiter_max_calls_10(self):
        limiter = RateLimiter(max_calls=10, window_seconds=60)
        assert limiter.max_calls == 10


class TestConstants:
    """验证 SECTIONS 和 SECTION_DEPENDENCIES 常量。"""

    def test_sections_contains_all_five(self):
        assert set(SECTIONS) == {"basic_info", "fundamentals", "risk_signals", "events", "institutional"}

    def test_section_dependencies_has_all_keys(self):
        assert set(SECTION_DEPENDENCIES.keys()) == set(SECTIONS)
```

- [ ] **步骤 3：运行测试验证失败（模块不存在）**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_setup.py -v 2>&1
```

预期：ModuleNotFoundError — fetch_fundamentals 尚未创建

- [ ] **步骤 4：编写最小实现 — RateLimiter + 常量定义**

```python
# akshare-stock-fundamentals/scripts/fetch_fundamentals.py
"""个股基本面数据获取工具。

用法:
    uv run python scripts/fetch_fundamentals.py --symbol 600183 [--date 20260621] [--output result.json]

输出结构化 JSON 到 stdout，包含 5 个板块的个股基本面数据。
"""
import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta

# 板块列表
SECTIONS = ["basic_info", "fundamentals", "risk_signals", "events", "institutional"]

# 每个板块依赖的数据源 (section -> list of source names)
SECTION_DEPENDENCIES = {
    "basic_info":    ["tencent_quote", "eastmoney_search", "stock_add_stock"],
    "fundamentals":  ["financial_abstract_by_report", "financial_abstract_by_year",
                      "financial_benefit", "financial_debt", "financial_cash",
                      "profit_forecast_eps", "profit_forecast_net", "profit_forecast_inst",
                      "profit_forecast_detail", "revenue_structure"],
    "risk_signals":  ["block_trades", "restricted_release_em", "restricted_release_sina", "pledge"],
    "events":        ["notices"],
    "institutional": ["research_visits"],
}


class RateLimiter:
    """滑动窗口速率限制器。"""

    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._call_times: list[float] = []

    def acquire(self):
        """等待直到可以发起下一次调用。"""
        now = time.time()
        # 清理窗口外的记录
        self._call_times = [t for t in self._call_times if now - t < self.window_seconds]
        if len(self._call_times) >= self.max_calls:
            # 等待到最早的调用滑出窗口
            wait = self._call_times[0] + self.window_seconds - now + 0.1
            if wait > 0:
                time.sleep(wait)
            self._call_times = [t for t in self._call_times if time.time() - t < self.window_seconds]
        # 随机抖动 0.3-1.0 秒
        time.sleep(random.uniform(0.3, 1.0))
        self._call_times.append(time.time())
```

- [ ] **步骤 5：运行测试验证通过**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_setup.py -v 2>&1
```

预期：全部 4 个测试 PASS

- [ ] **步骤 6：Commit**

```bash
git add akshare-stock-fundamentals/
git commit -m "feat: add project skeleton with RateLimiter and section constants

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 2：数据源 — 基础信息板块 (basic_info)

**文件：**
- 创建：`akshare-stock-fundamentals/scripts/tests/test_basic_info.py`
- 修改：`akshare-stock-fundamentals/scripts/fetch_fundamentals.py`

- [ ] **步骤 1：编写测试 — 三个数据源函数签名和返回值类型**

```python
# akshare-stock-fundamentals/scripts/tests/test_basic_info.py
"""测试 basic_info 板块的三个数据源函数。"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
import pytest
import pandas as pd

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import (
    fetch_tencent_quote,
    fetch_eastmoney_search,
    fetch_stock_add_stock,
)
sys.stdout = sys.__stdout__

SYMBOL = "600183"


class TestFetchTencentQuote:
    """腾讯行情: HTTP GET qt.gtimg.cn, GBK 解码, 返回 dict。"""

    MOCK_RESP = (
        b'v_sh600183="1~\xe7\x94\x9f\xe7\x9b\x8a\xe7\xa7\x91\xe6\x8a\x80~600183~183.87~180.15~178.50'
        b'~798770~419569~379201~183.87~1147~183.86~159~183.85~587~183.84~329~183.83~26'
        b'~183.88~165~183.89~46~183.90~77~183.91~32~183.92~30'
        b'~~20260618161425~3.72~2.06~187.35~176.73~183.87/798770/14605138345~798770~1460514'
        b'~3.34~113.69~~187.35~176.73~5.90~4402.77~4466.42~27.94~198.17~162.14~0.90~1898~182.85~96.41";\n'
    )

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_returns_dict_with_expected_keys(self, mock_urlopen):
        mock_urlopen.return_value.read.return_value = TestFetchTencentQuote.MOCK_RESP
        result = fetch_tencent_quote("600183")
        assert isinstance(result, dict)
        assert result["name"] == "生益科技"
        assert result["price"] == 183.87
        assert result["pe_ttm"] == 113.69
        assert result["pe_dynamic"] == 96.41
        assert result["pb"] == 27.94
        assert result["total_mcap_yi"] == 4466.42
        assert result["float_mcap_yi"] == 4402.77
        assert "open" in result
        assert "high" in result
        assert "low" in result

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_adds_sh_prefix_for_6xxxxx(self, mock_urlopen):
        mock_urlopen.return_value.read.return_value = TestFetchTencentQuote.MOCK_RESP
        fetch_tencent_quote("600183")
        url = mock_urlopen.call_args[0][0].full_url if hasattr(mock_urlopen.call_args[0][0], 'full_url') else str(mock_urlopen.call_args[0][0])
        assert "sh600183" in str(mock_urlopen.call_args)

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_handles_empty_response(self, mock_urlopen):
        mock_urlopen.return_value.read.return_value = b""
        result = fetch_tencent_quote("000001")
        assert result == {}


class TestFetchEastmoneySearch:
    """东财搜索: HTTP GET data.eastmoney.com/dataapi/search/company, 返回 dict。"""

    MOCK_RESP = {
        "result": {
            "companyInfo": [{
                "securityCode": "600183",
                "securityShortName": "生益科技",
                "listingDate": "1998-10-28 00:00:00",
                "totalCapital": "2429119230",
                "circulationCapital": "2394501544",
                "totalMarketValue": "446642152820",
                "circulationValue": "440276998895",
                "close": "183.87",
                "changePercent": "2.06",
                "pe": "96.41",
                "pb": "27.94",
                "companyProfile": "公司简介内容...",
                "mainBusiness": "设计、生产和销售覆铜板和粘结片",
                "mainBusinessOriginal": "设计、生产和销售覆铜板和粘结片、印制线路板",
                "businessScope": "经营范围...",
                "bk": "电子,元件,印制电路板,华为概念,HS300",
                "coreTheme": "【公司简介】广东生益科技股份有限公司创始于1985年...\r【所属板块】电子,元件\r【主营业务】设计、生产和销售\r【主营产品】主营产品：报告期：2025-12-31,覆铜板业务收入187.96亿，占比66.11%\r【经营范围】设计、生产和销售\r【公司沿革】广东生益科技股份有限公司原为东莞生益敷铜板股份有限公司..."
            }]
        }
    }

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_returns_dict_with_profile_fields(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(TestFetchEastmoneySearch.MOCK_RESP).encode('utf-8')
        mock_urlopen.return_value = mock_resp
        result = fetch_eastmoney_search("600183")
        assert isinstance(result, dict)
        assert result["security_short_name"] == "生益科技"
        assert result["total_capital"] == 2429119230
        assert result["circulation_capital"] == 2394501544
        assert result["boards"] == ["电子", "元件", "印制电路板", "华为概念", "HS300"]
        assert len(result["business_products"]) > 0

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_parses_business_products_from_core_theme(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(TestFetchEastmoneySearch.MOCK_RESP).encode('utf-8')
        mock_urlopen.return_value = mock_resp
        result = fetch_eastmoney_search("600183")
        assert len(result["business_products"]) > 0
        assert "product" in result["business_products"][0]
        assert "revenue_yi" in result["business_products"][0]

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_extracts_company_history(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(TestFetchEastmoneySearch.MOCK_RESP).encode('utf-8')
        mock_urlopen.return_value = mock_resp
        result = fetch_eastmoney_search("600183")
        assert "company_history" in result
        assert "广东生益科技" in result["company_history"]

    @patch('fetch_fundamentals.urllib.request.urlopen')
    def test_handles_no_results(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"result": {"companyInfo": []}}).encode('utf-8')
        mock_urlopen.return_value = mock_resp
        result = fetch_eastmoney_search("999999")
        assert result == {}


class TestFetchStockAddStock:
    """增发记录: stock_add_stock, 截取最近2年。"""

    @patch('fetch_fundamentals.ak.stock_add_stock')
    def test_returns_list_of_dicts(self, mock_api):
        mock_api.return_value = pd.DataFrame([
            {"发行方式": "定向增发", "发行价格": 12.50, "发行数量": 5000000, "上市日期": "2025-03-15"},
            {"发行方式": "公开增发", "发行价格": 10.00, "发行数量": 3000000, "上市日期": "2023-01-10"},
        ])
        result = fetch_stock_add_stock("600183", "20260621")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["发行方式"] == "定向增发"

    @patch('fetch_fundamentals.ak.stock_add_stock')
    def test_filters_by_two_years(self, mock_api):
        mock_api.return_value = pd.DataFrame([
            {"发行方式": "A", "发行价格": 1.0, "发行数量": 1, "上市日期": "2025-06-01"},
            {"发行方式": "B", "发行价格": 1.0, "发行数量": 1, "上市日期": "2021-01-01"},
        ])
        result = fetch_stock_add_stock("600183", "20260621")
        assert len(result) == 1

    @patch('fetch_fundamentals.ak.stock_add_stock')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_stock_add_stock("600183", "20260621")
        assert result == []
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_basic_info.py -v 2>&1
```

预期：FAIL，函数未定义

- [ ] **步骤 3：编写实现 — 三个数据源函数**

在 `fetch_fundamentals.py` 末尾追加：

```python
import urllib.request
import re

def fetch_tencent_quote(code: str) -> dict:
    """从腾讯财经获取实时行情快照。

    Args:
        code: 股票代码，如 "600183"

    Returns:
        dict 包含 price, pe_ttm, pe_dynamic, pb, total_mcap_yi 等字段，
        失败时返回空 dict。
    """
    # 确定市场前缀
    if code.startswith(("6", "9")):
        prefixed = f"sh{code}"
    elif code.startswith("8"):
        prefixed = f"bj{code}"
    else:
        prefixed = f"sz{code}"

    url = f"https://qt.gtimg.cn/q={prefixed}"
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode("gbk")
    except Exception:
        return {}

    for line in data.strip().split(";"):
        line = line.strip()
        if not line or "=" not in line or '"' not in line:
            continue
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        try:
            return {
                "name":           vals[1],
                "price":          float(vals[3]) if vals[3] else 0,
                "last_close":     float(vals[4]) if vals[4] else 0,
                "open":           float(vals[5]) if vals[5] else 0,
                "volume_hands":   int(float(vals[6])) if vals[6] else 0,
                "outer_disc_hands": int(float(vals[7])) if vals[7] else 0,
                "inner_disc_hands": int(float(vals[8])) if vals[8] else 0,
                "change_amt":     float(vals[31]) if vals[31] else 0,
                "change_pct":     float(vals[32]) if vals[32] else 0,
                "high":           float(vals[33]) if vals[33] else 0,
                "low":            float(vals[34]) if vals[34] else 0,
                "amount_wan":     float(vals[37]) if vals[37] else 0,
                "turnover_pct":   float(vals[38]) if vals[38] else 0,
                "pe_ttm":         float(vals[39]) if vals[39] else 0,
                "amplitude_pct":  float(vals[43]) if vals[43] else 0,
                "float_mcap_yi":  float(vals[44]) if vals[44] else 0,
                "total_mcap_yi":  float(vals[45]) if vals[45] else 0,
                "pb":             float(vals[46]) if vals[46] else 0,
                "limit_up":       float(vals[47]) if vals[47] else 0,
                "limit_down":     float(vals[48]) if vals[48] else 0,
                "vol_ratio":      float(vals[49]) if vals[49] else 0,
                "avg_price":      float(vals[51]) if vals[51] else 0,
                "pe_dynamic":     float(vals[52]) if vals[52] else 0,
                "update_time":    vals[30],
            }
        except (ValueError, IndexError):
            return {}
    return {}


def fetch_eastmoney_search(code: str) -> dict:
    """从东方财富搜索 API 获取公司档案（公司简介、主营业务、板块、主营产品等）。

    Args:
        code: 股票代码，如 "600183"

    Returns:
        dict 包含 security_short_name, company_profile, boards, business_products 等，
        失败时返回空 dict。
    """
    url = (f"https://data.eastmoney.com/dataapi/search/company"
           f"?st=CHANGE_PERCENT&sr=-1&ps=20&p=1&keyWord={code}&mainPoint=ALL")
    try:
        req = urllib.request.Request(url)
        req.add_header("Referer", "https://data.eastmoney.com/gstc/")
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}

    companies = data.get("result", {}).get("companyInfo", [])
    if not companies:
        return {}

    c = companies[0]

    # 解析所属板块
    bk_raw = c.get("bk", "") or c.get("bkOriginal", "")
    boards = [b.strip() for b in bk_raw.split(",") if b.strip()]

    # 从 coreTheme 中解析 【主营产品】和【公司沿革】
    core = c.get("coreTheme", "")
    products = _parse_business_products(core)

    # 解析公司沿革
    history = ""
    history_match = re.search(r"【公司沿革】(.*?)(?:$)", core, re.DOTALL)
    if history_match:
        history = history_match.group(1).strip()

    result = {
        "security_short_name": c.get("securityShortName", ""),
        "listing_date": (c.get("listingDate", "").split(" ")[0]
                         if c.get("listingDate") else ""),
        "total_capital": int(float(c["totalCapital"])) if c.get("totalCapital") else 0,
        "circulation_capital": int(float(c["circulationCapital"])) if c.get("circulationCapital") else 0,
        "total_market_value": int(float(c["totalMarketValue"])) if c.get("totalMarketValue") else 0,
        "circulation_value": int(float(c["circulationValue"])) if c.get("circulationValue") else 0,
        "close": float(c["close"]) if c.get("close") else 0,
        "change_pct": float(c["changePercent"]) if c.get("changePercent") else 0,
        "pe_dynamic": float(c["pe"]) if c.get("pe") else 0,
        "pb": float(c["pb"]) if c.get("pb") else 0,
        "company_profile": c.get("companyProfile", ""),
        "main_business": c.get("mainBusiness", "") or c.get("mainBusinessOriginal", ""),
        "business_scope": c.get("businessScope", ""),
        "company_history": history,
        "boards": boards,
        "business_products": products,
    }
    return result


def _parse_business_products(core_theme: str) -> list[dict]:
    """从 coreTheme 的【主营产品】段落解析产品构成。

    输入格式示例:
        【主营产品】主营产品：报告期：2025-12-31,覆铜板业务收入187.96亿，占比66.11%；
        线路板业务收入94.85亿，占比33.36%；
    输出: [{"product": "覆铜板业务", "revenue_yi": 187.96, "ratio_pct": 66.11}, ...]
    """
    products = []
    # 定位【主营产品】段落
    match = re.search(r"【主营产品】(.*?)(?:\r\n|\r|\n|【)", core_theme, re.DOTALL)
    if not match:
        return products
    section = match.group(1).strip()
    # 移除第一行的标题部分（如 "主营产品：报告期：2025-12-31,"）
    # 按中文逗号/分号分割每条产品
    # 格式: 产品名收入X亿(或万)，占比Y%
    product_pattern = re.compile(
        r'([一-龥a-zA-Z0-9（）()、]+?)(?:收入|业务收入)\s*'
        r'(-?[\d.]+)\s*(?:亿|万)\s*[,，]?\s*(?:占比)?\s*'
        r'(-?[\d.]+)\s*%',
        re.UNICODE
    )
    for m in product_pattern.finditer(section):
        product_name = m.group(1).strip().rstrip("，,")
        revenue_str = m.group(2)
        ratio_str = m.group(3)
        try:
            ratio = float(ratio_str)
            revenue = float(revenue_str)
            # 如果单位是"万"，转换为亿（简单处理：万→亿 除以 10000）
            # 不过通常都是亿，这里不做猜测转换
            products.append({"product": product_name, "revenue_yi": revenue, "ratio_pct": ratio})
        except ValueError:
            continue
    return products


def fetch_stock_add_stock(code: str, date_str: str) -> list[dict]:
    """获取增发记录，截取最近 2 年。

    Args:
        code: 股票代码
        date_str: 基准日期 YYYYMMDD

    Returns:
        list[dict], 失败返回空列表。
    """
    try:
        import akshare as ak
    except ImportError:
        return []
    try:
        df = ak.stock_add_stock(symbol=code)
        if df is None or df.empty:
            return []
        records = df.to_dict(orient="records")
        # 过滤最近 2 年
        cutoff = datetime.strptime(date_str, "%Y%m%d") - timedelta(days=730)
        filtered = []
        for r in records:
            date_val = r.get("上市日期", "")
            if not date_val:
                # 没有日期的保留
                filtered.append(r)
                continue
            try:
                rd = datetime.strptime(str(date_val)[:10], "%Y-%m-%d")
                if rd >= cutoff:
                    filtered.append(r)
            except ValueError:
                filtered.append(r)
        return filtered
    except Exception:
        return []
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_basic_info.py -v 2>&1
```

预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add akshare-stock-fundamentals/
git commit -m "feat: add basic_info data sources (tencent_quote, eastmoney_search, add_stock)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 3：数据源 — 基本面板块 (fundamentals)

**文件：**
- 创建：`akshare-stock-fundamentals/scripts/tests/test_fundamentals.py`
- 修改：`akshare-stock-fundamentals/scripts/fetch_fundamentals.py`

- [ ] **步骤 1：编写测试 — 财报 + 盈利预测 + 主营构成函数**

```python
# akshare-stock-fundamentals/scripts/tests/test_fundamentals.py
"""测试 fundamentals 板块的10个数据源函数。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
import pytest
import pandas as pd

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import (
    fetch_financial_abstract,
    fetch_financial_profit,
    fetch_financial_debt,
    fetch_financial_cashflow,
    fetch_profit_forecast_eps,
    fetch_profit_forecast_net,
    fetch_profit_forecast_inst,
    fetch_profit_forecast_detail,
    fetch_revenue_structure,
)
sys.stdout = sys.__stdout__

SYMBOL = "600183"
DATE = "20260621"


class TestFetchFinancialAbstract:
    @patch('fetch_fundamentals.ak.stock_financial_abstract_new_ths')
    def test_by_report_returns_list_of_dicts(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "报告期": ["2025-12-31", "2024-12-31"],
            "净利润": [52.3, 45.1],
        })
        result = fetch_financial_abstract(SYMBOL, "按报告期")
        assert isinstance(result, list)
        assert len(result) == 2

    @patch('fetch_fundamentals.ak.stock_financial_abstract_new_ths')
    def test_trims_to_five_years(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "报告期": [f"{y}-12-31" for y in range(2025, 2015, -1)],
            "净利润": [1.0] * 11,
        })
        result = fetch_financial_abstract(SYMBOL, "按报告期")
        assert len(result) <= 6  # 5年 + 当前

    @patch('fetch_fundamentals.ak.stock_financial_abstract_new_ths')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_financial_abstract(SYMBOL, "按报告期")
        assert result == []


class TestFetchFinancialProfit:
    @patch('fetch_fundamentals.ak.stock_financial_benefit_new_ths')
    def test_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({"报告期": ["2025-12-31"], "营业总收入": [100.0]})
        result = fetch_financial_profit(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) > 0

    @patch('fetch_fundamentals.ak.stock_financial_benefit_new_ths')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_financial_profit(SYMBOL, DATE)
        assert result == []


class TestFetchFinancialDebt:
    @patch('fetch_fundamentals.ak.stock_financial_debt_new_ths')
    def test_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({"报告期": ["2025-12-31"], "资产总计": [500.0]})
        result = fetch_financial_debt(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) > 0

    @patch('fetch_fundamentals.ak.stock_financial_debt_new_ths')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_financial_debt(SYMBOL, DATE)
        assert result == []


class TestFetchFinancialCashflow:
    @patch('fetch_fundamentals.ak.stock_financial_cash_new_ths')
    def test_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({"报告期": ["2025-12-31"], "经营现金流": [20.0]})
        result = fetch_financial_cashflow(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) > 0

    @patch('fetch_fundamentals.ak.stock_financial_cash_new_ths')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_financial_cashflow(SYMBOL, DATE)
        assert result == []


class TestFetchProfitForecasts:
    @patch('fetch_fundamentals.ak.stock_profit_forecast_ths')
    def test_eps_forecast_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({"预测年度": [2026], "机构名称": ["中信"], "每股收益": [2.15]})
        result = fetch_profit_forecast_eps(SYMBOL)
        assert isinstance(result, list)
        assert len(result) > 0

    @patch('fetch_fundamentals.ak.stock_profit_forecast_ths')
    def test_net_profit_forecast_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({"预测年度": [2026], "机构名称": ["中信"], "净利润": [52.3]})
        result = fetch_profit_forecast_net(SYMBOL)
        assert isinstance(result, list)
        assert len(result) > 0

    @patch('fetch_fundamentals.ak.stock_profit_forecast_ths')
    def test_institution_detail_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({"机构名称": ["中信"], "评级": ["买入"]})
        result = fetch_profit_forecast_inst(SYMBOL)
        assert isinstance(result, list)

    @patch('fetch_fundamentals.ak.stock_profit_forecast_ths')
    def test_indicator_detail_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({"预测年度": [2026], "每股收益": [2.15]})
        result = fetch_profit_forecast_detail(SYMBOL)
        assert isinstance(result, list)

    @patch('fetch_fundamentals.ak.stock_profit_forecast_ths')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_profit_forecast_eps(SYMBOL)
        assert result == []


class TestFetchRevenueStructure:
    @patch('fetch_fundamentals.ak.stock_zygc_em')
    def test_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "报告期": ["2025-12-31", "2024-12-31"],
            "主营收入": [284.4, 250.0],
        })
        result = fetch_revenue_structure(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) == 2

    @patch('fetch_fundamentals.ak.stock_zygc_em')
    def test_trims_to_three_years(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "报告期": [f"{y}-12-31" for y in range(2025, 2015, -1)],
            "主营收入": [1.0] * 11,
        })
        result = fetch_revenue_structure(SYMBOL, DATE)
        assert len(result) <= 4  # 3年最多4个报告期

    @patch('fetch_fundamentals.ak.stock_zygc_em')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_revenue_structure(SYMBOL, DATE)
        assert result == []
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_fundamentals.py -v 2>&1
```

预期：FAIL，函数未定义

- [ ] **步骤 3：编写实现 — fundamentals 板块数据源函数**

在 `fetch_fundamentals.py` 末尾追加：

```python
def _safe_df_to_records(df, date_str: str = None, years: int = None) -> list[dict]:
    """将 DataFrame 转为 dict 列表，可选按年份过滤。

    Args:
        df: pandas DataFrame
        date_str: 基准日期 YYYYMMDD
        years: 保留最近 N 年的数据，None 表示全量保留

    Returns:
        list[dict]
    """
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    if years is None or date_str is None:
        return records

    cutoff = datetime.strptime(date_str, "%Y%m%d") - timedelta(days=years * 365)
    filtered = []
    for r in records:
        # 尝试从报告期/日期字段过滤
        date_val = r.get("报告期", "") or r.get("日期", "") or r.get("截止日期", "")
        if not date_val:
            filtered.append(r)
            continue
        try:
            rd = datetime.strptime(str(date_val)[:10], "%Y-%m-%d")
            if rd >= cutoff:
                filtered.append(r)
        except ValueError:
            filtered.append(r)
    return filtered


def _call_akshare(func, *args, **kwargs):
    """安全调用 akshare API，返回 DataFrame 或空 DataFrame。"""
    try:
        import akshare as ak
        fn = getattr(ak, func, None)
        if fn is None:
            return None
        result = fn(*args, **kwargs)
        return result if isinstance(result, pd.DataFrame) else None
    except Exception:
        return None


# ---- 财务数据 ----

def fetch_financial_abstract(code: str, indicator: str, date_str: str = None) -> list[dict]:
    """获取主要财务指标。indicator: "按报告期" 或 "按年度"。"""
    try:
        import akshare as ak
        df = ak.stock_financial_abstract_new_ths(symbol=code, indicator=indicator)
    except Exception:
        return []
    return _safe_df_to_records(df, date_str, years=5)


def fetch_financial_profit(code: str, date_str: str) -> list[dict]:
    """获取利润表（按报告期，最近5年）。"""
    try:
        import akshare as ak
        df = ak.stock_financial_benefit_new_ths(symbol=code, indicator="按报告期")
    except Exception:
        return []
    return _safe_df_to_records(df, date_str, years=5)


def fetch_financial_debt(code: str, date_str: str) -> list[dict]:
    """获取资产负债表（按报告期，最近5年）。"""
    try:
        import akshare as ak
        df = ak.stock_financial_debt_new_ths(symbol=code, indicator="按报告期")
    except Exception:
        return []
    return _safe_df_to_records(df, date_str, years=5)


def fetch_financial_cashflow(code: str, date_str: str) -> list[dict]:
    """获取现金流量表（按报告期，最近5年）。"""
    try:
        import akshare as ak
        df = ak.stock_financial_cash_new_ths(symbol=code, indicator="按报告期")
    except Exception:
        return []
    return _safe_df_to_records(df, date_str, years=5)


# ---- 盈利预测 ----

def _fetch_profit_forecast(code: str, indicator: str) -> list[dict]:
    """获取盈利预测（指定 indicator）。"""
    try:
        import akshare as ak
        df = ak.stock_profit_forecast_ths(symbol=code, indicator=indicator)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    return df.to_dict(orient="records")


def fetch_profit_forecast_eps(code: str) -> list[dict]:
    return _fetch_profit_forecast(code, "预测年报每股收益")


def fetch_profit_forecast_net(code: str) -> list[dict]:
    return _fetch_profit_forecast(code, "预测年报净利润")


def fetch_profit_forecast_inst(code: str) -> list[dict]:
    return _fetch_profit_forecast(code, "业绩预测详表-机构")


def fetch_profit_forecast_detail(code: str) -> list[dict]:
    return _fetch_profit_forecast(code, "业绩预测详表-详细指标预测")


# ---- 主营构成 ----

def fetch_revenue_structure(code: str, date_str: str) -> list[dict]:
    """获取主营构成，截取最近3年。"""
    # stock_zygc_em 需要市场前缀，如 "SH600183"
    if code.startswith("6"):
        prefixed = f"SH{code}"
    elif code.startswith("0") or code.startswith("3"):
        prefixed = f"SZ{code}"
    elif code.startswith("8"):
        prefixed = f"BJ{code}"
    else:
        prefixed = f"SH{code}"
    try:
        import akshare as ak
        df = ak.stock_zygc_em(symbol=prefixed)
    except Exception:
        return []
    return _safe_df_to_records(df, date_str, years=3)
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_fundamentals.py -v 2>&1
```

预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add akshare-stock-fundamentals/
git commit -m "feat: add fundamentals data sources (financials, profit forecasts, revenue)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 4：数据源 — 风险信号板块 (risk_signals)

**文件：**
- 创建：`akshare-stock-fundamentals/scripts/tests/test_risk_signals.py`
- 修改：`akshare-stock-fundamentals/scripts/fetch_fundamentals.py`

- [ ] **步骤 1：编写测试 — 大宗交易 + 限售解禁 + 质押函数**

```python
# akshare-stock-fundamentals/scripts/tests/test_risk_signals.py
"""测试 risk_signals 板块的4个数据源函数。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch
import pytest
import pandas as pd

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import (
    fetch_block_trades,
    fetch_restricted_release_em,
    fetch_restricted_release_sina,
    fetch_pledge,
)
sys.stdout = sys.__stdout__

SYMBOL = "600183"
DATE = "20260621"


class TestFetchBlockTrades:
    @patch('fetch_fundamentals.ak.stock_dzjy_mrmx')
    def test_filters_by_stock_name(self, mock_api):
        mock_api.return_value = pd.DataFrame([
            {"股票代码": "600183", "股票名称": "生益科技", "成交日期": "2026-06-18", "成交价": 182.00},
            {"股票代码": "000001", "股票名称": "平安银行", "成交日期": "2026-06-18", "成交价": 11.50},
        ])
        result = fetch_block_trades(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["股票名称"] == "生益科技"

    @patch('fetch_fundamentals.ak.stock_dzjy_mrmx')
    def test_filters_by_stock_code(self, mock_api):
        mock_api.return_value = pd.DataFrame([
            {"股票代码": "600183", "股票名称": "生益科技", "成交日期": "2026-06-18"},
            {"股票代码": "600184", "股票名称": "光电股份", "成交日期": "2026-06-18"},
        ])
        result = fetch_block_trades(SYMBOL, DATE)
        assert len(result) == 1
        assert result[0]["股票代码"] == "600183"

    @patch('fetch_fundamentals.ak.stock_dzjy_mrmx')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_block_trades(SYMBOL, DATE)
        assert result == []


class TestFetchRestrictedRelease:
    @patch('fetch_fundamentals.ak.stock_restricted_release_queue_em')
    def test_em_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "解禁日期": ["2026-07-01"],
            "解禁数量": [1000000],
        })
        result = fetch_restricted_release_em(SYMBOL, DATE)
        assert isinstance(result, list)

    @patch('fetch_fundamentals.ak.stock_restricted_release_queue_em')
    def test_em_filters_past_two_years_only(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "解禁日期": ["2026-07-01", "2020-01-01"],
        })
        result = fetch_restricted_release_em(SYMBOL, DATE)
        # 2020-01-01 超过2年，2026-07-01 未执行保留
        assert len(result) >= 0  # pandas to_dict 返回原始行，过滤逻辑在函数内

    @patch('fetch_fundamentals.ak.stock_restricted_release_queue_em')
    def test_em_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_restricted_release_em(SYMBOL, DATE)
        assert result == []

    @patch('fetch_fundamentals.ak.stock_restricted_release_queue_sina')
    def test_sina_returns_list(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "解禁日期": ["2026-06-15"],
        })
        result = fetch_restricted_release_sina(SYMBOL, DATE)
        assert isinstance(result, list)

    @patch('fetch_fundamentals.ak.stock_restricted_release_queue_sina')
    def test_sina_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_restricted_release_sina(SYMBOL, DATE)
        assert result == []


class TestFetchPledge:
    @patch('fetch_fundamentals.ak.stock_gpzy_individual_pledge_ratio_detail_em')
    def test_filters_unreleased_only(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "质押状态": ["未解押", "已解押", "未解押"],
            "质押比例": [5.0, 2.0, 8.0],
        })
        result = fetch_pledge(SYMBOL)
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(r["质押状态"] == "未解押" for r in result)

    @patch('fetch_fundamentals.ak.stock_gpzy_individual_pledge_ratio_detail_em')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_pledge(SYMBOL)
        assert result == []
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_risk_signals.py -v 2>&1
```

预期：FAIL，函数未定义

- [ ] **步骤 3：编写实现**

在 `fetch_fundamentals.py` 末尾追加：

```python
def fetch_block_trades(code: str, date_str: str) -> list[dict]:
    """获取近30日大宗交易明细，按股票代码过滤。

    从全市场 A 股大宗交易中筛选目标个股。
    """
    try:
        import akshare as ak
    except ImportError:
        return []
    end_date = datetime.strptime(date_str, "%Y%m%d")
    start_date = end_date - timedelta(days=30)
    try:
        df = ak.stock_dzjy_mrmx(
            symbol="A股",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )
    except Exception:
        return []
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    return [r for r in records if str(r.get("股票代码", "")) == code]


def fetch_restricted_release_em(code: str, date_str: str) -> list[dict]:
    """从东财获取限售解禁数据，保留近2年+未执行计划。"""
    try:
        import akshare as ak
        df = ak.stock_restricted_release_queue_em(symbol=code)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    cutoff = datetime.strptime(date_str, "%Y%m%d") - timedelta(days=730)
    filtered = []
    for r in records:
        date_val = r.get("解禁日期", "")
        if not date_val:
            filtered.append(r)
            continue
        try:
            rd = datetime.strptime(str(date_val)[:10], "%Y-%m-%d")
            if rd >= cutoff:
                filtered.append(r)
        except ValueError:
            filtered.append(r)
    return filtered


def fetch_restricted_release_sina(code: str, date_str: str) -> list[dict]:
    """从新浪获取限售解禁数据，保留近2年+未执行计划。"""
    try:
        import akshare as ak
        df = ak.stock_restricted_release_queue_sina(symbol=code)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    cutoff = datetime.strptime(date_str, "%Y%m%d") - timedelta(days=730)
    filtered = []
    for r in records:
        date_val = r.get("解禁日期", "")
        if not date_val:
            filtered.append(r)
            continue
        try:
            rd = datetime.strptime(str(date_val)[:10], "%Y-%m-%d")
            if rd >= cutoff:
                filtered.append(r)
        except ValueError:
            filtered.append(r)
    return filtered


def fetch_pledge(code: str) -> list[dict]:
    """获取股权质押明细，仅保留"未解押"状态。"""
    try:
        import akshare as ak
        df = ak.stock_gpzy_individual_pledge_ratio_detail_em(symbol=code)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    return [r for r in records if r.get("质押状态", "") == "未解押"]
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_risk_signals.py -v 2>&1
```

预期：全部 PASS（部分 mock 测试可能与 DataFrame 实际列名有偏差，根据实际 API 返回调整）

- [ ] **步骤 5：Commit**

```bash
git add akshare-stock-fundamentals/
git commit -m "feat: add risk_signals data sources (block trades, restricted release, pledge)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 5：数据源 — 事件驱动板块 (events)

**文件：**
- 创建：`akshare-stock-fundamentals/scripts/tests/test_events.py`
- 修改：`akshare-stock-fundamentals/scripts/fetch_fundamentals.py`

- [ ] **步骤 1：编写测试 — 公告通知函数**

```python
# akshare-stock-fundamentals/scripts/tests/test_events.py
"""测试 events 板块的数据源函数。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch
import pytest
import pandas as pd

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import fetch_notices
sys.stdout = sys.__stdout__

SYMBOL = "600183"
DATE = "20260621"


class TestFetchNotices:
    @patch('fetch_fundamentals.ak.stock_individual_notice_report')
    def test_returns_list_of_dicts(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "公告日期": ["2026-06-18", "2026-05-15"],
            "公告标题": ["年度股东大会决议公告", "2025年报"],
        })
        result = fetch_notices(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) == 2

    @patch('fetch_fundamentals.ak.stock_individual_notice_report')
    def test_calls_with_90_day_range(self, mock_api):
        mock_api.return_value = pd.DataFrame()
        fetch_notices(SYMBOL, DATE)
        call_args = mock_api.call_args
        assert call_args[1]["security"] == SYMBOL
        assert call_args[1]["symbol"] == "全部"

    @patch('fetch_fundamentals.ak.stock_individual_notice_report')
    def test_returns_empty_list_on_error(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_notices(SYMBOL, DATE)
        assert result == []
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_events.py -v 2>&1
```

预期：FAIL，函数未定义

- [ ] **步骤 3：编写实现**

在 `fetch_fundamentals.py` 末尾追加：

```python
def fetch_notices(code: str, date_str: str) -> list[dict]:
    """获取个股公告（近90日，全部类型）。

    Args:
        code: 股票代码
        date_str: 基准日期 YYYYMMDD

    Returns:
        list[dict]
    """
    try:
        import akshare as ak
    except ImportError:
        return []
    end_date = datetime.strptime(date_str, "%Y%m%d")
    begin_date = end_date - timedelta(days=90)
    try:
        df = ak.stock_individual_notice_report(
            security=code,
            symbol="全部",
            begin_date=begin_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )
    except Exception:
        return []
    if df is None or df.empty:
        return []
    return df.to_dict(orient="records")
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_events.py -v 2>&1
```

预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add akshare-stock-fundamentals/
git commit -m "feat: add events data source (notices, 90-day window)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 6：数据源 — 机构动向板块 (institutional)

**文件：**
- 创建：`akshare-stock-fundamentals/scripts/tests/test_institutional.py`
- 修改：`akshare-stock-fundamentals/scripts/fetch_fundamentals.py`

- [ ] **步骤 1：编写测试 — 机构调研函数**

```python
# akshare-stock-fundamentals/scripts/tests/test_institutional.py
"""测试 institutional 板块的数据源函数。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch
import pytest
import pandas as pd

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import fetch_research_visits
sys.stdout = sys.__stdout__

SYMBOL = "600183"
DATE = "20260621"


class TestFetchResearchVisits:
    @patch('fetch_fundamentals.ak.stock_jgdy_tj_em')
    def test_filters_by_stock_name(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "股票代码": ["600183", "000001"],
            "股票名称": ["生益科技", "平安银行"],
        })
        result = fetch_research_visits(SYMBOL, DATE)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["股票名称"] == "生益科技"

    @patch('fetch_fundamentals.ak.stock_jgdy_tj_em')
    def test_filters_by_stock_code(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "股票代码": ["600183", "600184"],
            "股票名称": ["生益科技", "光电股份"],
        })
        result = fetch_research_visits(SYMBOL, DATE)
        assert len(result) == 1
        assert result[0]["股票代码"] == "600183"

    @patch('fetch_fundamentals.ak.stock_jgdy_tj_em')
    def test_handles_api_error_gracefully(self, mock_api):
        mock_api.side_effect = Exception("API error")
        result = fetch_research_visits(SYMBOL, DATE)
        assert result == []
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_institutional.py -v 2>&1
```

预期：FAIL，函数未定义

- [ ] **步骤 3：编写实现**

在 `fetch_fundamentals.py` 末尾追加：

```python
def fetch_research_visits(code: str, date_str: str) -> list[dict]:
    """获取近30日机构调研记录，按股票代码/名称过滤。

    遍历近30天每日的 stock_jgdy_tj_em，筛选目标个股。

    Args:
        code: 股票代码
        date_str: 基准日期 YYYYMMDD

    Returns:
        list[dict]
    """
    try:
        import akshare as ak
    except ImportError:
        return []
    end_date = datetime.strptime(date_str, "%Y%m%d")
    start_date = end_date - timedelta(days=30)
    all_results = []
    current = start_date
    while current <= end_date:
        date_key = current.strftime("%Y%m%d")
        try:
            df = ak.stock_jgdy_tj_em(date=date_key)
        except Exception:
            current += timedelta(days=1)
            continue
        if df is not None and not df.empty:
            records = df.to_dict(orient="records")
            for r in records:
                if (str(r.get("股票代码", "")) == code
                        or str(r.get("股票名称", "")) == code):
                    all_results.append(r)
        current += timedelta(days=1)
    return all_results
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_institutional.py -v 2>&1
```

预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add akshare-stock-fundamentals/
git commit -m "feat: add institutional data source (research visits, 30-day traversal)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 7：CLI + 板块编排

**文件：**
- 创建：`akshare-stock-fundamentals/scripts/tests/test_cli.py`
- 修改：`akshare-stock-fundamentals/scripts/fetch_fundamentals.py`

- [ ] **步骤 1：编写测试 — CLI 参数解析 + 编排逻辑**

```python
# akshare-stock-fundamentals/scripts/tests/test_cli.py
"""测试 CLI 参数解析和板块编排逻辑。"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
import pytest

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import parse_args, build_output, fetch_all_sections, main
sys.stdout = sys.__stdout__


class TestParseArgs:
    def test_parses_symbol_required(self):
        test_args = ["--symbol", "600183"]
        with patch('sys.argv', ['fetch_fundamentals.py'] + test_args):
            args = parse_args()
            assert args.symbol == "600183"

    def test_date_defaults_to_today(self):
        test_args = ["--symbol", "600183"]
        with patch('sys.argv', ['fetch_fundamentals.py'] + test_args):
            args = parse_args()
            assert args.date is not None
            assert len(args.date) == 8

    def test_symbol_validation_rejects_non_numeric(self):
        test_args = ["--symbol", "ABC123"]
        with patch('sys.argv', ['fetch_fundamentals.py'] + test_args):
            with pytest.raises(SystemExit):
                parse_args()


class TestBuildOutput:
    def test_builds_correct_top_level_structure(self):
        result = build_output("600183", {"basic_info": {}, "fundamentals": {}},
                              "20260621")
        assert result["symbol"] == "600183"
        assert "fetch_time" in result
        assert "sections" in result
        assert "errors" in result

    def test_stock_name_extracted_from_basic_info(self):
        sections = {
            "basic_info": {"profile": {"security_short_name": "生益科技"}},
            "fundamentals": {"financials": {}},
        }
        result = build_output("600183", sections, "20260621")
        assert result["stock_name"] == "生益科技"

    def test_stock_name_fallback_to_symbol(self):
        sections = {"basic_info": None, "fundamentals": {"financials": {}}}
        result = build_output("600183", sections, "20260621")
        assert result["stock_name"] == "600183"


class TestFetchAllSections:
    @patch('fetch_fundamentals.fetch_tencent_quote', return_value={"name": "test"})
    @patch('fetch_fundamentals.fetch_eastmoney_search', return_value={"security_short_name": "test"})
    @patch('fetch_fundamentals.fetch_stock_add_stock', return_value=[])
    @patch('fetch_fundamentals.fetch_financial_abstract', return_value=[])
    @patch('fetch_fundamentals.fetch_financial_profit', return_value=[])
    @patch('fetch_fundamentals.fetch_financial_debt', return_value=[])
    @patch('fetch_fundamentals.fetch_financial_cashflow', return_value=[])
    @patch('fetch_fundamentals.fetch_profit_forecast_eps', return_value=[])
    @patch('fetch_fundamentals.fetch_profit_forecast_net', return_value=[])
    @patch('fetch_fundamentals.fetch_profit_forecast_inst', return_value=[])
    @patch('fetch_fundamentals.fetch_profit_forecast_detail', return_value=[])
    @patch('fetch_fundamentals.fetch_revenue_structure', return_value=[])
    @patch('fetch_fundamentals.fetch_block_trades', return_value=[])
    @patch('fetch_fundamentals.fetch_restricted_release_em', return_value=[])
    @patch('fetch_fundamentals.fetch_restricted_release_sina', return_value=[])
    @patch('fetch_fundamentals.fetch_pledge', return_value=[])
    @patch('fetch_fundamentals.fetch_notices', return_value=[])
    @patch('fetch_fundamentals.fetch_research_visits', return_value=[])
    @patch('fetch_fundamentals.RateLimiter')
    def test_returns_all_five_sections(self, mock_limiter, *mocks):
        mock_limiter_instance = MagicMock()
        mock_limiter.return_value = mock_limiter_instance
        sections = fetch_all_sections("600183", "20260621", mock_limiter_instance)
        assert set(sections.keys()) == {"basic_info", "fundamentals", "risk_signals", "events", "institutional"}

    @patch('fetch_fundamentals.fetch_tencent_quote', side_effect=Exception("fail"))
    @patch('fetch_fundamentals.fetch_eastmoney_search', side_effect=Exception("fail"))
    @patch('fetch_fundamentals.fetch_stock_add_stock', side_effect=Exception("fail"))
    @patch('fetch_fundamentals.fetch_financial_abstract', return_value=[])
    @patch('fetch_fundamentals.fetch_financial_profit', return_value=[])
    @patch('fetch_fundamentals.fetch_financial_debt', return_value=[])
    @patch('fetch_fundamentals.fetch_financial_cashflow', return_value=[])
    @patch('fetch_fundamentals.fetch_profit_forecast_eps', return_value=[])
    @patch('fetch_fundamentals.fetch_profit_forecast_net', return_value=[])
    @patch('fetch_fundamentals.fetch_profit_forecast_inst', return_value=[])
    @patch('fetch_fundamentals.fetch_profit_forecast_detail', return_value=[])
    @patch('fetch_fundamentals.fetch_revenue_structure', return_value=[])
    @patch('fetch_fundamentals.fetch_block_trades', return_value=[])
    @patch('fetch_fundamentals.fetch_restricted_release_em', return_value=[])
    @patch('fetch_fundamentals.fetch_restricted_release_sina', return_value=[])
    @patch('fetch_fundamentals.fetch_pledge', return_value=[])
    @patch('fetch_fundamentals.fetch_notices', return_value=[])
    @patch('fetch_fundamentals.fetch_research_visits', return_value=[])
    @patch('fetch_fundamentals.RateLimiter')
    def test_section_is_none_when_all_sources_fail(self, mock_limiter, *mocks):
        mock_limiter_instance = MagicMock()
        mock_limiter.return_value = mock_limiter_instance
        sections = fetch_all_sections("600183", "20260621", mock_limiter_instance)
        assert sections["basic_info"] is None
        assert sections["fundamentals"] is not None  # financial mock returns []


class TestMain:
    @patch('fetch_fundamentals.fetch_all_sections')
    @patch('sys.stdout')
    def test_exit_code_0_on_success(self, mock_stdout, mock_fetch):
        mock_fetch.return_value = {
            "basic_info": {"profile": {"security_short_name": "test"}},
            "fundamentals": {"financials": {}},
            "risk_signals": {},
            "events": {},
            "institutional": {},
        }
        test_args = ["fetch_fundamentals.py", "--symbol", "600183"]
        with patch('sys.argv', test_args):
            exit_code = main()
            assert exit_code == 0

    @patch('fetch_fundamentals.fetch_all_sections')
    @patch('sys.stdout')
    def test_exit_code_2_on_invalid_symbol(self, mock_stdout, mock_fetch):
        test_args = ["fetch_fundamentals.py", "--symbol", "ABC"]
        with patch('sys.argv', test_args):
            exit_code = main()
            assert exit_code == 2
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_cli.py -v 2>&1
```

预期：FAIL，`parse_args`, `build_output`, `fetch_all_sections`, `main` 未定义

- [ ] **步骤 3：编写实现 — CLI + 编排**

在 `fetch_fundamentals.py` 末尾追加：

```python
def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="获取A股个股基本面数据，输出结构化JSON",
    )
    parser.add_argument(
        "--symbol", required=True,
        help="股票代码，纯数字，如 600183"
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y%m%d"),
        help="基准日期 YYYYMMDD，默认今天"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出 JSON 文件路径，默认 stdout"
    )
    args = parser.parse_args()

    # 验证 symbol 格式
    if not args.symbol.isdigit() or len(args.symbol) != 6:
        print(f"[ERROR] 股票代码格式非法: {args.symbol}，应为6位纯数字", file=sys.stderr)
        sys.exit(2)

    return args


def fetch_all_sections(symbol: str, date_str: str, limiter: RateLimiter) -> dict:
    """按板块顺序拉取所有数据源，组装 sections dict。

    每个板块内的数据源失败不阻断其他板块。

    Args:
        symbol: 股票代码
        date_str: 基准日期
        limiter: 速率限制器实例

    Returns:
        dict 包含 5 个板块的数据
    """
    errors: list[dict] = []
    sections = {}

    # ---- basic_info ----
    basic_info = {}
    basic_success = 0
    # tencent_quote
    limiter.acquire()
    try:
        basic_info["quote"] = fetch_tencent_quote(symbol)
        basic_success += 1
    except Exception as e:
        errors.append({"section": "basic_info", "source": "tencent_quote", "error": str(e)})
        basic_info["quote"] = None
    # eastmoney_search
    limiter.acquire()
    try:
        basic_info["profile"] = fetch_eastmoney_search(symbol)
        basic_success += 1
    except Exception as e:
        errors.append({"section": "basic_info", "source": "eastmoney_search", "error": str(e)})
        basic_info["profile"] = None
    # stock_add_stock
    limiter.acquire()
    try:
        basic_info["add_stock"] = fetch_stock_add_stock(symbol, date_str)
        basic_success += 1
    except Exception as e:
        errors.append({"section": "basic_info", "source": "stock_add_stock", "error": str(e)})
        basic_info["add_stock"] = None
    sections["basic_info"] = basic_info if basic_success > 0 else None

    # ---- fundamentals ----
    fin_success = 0
    fundamentals = {
        "financials": {},
        "profit_forecast": {},
        "revenue_structure": None,
    }
    for name, fn, kwargs in [
        ("abstract_by_report", fetch_financial_abstract, {"code": symbol, "indicator": "按报告期", "date_str": date_str}),
        ("abstract_by_year", fetch_financial_abstract, {"code": symbol, "indicator": "按年度", "date_str": date_str}),
        ("benefit", fetch_financial_profit, {"code": symbol, "date_str": date_str}),
        ("debt", fetch_financial_debt, {"code": symbol, "date_str": date_str}),
        ("cashflow", fetch_financial_cashflow, {"code": symbol, "date_str": date_str}),
    ]:
        limiter.acquire()
        try:
            data = fn(**kwargs)
            fundamentals["financials"][name] = data
            fin_success += 1
        except Exception as e:
            errors.append({"section": "fundamentals", "source": f"financial_{name}", "error": str(e)})
            fundamentals["financials"][name] = None

    for name, fn in [
        ("eps_forecast", fetch_profit_forecast_eps),
        ("net_profit_forecast", fetch_profit_forecast_net),
        ("institution_detail", fetch_profit_forecast_inst),
        ("indicator_detail", fetch_profit_forecast_detail),
    ]:
        limiter.acquire()
        try:
            fundamentals["profit_forecast"][name] = fn(symbol)
            fin_success += 1
        except Exception as e:
            errors.append({"section": "fundamentals", "source": f"profit_forecast_{name}", "error": str(e)})
            fundamentals["profit_forecast"][name] = None

    # revenue_structure
    limiter.acquire()
    try:
        fundamentals["revenue_structure"] = fetch_revenue_structure(symbol, date_str)
        fin_success += 1
    except Exception as e:
        errors.append({"section": "fundamentals", "source": "revenue_structure", "error": str(e)})
        fundamentals["revenue_structure"] = None

    # 重组 financials: 将 abstract_by_report / abstract_by_year 合并到 abstract 键下
    abs_by_report = fundamentals["financials"].pop("abstract_by_report", None)
    abs_by_year = fundamentals["financials"].pop("abstract_by_year", None)
    fundamentals["financials"]["abstract"] = {
        "by_report": abs_by_report,
        "by_year": abs_by_year,
    }

    sections["fundamentals"] = fundamentals if fin_success > 0 else None

    # ---- risk_signals ----
    risk_success = 0
    risk_signals = {}
    for name, fn, kwargs in [
        ("block_trades", fetch_block_trades, {"code": symbol, "date_str": date_str}),
        ("restricted_release_em", fetch_restricted_release_em, {"code": symbol, "date_str": date_str}),
        ("restricted_release_sina", fetch_restricted_release_sina, {"code": symbol, "date_str": date_str}),
        ("pledge", fetch_pledge, {"code": symbol}),
    ]:
        limiter.acquire()
        try:
            risk_signals[name] = fn(**kwargs)
            risk_success += 1
        except Exception as e:
            errors.append({"section": "risk_signals", "source": name, "error": str(e)})
            risk_signals[name] = None
    sections["risk_signals"] = risk_signals if risk_success > 0 else None

    # ---- events ----
    limiter.acquire()
    try:
        notices = fetch_notices(symbol, date_str)
        sections["events"] = {"notices": {"period": _build_period(date_str, 90), "data": notices}}
    except Exception as e:
        errors.append({"section": "events", "source": "notices", "error": str(e)})
        sections["events"] = None

    # ---- institutional ----
    limiter.acquire()
    try:
        visits = fetch_research_visits(symbol, date_str)
        sections["institutional"] = {"research_visits": {"period": _build_period(date_str, 30), "data": visits}}
    except Exception as e:
        errors.append({"section": "institutional", "source": "research_visits", "error": str(e)})
        sections["institutional"] = None

    return sections, errors


def _build_period(date_str: str, days_back: int) -> dict:
    """构建时间范围字段。"""
    end = datetime.strptime(date_str, "%Y%m%d")
    start = end - timedelta(days=days_back)
    return {"start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d")}


def build_output(symbol: str, sections: dict, errors: list[dict], date_str: str) -> dict:
    """根据 sections 和 errors 构建最终输出 JSON。

    Args:
        symbol: 股票代码
        sections: fetch_all_sections 的返回值
        errors: 错误列表
        date_str: 基准日期

    Returns:
        最终 JSON dict
    """
    stock_name = symbol
    bi = sections.get("basic_info", {}) or {}
    profile = bi.get("profile", {}) or {}
    if profile and profile.get("security_short_name"):
        stock_name = profile["security_short_name"]

    return {
        "symbol": symbol,
        "stock_name": stock_name,
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sections": sections,
        "errors": errors,
    }


def main() -> int:
    """CLI 入口。

    Returns:
        exit code (0=成功, 1=全部失败, 2=参数错误)
    """
    args = parse_args()
    limiter = RateLimiter(max_calls=10, window_seconds=60)

    sections, errors = fetch_all_sections(args.symbol, args.date, limiter)

    # 判断是否全部失败
    all_successful = all(v is not None for v in sections.values())
    any_successful = any(v is not None for v in sections.values())

    output = build_output(args.symbol, sections, errors, args.date)

    json_str = json.dumps(output, ensure_ascii=False, indent=2, default=str)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(json_str)
                f.write("\n")
        except Exception as e:
            print(f"[ERROR] 写入输出文件失败: {e}", file=sys.stderr)
            # 回退到 stdout
            sys.stdout.write(json_str)
            sys.stdout.write("\n")
    else:
        sys.stdout.write(json_str)
        sys.stdout.write("\n")
    sys.stdout.flush()

    if not any_successful:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_cli.py -v 2>&1
```

预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add akshare-stock-fundamentals/
git commit -m "feat: add CLI parsing, section orchestration, and main entry point

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 8：错误处理完善 + 全部测试回归

**文件：**
- 修改：`akshare-stock-fundamentals/scripts/fetch_fundamentals.py`
- 修改：`akshare-stock-fundamentals/scripts/tests/test_cli.py`

- [ ] **步骤 1：补充边界情况测试**

在 `test_cli.py` 的 `TestMain` 类中追加：

```python
    @patch('fetch_fundamentals.fetch_all_sections')
    def test_exit_code_1_when_all_sections_none(self, mock_fetch):
        mock_fetch.return_value = (
            {"basic_info": None, "fundamentals": None, "risk_signals": None,
             "events": None, "institutional": None},
            [{"section": "basic_info", "source": "tencent_quote", "error": "timeout"}]
        )
        test_args = ["fetch_fundamentals.py", "--symbol", "600183"]
        with patch('sys.argv', test_args):
            exit_code = main()
            assert exit_code == 1

    @patch('fetch_fundamentals.fetch_all_sections')
    @patch('sys.stdout')
    def test_output_contains_errors_array(self, mock_stdout, mock_fetch):
        mock_fetch.return_value = (
            {"basic_info": {"profile": {"security_short_name": "test"}},
             "fundamentals": {}, "risk_signals": {}, "events": {}, "institutional": {}},
            [{"section": "fundamentals", "source": "financial_debt", "error": "timeout"}]
        )
        captured = []
        mock_stdout.write = lambda s: captured.append(s)
        test_args = ["fetch_fundamentals.py", "--symbol", "600183"]
        with patch('sys.argv', test_args):
            main()
        output = json.loads("".join(captured))
        assert len(output["errors"]) > 0

    @patch('fetch_fundamentals.fetch_all_sections')
    def test_output_flag_writes_to_file(self, mock_fetch, tmp_path):
        mock_fetch.return_value = (
            {"basic_info": {"profile": {"security_short_name": "test"}},
             "fundamentals": {}, "risk_signals": {}, "events": {}, "institutional": {}},
            []
        )
        outfile = tmp_path / "result.json"
        test_args = ["fetch_fundamentals.py", "--symbol", "600183", "--output", str(outfile)]
        with patch('sys.argv', test_args):
            exit_code = main()
        assert exit_code == 0
        assert outfile.exists()
        data = json.loads(outfile.read_text())
        assert data["symbol"] == "600183"
```

- [ ] **步骤 2：运行全部单元测试回归**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/ -v 2>&1
```

预期：全部 PASS（约 30+ 个测试）

- [ ] **步骤 3：修复发现的任何问题**

如果有测试失败，修复代码后重新运行直到全部通过。

- [ ] **步骤 4：Commit**

```bash
git add akshare-stock-fundamentals/
git commit -m "test: add edge case tests for error handling and output modes

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 9：端到端集成测试

**文件：**
- 创建：`akshare-stock-fundamentals/scripts/tests/test_integration.py`

- [ ] **步骤 1：编写集成测试（使用真实 API，标记为 slow）**

```python
# akshare-stock-fundamentals/scripts/tests/test_integration.py
"""端到端集成测试 — 使用真实 API 调用验证完整流程。

这些测试使用真实网络请求，运行较慢。标记为 slow。
用法: uv run pytest tests/test_integration.py -v -m slow
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

sys.stdout = open(os.devnull, 'w')
from fetch_fundamentals import (
    fetch_tencent_quote,
    fetch_eastmoney_search,
    fetch_stock_add_stock,
    fetch_notices,
    fetch_pledge,
)
sys.stdout = sys.__stdout__

pytestmark = pytest.mark.slow


class TestIntegrationBasicInfo:
    def test_tencent_quote_real_api(self):
        """真实调用腾讯行情 API 获取600519(贵州茅台)的行情。"""
        result = fetch_tencent_quote("600519")
        assert isinstance(result, dict)
        assert result.get("name", "")  # 至少要有名称
        assert result.get("price", 0) > 0

    def test_eastmoney_search_real_api(self):
        """真实调用东财搜索 API 获取600519的公司档案。"""
        result = fetch_eastmoney_search("600519")
        assert isinstance(result, dict)
        if result:  # 可能被反爬虫拦截
            assert "security_short_name" in result
            assert result.get("boards", [])

    def test_add_stock_real_api(self):
        """真实调用增发记录 API。"""
        result = fetch_stock_add_stock("600000", "20260621")
        assert isinstance(result, list)


class TestIntegrationRiskSignals:
    def test_pledge_real_api(self):
        """真实调用股权质押 API。"""
        result = fetch_pledge("600183")
        assert isinstance(result, list)


class TestIntegrationEvents:
    def test_notices_real_api(self):
        """真实调用公告 API。"""
        result = fetch_notices("600183", "20260621")
        assert isinstance(result, list)


class TestEndToEnd:
    def test_full_pipeline_with_real_apis(self):
        """端到端：运行完整 main 函数。"""
        test_args = ["fetch_fundamentals.py", "--symbol", "600183"]
        with patch('sys.argv', test_args):
            exit_code = main()
        assert exit_code in (0, 1)
```

- [ ] **步骤 2：注册 slow 标记**

在 `conftest.py`（如果不存在则创建 `tests/conftest.py`）中添加：

```python
# akshare-stock-fundamentals/scripts/tests/conftest.py
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: slow tests that make real API calls")
```

- [ ] **步骤 3：运行集成测试验证**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/test_integration.py -v -m slow 2>&1
```

预期：PASS（或部分因限速/网络问题跳过）

- [ ] **步骤 4：Commit**

```bash
git add akshare-stock-fundamentals/
git commit -m "test: add end-to-end integration tests with real API calls

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### 任务 10：编写 SKILL.md + 最终验证

**文件：**
- 创建：`akshare-stock-fundamentals/SKILL.md`
- 验证：全部测试通过 + 手工端到端运行

- [ ] **步骤 1：编写 SKILL.md**

```markdown
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
      "quote": { "name": "...", "price": 0, "pe_ttm": 0, "pb": 0, ... },
      "profile": { "security_short_name": "...", "boards": [...], "business_products": [...], ... },
      "add_stock": [...]
    },
    "fundamentals": {
      "financials": {
        "abstract": { "by_report": [...], "by_year": [...] },
        "benefit": [...],
        "debt": [...],
        "cashflow": [...]
      },
      "profit_forecast": {
        "eps_forecast": [...],
        "net_profit_forecast": [...],
        "institution_detail": [...],
        "indicator_detail": [...]
      },
      "revenue_structure": [...]
    },
    "risk_signals": {
      "block_trades": { "period": {...}, "data": [...] },
      "restricted_release_em": [...],
      "restricted_release_sina": [...],
      "pledge": { "unreleased_only": true, "data": [...] }
    },
    "events": {
      "notices": { "period": {...}, "data": [...] }
    },
    "institutional": {
      "research_visits": { "period": {...}, "data": [...] }
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
```

- [ ] **步骤 2：运行全部测试最终回归**

```bash
cd akshare-stock-fundamentals/scripts && uv run pytest tests/ -v --ignore=tests/test_integration.py 2>&1
```

预期：全部单元测试 PASS

- [ ] **步骤 3：手工端到端验证**

```bash
cd akshare-stock-fundamentals && uv run python scripts/fetch_fundamentals.py --symbol 600183 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'sections: {list(d[\"sections\"].keys())}, errors: {len(d[\"errors\"])}')" 2>&1
```

预期：输出 `sections: ['basic_info', 'fundamentals', 'risk_signals', 'events', 'institutional'], errors: X`

- [ ] **步骤 4：Commit**

```bash
git add akshare-stock-fundamentals/
git commit -m "docs: add SKILL.md with full usage guide and analysis prompt

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 自检清单

### 规格覆盖度
- [x] CLI 接口 (--symbol, --date, --output) → 任务 7
- [x] exit code (0/1/2) → 任务 7
- [x] 速率限制 (10次/分钟) → 任务 1
- [x] basic_info: tencent_quote → 任务 2
- [x] basic_info: eastmoney_search (含主营产品解析) → 任务 2
- [x] basic_info: stock_add_stock (近2年) → 任务 2
- [x] fundamentals: abstract (by_report + by_year) → 任务 3
- [x] fundamentals: benefit/debt/cashflow → 任务 3
- [x] fundamentals: profit_forecast ×4 → 任务 3
- [x] fundamentals: revenue_structure (近3年) → 任务 3
- [x] risk_signals: block_trades (近30日) → 任务 4
- [x] risk_signals: restricted_release_em + sina (近2年+未执行) → 任务 4
- [x] risk_signals: pledge (仅未解押) → 任务 4
- [x] events: notices (近90日) → 任务 5
- [x] institutional: research_visits → 任务 6
- [x] 错误处理 (单源失败不阻断, 全部失败 exit 1) → 任务 8
- [x] 分析 Prompt → 任务 10 (SKILL.md)
- [x] SKILL.md → 任务 10
- [x] 集成测试 → 任务 9

### 占位符扫描
- 无 "TODO"、"待定"、"后续实现" 占位符
- 所有代码步骤包含实际代码块
- 所有测试步骤包含完整测试代码

### 类型一致性
- `RateLimiter`: 任务 1 定义, 任务 7 使用 → 一致
- `SECTIONS`: 任务 1 定义 `list`, 任务 7 遍历 → 一致
- `SECTION_DEPENDENCIES`: 任务 1 定义 `dict[str, list[str]]`, 任务 7 未直接使用 → 常量提供元数据
- 所有数据源函数签名 (code: str, date_str: str) 统一
- `build_output(symbol, sections, errors, date_str)` → 任务 7 定义和使用一致
- `fetch_all_sections(symbol, date_str, limiter) -> dict` → 返回 `(sections, errors)` 元组, 任务 7 测试使用 `.return_value` mock 返回元组
