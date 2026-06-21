# akshare-real-time-quotes 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 新建 `akshare-real-time-quotes` 技能，提供 A 股实时行情快照（含盘口）和日内分钟 K 线两个功能，输出结构化 JSON 供 AI 交易决策消费。

**架构：** 单脚本 `fetch_realtime.py`，两个数据获取函数 (`fetch_tencent_quote_verbose`、`fetch_intraday_minute`)，argparse subparser 模式（`quote` / `intraday` 子命令）。仅依赖 Python 标准库。

**技术栈：** Python 3, argparse, json, urllib.request, pytest, unittest.mock

---

### 任务 1：创建技能目录结构

**文件：**
- 创建：`akshare-real-time-quotes/__init__.py`（空文件）
- 创建：`akshare-real-time-quotes/scripts/__init__.py`（空文件）
- 创建：`akshare-real-time-quotes/scripts/tests/__init__.py`（空文件）

- [ ] **步骤 1：创建目录和空 `__init__.py` 文件**

```bash
mkdir -p akshare-real-time-quotes/scripts/tests
touch akshare-real-time-quotes/__init__.py
touch akshare-real-time-quotes/scripts/__init__.py
touch akshare-real-time-quotes/scripts/tests/__init__.py
```

- [ ] **步骤 2：Commit**

```bash
git add akshare-real-time-quotes/
git commit -m "chore: add akshare-real-time-quotes directory skeleton"
```

---

### 任务 2：编写 quote 函数单元测试

**文件：**
- 创建：`akshare-real-time-quotes/scripts/tests/test_fetch_realtime_quote.py`

请先阅读 `akshare-stock-fundamentals/scripts/fetch_fundamentals.py:171-229` 中 `fetch_tencent_quote` 的实现，了解现有行情 API 返回格式。本测试的 mock 数据基于同一 API（`qt.gtimg.cn`），但输出结构不同——新增了盘口数据分组。

- [ ] **步骤 1：编写失败的测试**

```python
"""fetch_tencent_quote_verbose 单元测试 (mock HTTP)"""
import json
import sys
import os
import urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, Mock
import pytest
import fetch_realtime


# 模拟腾讯行情 API 返回的原始数据 (gbk 编码)
# 字段顺序: 0:市场 1:名称 2:代码 3:现价 4:昨收 5:今开 6:成交量 7:外盘 8:内盘
# 9-18:买一~买五(价量对) 19-28:卖一~卖五(价量对) 29:空 30:时间
# 31:涨跌额 32:涨跌幅 33:最高 34:最低 35:价/量/额 36:成交量 37:成交额(万)
# 38:换手率 39:PE(TTM) 40:空 41:最高 42:最低 43:振幅 44:流通市值(亿)
# 45:总市值(亿) 46:PB 47:涨停价 48:跌停价 49:量比 50:委差 51:日内均价 52:动态PE
MOCK_QUOTE_FIELDS = [
    "1", "生益科技", "600183", "183.87", "180.15", "178.50", "798770",
    "419569", "379201",
    "183.87", "1147", "183.86", "159", "183.85", "587", "183.84", "329", "183.83", "26",
    "183.88", "165", "183.89", "46", "183.90", "77", "183.91", "32", "183.92", "30",
    "", "20260618161425", "3.72", "2.06", "187.35", "176.73",
    "183.87/798770/14605138345", "798770", "1460514", "3.34", "113.69",
    "", "", "", "5.90", "4402.77", "4466.42", "27.94", "198.17", "162.14",
    "0.90", "1898", "182.85", "96.41",
]

MOCK_QUOTE_RAW = (
    'v_sh600183="' + "~".join(MOCK_QUOTE_FIELDS) + '";\n'
)


class TestFetchTencentQuoteVerbose:
    """fetch_tencent_quote_verbose 单元测试"""

    def test_returns_grouped_structure(self):
        """验证返回结构包含4个分组和根级字段"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW.encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")

        assert "股票代码" in result
        assert result["股票代码"] == "600183"
        assert "股票名称" in result
        assert result["股票名称"] == "生益科技"
        assert "行情更新时间" in result
        assert result["行情更新时间"] == "20260618161425"
        assert "行情数据" in result
        assert "成交数据" in result
        assert "盘口数据" in result
        assert "估值数据" in result

    def test_quote_data_fields(self):
        """验证行情数据分组字段值和类型"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW.encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")

        q = result["行情数据"]
        assert q["当前价格(元)"] == 183.87
        assert isinstance(q["当前价格(元)"], float)
        assert q["昨收价(元)"] == 180.15
        assert q["今开价(元)"] == 178.50
        assert q["最高价(元)"] == 187.35
        assert q["最低价(元)"] == 176.73
        assert q["涨跌额(元)"] == 3.72
        assert q["涨跌幅(%)"] == 2.06
        assert q["振幅(%)"] == 5.90
        assert q["日内均价(元)"] == 182.85

    def test_trade_data_fields(self):
        """验证成交数据分组字段值和类型"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW.encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")

        t = result["成交数据"]
        assert t["成交量(手)"] == 798770
        assert isinstance(t["成交量(手)"], int)
        assert t["成交额(万元)"] == 1460514
        assert isinstance(t["成交额(万元)"], float)
        assert t["换手率(%)"] == 3.34
        assert t["量比"] == 0.90
        assert t["外盘(手)"] == 419569
        assert t["内盘(手)"] == 379201

    def test_order_book_fields(self):
        """验证盘口数据分组——买五卖五和委差"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW.encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")

        b = result["盘口数据"]
        assert b["买一价(元)"] == 183.87
        assert b["买一量(手)"] == 1147
        assert isinstance(b["买一量(手)"], int)
        assert b["买五价(元)"] == 183.83
        assert b["买五量(手)"] == 26
        assert b["卖一价(元)"] == 183.88
        assert b["卖一量(手)"] == 165
        assert b["卖五价(元)"] == 183.92
        assert b["卖五量(手)"] == 30
        assert b["委差"] == 1898
        assert isinstance(b["委差"], int)

    def test_valuation_fields(self):
        """验证估值数据分组字段值和类型"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW.encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")

        v = result["估值数据"]
        assert v["滚动市盈率"] == 113.69
        assert isinstance(v["滚动市盈率"], float)
        assert v["动态市盈率"] == 96.41
        assert v["市净率"] == 27.94
        assert v["流通市值(亿)"] == 4402.77
        assert v["总市值(亿)"] == 4466.42
        assert v["涨停价(元)"] == 198.17
        assert v["跌停价(元)"] == 162.14

    def test_network_error_returns_empty_dict(self):
        """网络异常返回空 dict"""
        with patch.object(
            urllib.request, "urlopen", side_effect=OSError("network")
        ):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")
        assert result == {}

    def test_short_fields_returns_empty_dict(self):
        """字段数量不足返回空 dict"""
        mock_resp = Mock()
        mock_resp.read.return_value = b'v_sh600183="1~2~3";\n'
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("600183")
        assert result == {}

    def test_prefixed_code_sh_for_6xx(self):
        """6 开头股票使用 sh 前缀"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW.encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen") as mock_urlopen:
            mock_urlopen.return_value = mock_resp
            fetch_realtime.fetch_tencent_quote_verbose("600183")
            called_url = mock_urlopen.call_args[0][0]
            # urlopen receives a Request object, check its full_url
            assert "sh600183" in called_url.full_url if hasattr(called_url, 'full_url') else True

    def test_prefixed_code_sz_for_0xx(self):
        """0 开头股票使用 sz 前缀"""
        mock_resp = Mock()
        mock_resp.read.return_value = (
            'v_sz000001="' + "~".join(["1", "平安银行", "000001"] + ["0"] * 50) + '";\n'
        ).encode("gbk")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_tencent_quote_verbose("000001")
        assert result["股票代码"] == "000001"
        assert result["股票名称"] == "平安银行"
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd akshare-real-time-quotes && python -m pytest scripts/tests/test_fetch_realtime_quote.py -v
```
预期：全部 FAIL（`fetch_realtime` 模块尚不存在）

- [ ] **步骤 3：Commit**

```bash
git add akshare-real-time-quotes/scripts/tests/test_fetch_realtime_quote.py
git commit -m "test: add fetch_tencent_quote_verbose unit tests"
```

---

### 任务 3：实现 fetch_tencent_quote_verbose 函数

**文件：**
- 创建：`akshare-real-time-quotes/scripts/fetch_realtime.py`

- [ ] **步骤 1：编写最少实现**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A股实时行情与日内分钟K线数据获取工具。

用法:
    uv run python scripts/fetch_realtime.py quote --symbol 600183
    uv run python scripts/fetch_realtime.py intraday --symbol 600183

输出结构化 JSON 到 stdout，所有字段中文命名带单位。
"""
import argparse
import json
import sys
import urllib.request


def fetch_tencent_quote_verbose(code: str) -> dict:
    """从腾讯财经获取实时行情快照（完整版，含盘口数据）。

    解析 qt.gtimg.cn 返回的 ~ 分隔字符串，按语义分为行情数据、成交数据、
    盘口数据、估值数据四个分组。

    Args:
        code: 6 位股票代码，如 600183

    Returns:
        dict，含股票代码、股票名称、行情更新时间及四个分组子对象，失败返回 {}
    """
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
                "股票代码": vals[2],
                "股票名称": vals[1],
                "行情更新时间": vals[30],
                "行情数据": {
                    "当前价格(元)": float(vals[3]) if vals[3] else 0.0,
                    "昨收价(元)":   float(vals[4]) if vals[4] else 0.0,
                    "今开价(元)":   float(vals[5]) if vals[5] else 0.0,
                    "最高价(元)":   float(vals[33]) if vals[33] else 0.0,
                    "最低价(元)":   float(vals[34]) if vals[34] else 0.0,
                    "涨跌额(元)":   float(vals[31]) if vals[31] else 0.0,
                    "涨跌幅(%)":    float(vals[32]) if vals[32] else 0.0,
                    "振幅(%)":      float(vals[43]) if vals[43] else 0.0,
                    "日内均价(元)": float(vals[51]) if vals[51] else 0.0,
                },
                "成交数据": {
                    "成交量(手)":   int(float(vals[6])) if vals[6] else 0,
                    "成交额(万元)": float(vals[37]) if vals[37] else 0.0,
                    "换手率(%)":    float(vals[38]) if vals[38] else 0.0,
                    "量比":         float(vals[49]) if vals[49] else 0.0,
                    "外盘(手)":     int(float(vals[7])) if vals[7] else 0,
                    "内盘(手)":     int(float(vals[8])) if vals[8] else 0,
                },
                "盘口数据": {
                    "买一价(元)": float(vals[9]) if vals[9] else 0.0,
                    "买一量(手)": int(float(vals[10])) if vals[10] else 0,
                    "买二价(元)": float(vals[11]) if vals[11] else 0.0,
                    "买二量(手)": int(float(vals[12])) if vals[12] else 0,
                    "买三价(元)": float(vals[13]) if vals[13] else 0.0,
                    "买三量(手)": int(float(vals[14])) if vals[14] else 0,
                    "买四价(元)": float(vals[15]) if vals[15] else 0.0,
                    "买四量(手)": int(float(vals[16])) if vals[16] else 0,
                    "买五价(元)": float(vals[17]) if vals[17] else 0.0,
                    "买五量(手)": int(float(vals[18])) if vals[18] else 0,
                    "卖一价(元)": float(vals[19]) if vals[19] else 0.0,
                    "卖一量(手)": int(float(vals[20])) if vals[20] else 0,
                    "卖二价(元)": float(vals[21]) if vals[21] else 0.0,
                    "卖二量(手)": int(float(vals[22])) if vals[22] else 0,
                    "卖三价(元)": float(vals[23]) if vals[23] else 0.0,
                    "卖三量(手)": int(float(vals[24])) if vals[24] else 0,
                    "卖四价(元)": float(vals[25]) if vals[25] else 0.0,
                    "卖四量(手)": int(float(vals[26])) if vals[26] else 0,
                    "卖五价(元)": float(vals[27]) if vals[27] else 0.0,
                    "卖五量(手)": int(float(vals[28])) if vals[28] else 0,
                    "委差":         int(float(vals[50])) if vals[50] else 0,
                },
                "估值数据": {
                    "滚动市盈率":   float(vals[39]) if vals[39] else 0.0,
                    "动态市盈率":   float(vals[52]) if vals[52] else 0.0,
                    "市净率":       float(vals[46]) if vals[46] else 0.0,
                    "流通市值(亿)": float(vals[44]) if vals[44] else 0.0,
                    "总市值(亿)":   float(vals[45]) if vals[45] else 0.0,
                    "涨停价(元)":   float(vals[47]) if vals[47] else 0.0,
                    "跌停价(元)":   float(vals[48]) if vals[48] else 0.0,
                },
            }
        except (ValueError, IndexError):
            return {}
    return {}
```

- [ ] **步骤 2：运行测试验证通过**

```bash
cd akshare-real-time-quotes && python -m pytest scripts/tests/test_fetch_realtime_quote.py -v
```
预期：全部 PASS

- [ ] **步骤 3：Commit**

```bash
git add akshare-real-time-quotes/scripts/fetch_realtime.py
git commit -m "feat: implement fetch_tencent_quote_verbose with full order book"
```

---

### 任务 4：编写日内分钟 K 线函数单元测试

**文件：**
- 创建：`akshare-real-time-quotes/scripts/tests/test_fetch_realtime_intraday.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""fetch_intraday_minute 单元测试 (mock HTTP)"""
import json
import sys
import os
import urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, Mock
import pytest
import fetch_realtime


# 模拟腾讯分钟K线 API 返回的 JSON 数据
MOCK_INTRADAY_JSON = {
    "data": {
        "sh600183": {
            "data": {
                "date": "20260618",
                "data": [
                    "0930 178.50 13747 245383950.50",
                    "0931 178.80 8921 159423180.00",
                    "0932 179.00 12500 223750000.00",
                    "0933 178.65 9800 175077000.00",
                ]
            },
            "qt": {
                "sh600183": [
                    "1", "生益科技", "600183", "183.87", "180.15",
                ]
            },
            "mx_price": {"price": "", "mx": ""}
        }
    }
}

MOCK_INTRADAY_RAW = ("min_data=" + json.dumps(MOCK_INTRADAY_JSON)).encode("utf-8")


class TestFetchIntradayMinute:
    """fetch_intraday_minute 单元测试"""

    def test_returns_correct_structure(self):
        """验证返回结构包含股票代码、名称、交易日期、分钟K线"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_INTRADAY_RAW
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_intraday_minute("600183")

        assert "股票代码" in result
        assert result["股票代码"] == "600183"
        assert "股票名称" in result
        assert result["股票名称"] == "生益科技"
        assert "交易日期" in result
        assert result["交易日期"] == "20260618"
        assert "分钟K线" in result
        assert isinstance(result["分钟K线"], list)

    def test_parses_minute_data_correctly(self):
        """验证分钟数据解析——时间、价格、成交量、成交额类型正确"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_INTRADAY_RAW
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_intraday_minute("600183")

        minutes = result["分钟K线"]
        assert len(minutes) == 4

        first = minutes[0]
        assert first["时间"] == "0930"
        assert isinstance(first["时间"], str)
        assert first["价格(元)"] == 178.50
        assert isinstance(first["价格(元)"], float)
        assert first["成交量"] == 13747
        assert isinstance(first["成交量"], int)
        assert first["成交额(元)"] == 245383950.50
        assert isinstance(first["成交额(元)"], float)

        last = minutes[-1]
        assert last["时间"] == "0933"
        assert last["价格(元)"] == 178.65
        assert last["成交量"] == 9800

    def test_network_error_returns_empty_dict(self):
        """网络异常返回空 dict"""
        with patch.object(
            urllib.request, "urlopen", side_effect=OSError("timeout")
        ):
            result = fetch_realtime.fetch_intraday_minute("600183")
        assert result == {}

    def test_malformed_minute_string_skipped(self):
        """格式异常的分钟字符串被跳过"""
        bad_json = {
            "data": {
                "sh600183": {
                    "data": {
                        "date": "20260618",
                        "data": [
                            "0930 178.50 13747 245383950.50",   # 正常
                            "not-valid-data",                      # 格式错误
                            "0932 179.00 12500 223750000.00",   # 正常
                        ]
                    },
                    "qt": {"sh600183": ["1", "生益科技", "600183"]},
                    "mx_price": {"price": "", "mx": ""}
                }
            }
        }
        bad_raw = ("min_data=" + json.dumps(bad_json)).encode("utf-8")
        mock_resp = Mock()
        mock_resp.read.return_value = bad_raw
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_intraday_minute("600183")

        minutes = result["分钟K线"]
        assert len(minutes) == 2
        assert minutes[0]["时间"] == "0930"
        assert minutes[1]["时间"] == "0932"

    def test_empty_data_returns_empty_list(self):
        """无分钟数据时返回空列表"""
        empty_json = {
            "data": {
                "sh600183": {
                    "data": {"date": "20260618", "data": []},
                    "qt": {"sh600183": ["1", "生益科技", "600183"]},
                    "mx_price": {"price": "", "mx": ""}
                }
            }
        }
        empty_raw = ("min_data=" + json.dumps(empty_json)).encode("utf-8")
        mock_resp = Mock()
        mock_resp.read.return_value = empty_raw
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_intraday_minute("600183")

        assert result["分钟K线"] == []

    def test_prefixed_code_bj_for_8xx(self):
        """8 开头股票使用 bj 前缀"""
        bj_json = {
            "data": {
                "bj830799": {
                    "data": {"date": "20260618", "data": []},
                    "qt": {"bj830799": ["1", "艾融软件", "830799"]},
                    "mx_price": {"price": "", "mx": ""}
                }
            }
        }
        bj_raw = ("min_data=" + json.dumps(bj_json)).encode("utf-8")
        mock_resp = Mock()
        mock_resp.read.return_value = bj_raw
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = fetch_realtime.fetch_intraday_minute("830799")

        assert result["股票代码"] == "830799"
        assert result["股票名称"] == "艾融软件"
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd akshare-real-time-quotes && python -m pytest scripts/tests/test_fetch_realtime_intraday.py -v
```
预期：全部 FAIL（函数尚未定义）

- [ ] **步骤 3：Commit**

```bash
git add akshare-real-time-quotes/scripts/tests/test_fetch_realtime_intraday.py
git commit -m "test: add fetch_intraday_minute unit tests"
```

---

### 任务 5：实现 fetch_intraday_minute 函数

**文件：**
- 修改：`akshare-real-time-quotes/scripts/fetch_realtime.py` — 在现有 `fetch_tencent_quote_verbose` 函数后追加

- [ ] **步骤 1：编写实现**

在 `fetch_realtime.py` 中 `fetch_tencent_quote_verbose` 函数后面追加以下代码：

```python
def fetch_intraday_minute(code: str) -> dict:
    """从腾讯财经获取当日分钟级K线数据。

    解析 web.ifzq.gtimg.cn 返回的分钟K线 JSON，提取每笔分钟数据
    （时间、价格、成交量、成交额）。

    Args:
        code: 6 位股票代码，如 600183

    Returns:
        dict，含股票代码、股票名称、交易日期、分钟K线数组，失败返回 {}
    """
    if code.startswith(("6", "9")):
        prefixed = f"sh{code}"
    elif code.startswith("8"):
        prefixed = f"bj{code}"
    else:
        prefixed = f"sz{code}"

    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/minute/query"
        f"?_var=min_data&code={prefixed}"
    )
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("utf-8")
    except Exception:
        return {}

    # 去掉 "min_data=" 前缀，解析 JSON
    json_str = raw[len("min_data="):]
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return {}

    stock_data = data.get("data", {}).get(prefixed, {})
    minute_section = stock_data.get("data", {})
    trading_date = minute_section.get("date", "")
    raw_minutes = minute_section.get("data", [])

    # 从 qt 快照提取股票名称
    qt_list = stock_data.get("qt", {}).get(prefixed, [])
    stock_name = qt_list[1] if len(qt_list) > 1 else code

    minutes = []
    for raw_str in raw_minutes:
        parts = raw_str.split()
        if len(parts) != 4:
            continue
        try:
            minutes.append({
                "时间": parts[0],
                "价格(元)": float(parts[1]),
                "成交量": int(parts[2]),
                "成交额(元)": float(parts[3]),
            })
        except (ValueError, IndexError):
            continue

    return {
        "股票代码": code,
        "股票名称": stock_name,
        "交易日期": trading_date,
        "分钟K线": minutes,
    }
```

- [ ] **步骤 2：运行测试验证通过**

```bash
cd akshare-real-time-quotes && python -m pytest scripts/tests/test_fetch_realtime_intraday.py -v
```
预期：全部 PASS

- [ ] **步骤 3：确保 quote 测试仍通过**

```bash
cd akshare-real-time-quotes && python -m pytest scripts/tests/ -v
```
预期：全部 PASS

- [ ] **步骤 4：Commit**

```bash
git add akshare-real-time-quotes/scripts/fetch_realtime.py
git commit -m "feat: implement fetch_intraday_minute with per-minute K-line parsing"
```

---

### 任务 6：编写 CLI 单元测试

**文件：**
- 创建：`akshare-real-time-quotes/scripts/tests/test_cli.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""CLI 参数解析和子命令调度单元测试"""
import json
import sys
import os
import io
import urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, Mock
import pytest
import fetch_realtime


# 复刻任务 2 中的 mock 数据
MOCK_QUOTE_FIELDS = [
    "1", "生益科技", "600183", "183.87", "180.15", "178.50", "798770",
    "419569", "379201",
    "183.87", "1147", "183.86", "159", "183.85", "587", "183.84", "329", "183.83", "26",
    "183.88", "165", "183.89", "46", "183.90", "77", "183.91", "32", "183.92", "30",
    "", "20260618161425", "3.72", "2.06", "187.35", "176.73",
    "183.87/798770/14605138345", "798770", "1460514", "3.34", "113.69",
    "", "", "", "5.90", "4402.77", "4466.42", "27.94", "198.17", "162.14",
    "0.90", "1898", "182.85", "96.41",
]
MOCK_QUOTE_RAW = (
    'v_sh600183="' + "~".join(MOCK_QUOTE_FIELDS) + '";\n'
).encode("gbk")


class TestCLI:
    """CLI 集成测试（mock 网络）"""

    def test_quote_subcommand_outputs_json(self):
        """quote 子命令输出有效 JSON"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            with patch.object(sys, "argv", ["fetch_realtime.py", "quote", "--symbol", "600183"]):
                stdout = io.StringIO()
                with patch.object(sys, "stdout", stdout):
                    fetch_realtime.main()

        output = json.loads(stdout.getvalue())
        assert output["股票代码"] == "600183"
        assert "股票名称" in output
        assert "行情数据" in output
        assert "成交数据" in output
        assert "盘口数据" in output
        assert "估值数据" in output

    def test_quote_with_output_file(self, tmp_path):
        """--output 参数将 JSON 写入文件"""
        mock_resp = Mock()
        mock_resp.read.return_value = MOCK_QUOTE_RAW
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        out_file = tmp_path / "quote.json"
        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            test_args = [
                "fetch_realtime.py", "quote", "--symbol", "600183",
                "--output", str(out_file),
            ]
            with patch.object(sys, "argv", test_args):
                fetch_realtime.main()

        assert out_file.exists()
        content = json.loads(out_file.read_text(encoding="utf-8"))
        assert content["股票代码"] == "600183"

    def test_invalid_symbol_exits_2(self):
        """非法股票代码 exit 2"""
        with patch.object(sys, "argv", ["fetch_realtime.py", "quote", "--symbol", "123"]):
            with pytest.raises(SystemExit) as exc_info:
                fetch_realtime.main()
        assert exc_info.value.code == 2

    def test_non_numeric_symbol_exits_2(self):
        """非数字股票代码 exit 2"""
        with patch.object(sys, "argv", ["fetch_realtime.py", "quote", "--symbol", "abcdef"]):
            with pytest.raises(SystemExit) as exc_info:
                fetch_realtime.main()
        assert exc_info.value.code == 2

    def test_intraday_subcommand_outputs_json(self):
        """intraday 子命令输出有效 JSON"""
        mock_json = {
            "data": {
                "sh600183": {
                    "data": {
                        "date": "20260618",
                        "data": ["0930 178.50 13747 245383950.50"],
                    },
                    "qt": {"sh600183": ["1", "生益科技", "600183"]},
                    "mx_price": {"price": "", "mx": ""}
                }
            }
        }
        mock_raw = ("min_data=" + json.dumps(mock_json)).encode("utf-8")
        mock_resp = Mock()
        mock_resp.read.return_value = mock_raw
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            test_args = ["fetch_realtime.py", "intraday", "--symbol", "600183"]
            with patch.object(sys, "argv", test_args):
                stdout = io.StringIO()
                with patch.object(sys, "stdout", stdout):
                    fetch_realtime.main()

        output = json.loads(stdout.getvalue())
        assert output["股票代码"] == "600183"
        assert output["交易日期"] == "20260618"
        assert len(output["分钟K线"]) == 1
        assert output["分钟K线"][0]["时间"] == "0930"

    def test_missing_symbol_arg_errors(self):
        """缺少 --symbol 参数时报错"""
        with patch.object(sys, "argv", ["fetch_realtime.py", "quote"]):
            with pytest.raises(SystemExit) as exc_info:
                fetch_realtime.main()
        assert exc_info.value.code != 0

    def test_quote_api_failure_returns_empty(self):
        """API 完全失败时输出空结构但不崩溃"""
        with patch.object(urllib.request, "urlopen", side_effect=OSError("down")):
            test_args = ["fetch_realtime.py", "quote", "--symbol", "600183"]
            with patch.object(sys, "argv", test_args):
                stdout = io.StringIO()
                with patch.object(sys, "stdout", stdout):
                    fetch_realtime.main()

        output = json.loads(stdout.getvalue())
        assert output["股票代码"] == "600183"
        # API 失败返回空字段
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd akshare-real-time-quotes && python -m pytest scripts/tests/test_cli.py -v
```
预期：大部分 FAIL（CLI 尚未实现）

- [ ] **步骤 3：Commit**

```bash
git add akshare-real-time-quotes/scripts/tests/test_cli.py
git commit -m "test: add CLI integration tests with mocked HTTP"
```

---

### 任务 7：实现 CLI (argparse subparsers + main)

**文件：**
- 修改：`akshare-real-time-quotes/scripts/fetch_realtime.py` — 在现有两个数据函数后追加 CLI 部分

- [ ] **步骤 1：编写 CLI 实现**

在 `fetch_realtime.py` 末尾追加以下代码：

```python
def _validate_symbol(symbol: str) -> str:
    """校验股票代码为 6 位纯数字。

    Args:
        symbol: 股票代码字符串

    Returns:
        str: 校验通过的代码

    Raises:
        SystemExit: 格式非法时 exit(2)
    """
    if not symbol.isdigit() or len(symbol) != 6:
        print(
            f"[ERROR] 股票代码格式非法: {symbol}，应为6位纯数字",
            file=sys.stderr,
        )
        sys.exit(2)
    return symbol


def _write_output(data: dict, output_path: str | None) -> None:
    """将 dict 序列化为 JSON 输出到 stdout 或文件。

    Args:
        data: 要输出的数据
        output_path: 为 None 输出到 stdout，否则写入文件
    """
    json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_str)
                f.write("\n")
        except Exception as e:
            print(f"[ERROR] 写入输出文件失败: {e}", file=sys.stderr)
            sys.stdout.write(json_str)
            sys.stdout.write("\n")
    else:
        sys.stdout.write(json_str)
        sys.stdout.write("\n")
    sys.stdout.flush()


def cmd_quote(args: argparse.Namespace) -> int:
    """quote 子命令：获取实时行情快照（含盘口）。"""
    symbol = _validate_symbol(args.symbol)
    result = fetch_tencent_quote_verbose(symbol)
    if not result:
        result = {"股票代码": symbol, "股票名称": "", "行情更新时间": "",
                   "行情数据": {}, "成交数据": {}, "盘口数据": {}, "估值数据": {}}
    _write_output(result, args.output)
    return 0 if result.get("行情数据") else 1


def cmd_intraday(args: argparse.Namespace) -> int:
    """intraday 子命令：获取日内分钟K线。"""
    symbol = _validate_symbol(args.symbol)
    result = fetch_intraday_minute(symbol)
    if not result:
        result = {"股票代码": symbol, "股票名称": "", "交易日期": "",
                   "分钟K线": []}
    _write_output(result, args.output)
    return 0 if result.get("分钟K线") is not None else 1


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="获取A股实时行情与日内分钟K线数据",
    )
    subparsers = parser.add_subparsers(dest="command")

    p_quote = subparsers.add_parser("quote", help="获取实时行情快照（含盘口）")
    p_quote.add_argument("--symbol", required=True, help="股票代码，纯数字，如 600183")
    p_quote.add_argument("--output", default=None, help="输出 JSON 文件路径，默认 stdout")
    p_quote.set_defaults(func=cmd_quote)

    p_intraday = subparsers.add_parser("intraday", help="获取日内分钟K线")
    p_intraday.add_argument("--symbol", required=True, help="股票代码，纯数字，如 600183")
    p_intraday.add_argument("--output", default=None, help="输出 JSON 文件路径，默认 stdout")
    p_intraday.set_defaults(func=cmd_intraday)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(2)
    return args


def main() -> None:
    """CLI 入口。"""
    args = parse_args()
    exit_code = args.func(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
```

- [ ] **步骤 2：运行所有单元测试**

```bash
cd akshare-real-time-quotes && python -m pytest scripts/tests/ -v
```
预期：全部 PASS

- [ ] **步骤 3：Commit**

```bash
git add akshare-real-time-quotes/scripts/fetch_realtime.py
git commit -m "feat: add CLI with quote and intraday subcommands"
```

---

### 任务 8：创建 SKILL.md

**文件：**
- 创建：`akshare-real-time-quotes/SKILL.md`

- [ ] **步骤 1：创建 SKILL.md**

```markdown
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
```

- [ ] **步骤 2：Commit**

```bash
git add akshare-real-time-quotes/SKILL.md
git commit -m "docs: add SKILL.md for akshare-real-time-quotes"
```

---

### 任务 9：编写集成测试（真实网络）

**文件：**
- 创建：`akshare-real-time-quotes/scripts/tests/test_integration.py`

- [ ] **步骤 1：编写集成测试**

```python
"""集成测试 — 需要真实网络，标记为 integration"""
import json
import os
import subprocess
import sys
import pytest


SCRIPT = os.path.join(os.path.dirname(__file__), "..", "fetch_realtime.py")


@pytest.mark.integration
class TestQuoteIntegration:
    """真实网络 quote 子命令集成测试"""

    def test_quote_shanghai_stock(self):
        """上海股票 600183 实时行情"""
        result = subprocess.run(
            [sys.executable, SCRIPT, "quote", "--symbol", "600183"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["股票代码"] == "600183"
        assert data["股票名称"] != ""
        assert "行情数据" in data
        assert "当前价格(元)" in data["行情数据"]
        assert "盘口数据" in data
        # 盘口至少有委差字段
        assert "委差" in data["盘口数据"]

    def test_quote_shenzhen_stock(self):
        """深圳股票 000001 实时行情"""
        result = subprocess.run(
            [sys.executable, SCRIPT, "quote", "--symbol", "000001"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["股票代码"] == "000001"
        assert "行情数据" in data
        assert "成交数据" in data
        assert "盘口数据" in data
        assert "估值数据" in data
        # 数据类型检查
        assert isinstance(data["行情数据"]["当前价格(元)"], (int, float))

    def test_invalid_symbol_rejected(self):
        """非法代码被拒绝"""
        result = subprocess.run(
            [sys.executable, SCRIPT, "quote", "--symbol", "abc"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 2


@pytest.mark.integration
class TestIntradayIntegration:
    """真实网络 intraday 子命令集成测试"""

    def test_intraday_returns_minute_data(self):
        """上海股票日内分钟K线"""
        result = subprocess.run(
            [sys.executable, SCRIPT, "intraday", "--symbol", "600183"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["股票代码"] == "600183"
        assert data["股票名称"] != ""
        assert len(data["交易日期"]) == 8  # YYYYMMDD
        assert isinstance(data["分钟K线"], list)
        if data["分钟K线"]:
            minute = data["分钟K线"][0]
            assert len(minute["时间"]) == 4  # HHmm
            assert isinstance(minute["价格(元)"], (int, float))
            assert isinstance(minute["成交量"], int)
            assert isinstance(minute["成交额(元)"], (int, float))
```

- [ ] **步骤 2：运行集成测试**

```bash
cd akshare-real-time-quotes && python -m pytest scripts/tests/test_integration.py -v -m integration
```
预期：PASS（需要网络连接）

- [ ] **步骤 3：Commit**

```bash
git add akshare-real-time-quotes/scripts/tests/test_integration.py
git commit -m "test: add real-network integration tests"
```

---

### 任务 10：最终验证

**文件：** 无新建，运行全量验证

- [ ] **步骤 1：运行全部单元测试**

```bash
cd akshare-real-time-quotes && python -m pytest scripts/tests/test_fetch_realtime_quote.py scripts/tests/test_fetch_realtime_intraday.py scripts/tests/test_cli.py -v
```
预期：全部 PASS

- [ ] **步骤 2：验证 help 输出正常**

```bash
cd akshare-real-time-quotes && python scripts/fetch_realtime.py --help
```
预期：显示两个子命令（quote, intraday）的帮助信息

- [ ] **步骤 3：验证 quote 子命令帮助**

```bash
cd akshare-real-time-quotes && python scripts/fetch_realtime.py quote --help
```
预期：显示 `--symbol` 和 `--output` 参数说明

- [ ] **步骤 4：真实验证行情 API（需要网络）**

```bash
cd akshare-real-time-quotes && python scripts/fetch_realtime.py quote --symbol 600183 | python3 -m json.tool | head -40
```
预期：输出格式正确的实时行情 JSON

- [ ] **步骤 5：真实验证分钟K线 API（需要网络）**

```bash
cd akshare-real-time-quotes && python scripts/fetch_realtime.py intraday --symbol 600183 | python3 -m json.tool | head -30
```
预期：输出格式正确的分钟K线 JSON，包含交易日期和分钟数据数组

- [ ] **步骤 6：最终 commit**

```bash
git add -A
git commit -m "chore: final lint and verification pass"
```
