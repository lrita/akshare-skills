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

try:
    import akshare as ak
except ImportError:
    ak = None

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
        self._call_times = [t for t in self._call_times if now - t < self.window_seconds]
        if len(self._call_times) >= self.max_calls:
            wait = self._call_times[0] + self.window_seconds - now + 0.1
            if wait > 0:
                time.sleep(wait)
            self._call_times = [t for t in self._call_times if time.time() - t < self.window_seconds]
        time.sleep(random.uniform(0.3, 1.0))
        self._call_times.append(time.time())


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
    if ak is None:
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
