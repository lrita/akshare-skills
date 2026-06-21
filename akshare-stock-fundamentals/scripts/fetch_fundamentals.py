"""个股基本面数据获取工具。

用法:
    uv run python scripts/fetch_fundamentals.py --symbol 600183 [--date 20260621] [--output result.json]

输出结构化 JSON 到 stdout，包含 5 个板块的个股基本面数据。
所有字段使用中文命名并附带单位，NaN 值统一转换为 null。
"""
import argparse
import json
import math
import random
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta

try:
    import akshare as ak
except ImportError:
    ak = None

# 板块列表
SECTIONS = ["basic_info", "fundamentals", "risk_signals", "events", "institutional"]

# 每个板块依赖的数据源 (section -> list of source names)
SECTION_DEPENDENCIES = {
    "basic_info":    ["tencent_quote", "eastmoney_boards", "eastmoney_profile", "stock_add_stock"],
    "fundamentals":  ["financial_abstract_by_report", "financial_abstract_by_year",
                      "financial_benefit", "financial_debt", "financial_cash",
                      "profit_forecast_eps", "profit_forecast_net", "profit_forecast_inst",
                      "profit_forecast_detail", "revenue_structure"],
    "risk_signals":  ["block_trades", "restricted_release_em", "restricted_release_sina", "pledge"],
    "events":        ["notices"],
    "institutional": ["research_visits"],
}

# 同花顺财务 API 列名 → 中文映射
_FINANCIAL_COLUMN_MAP = {
    "report_date": "报告期",
    "report_name": "报表名称",
    "report_period": "报告周期",
    "quarter_name": "季度",
    "metric_name": "指标名称",
    "value": "数值",
    "single": "单季度",
    "yoy": "同比增长率(%)",
    "mom": "环比增长率(%)",
    "single_yoy": "单季度同比增长率(%)",
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


# ---------------------------------------------------------------------------
# 通用工具函数
# ---------------------------------------------------------------------------

def _nan_to_none(val):
    """将 NaN 转换为 None（用于 JSON 序列化）。"""
    if isinstance(val, float) and math.isnan(val):
        return None
    return val


def _records_nan_to_none(records: list[dict]) -> list[dict]:
    """对每条记录的所有值执行 NaN → None 转换。"""
    return [{k: _nan_to_none(v) for k, v in r.items()} for r in records]


def _safe_df_to_records(df, date_str: str = None, years: int = None,
                        column_map: dict = None) -> list[dict]:
    """DataFrame → dict 列表，支持年限过滤、NaN清理、列名映射。"""
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    records = _records_nan_to_none(records)

    if years is not None and date_str is not None:
        cutoff = datetime.strptime(date_str, "%Y%m%d") - timedelta(days=years * 365)
        filtered = []
        for r in records:
            date_val = (r.get("report_date", "")
                        or r.get("报告日期", "")
                        or r.get("报告期", "")
                        or r.get("日期", "")
                        or r.get("截止日期", ""))
            if not date_val:
                filtered.append(r)
                continue
            try:
                rd = datetime.strptime(str(date_val)[:10], "%Y-%m-%d")
                if rd >= cutoff:
                    filtered.append(r)
            except ValueError:
                filtered.append(r)
        records = filtered

    if column_map:
        records = [
            {column_map.get(k, k): v for k, v in r.items()}
            for r in records
        ]

    return records


def _make_secucode(code: str) -> str:
    """将 6 位股票代码转为东方财富 SECUCODE 格式，如 600183 → 600183.SH。"""
    if code.startswith("6"):
        return f"{code}.SH"
    elif code.startswith(("0", "3")):
        return f"{code}.SZ"
    elif code.startswith(("8", "4")):
        return f"{code}.BJ"
    else:
        return f"{code}.SZ"


def _http_get_json(url: str, timeout: int = 10) -> dict:
    """带模拟浏览器头的 HTTP GET，返回 JSON dict。失败返回 {}。"""
    try:
        req = urllib.request.Request(url)
        req.add_header("Referer", "https://emweb.securities.eastmoney.com/")
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# basic_info 数据源
# ---------------------------------------------------------------------------

def fetch_tencent_quote(code: str) -> dict:
    """从腾讯财经获取实时行情快照。

    Returns:
        dict，字段全部中文带单位，失败返回 {}。
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
                "股票名称":       vals[1],
                "当前价格(元)":    float(vals[3]) if vals[3] else 0,
                "昨收价(元)":      float(vals[4]) if vals[4] else 0,
                "今开价(元)":      float(vals[5]) if vals[5] else 0,
                "成交量(手)":      int(float(vals[6])) if vals[6] else 0,
                "外盘(手)":        int(float(vals[7])) if vals[7] else 0,
                "内盘(手)":        int(float(vals[8])) if vals[8] else 0,
                "涨跌额(元)":      float(vals[31]) if vals[31] else 0,
                "涨跌幅(%)":       float(vals[32]) if vals[32] else 0,
                "最高价(元)":      float(vals[33]) if vals[33] else 0,
                "最低价(元)":      float(vals[34]) if vals[34] else 0,
                "成交额(万元)":    float(vals[37]) if vals[37] else 0,
                "换手率(%)":       float(vals[38]) if vals[38] else 0,
                "滚动市盈率":      float(vals[39]) if vals[39] else 0,
                "振幅(%)":         float(vals[43]) if vals[43] else 0,
                "流通市值(亿)":    float(vals[44]) if vals[44] else 0,
                "总市值(亿)":      float(vals[45]) if vals[45] else 0,
                "市净率":          float(vals[46]) if vals[46] else 0,
                "涨停价(元)":      float(vals[47]) if vals[47] else 0,
                "跌停价(元)":      float(vals[48]) if vals[48] else 0,
                "量比":            float(vals[49]) if vals[49] else 0,
                "日内均价(元)":    float(vals[51]) if vals[51] else 0,
                "动态市盈率":      float(vals[52]) if vals[52] else 0,
                "行情更新时间":    vals[30],
            }
        except (ValueError, IndexError):
            return {}
    return {}


def fetch_eastmoney_boards(code: str) -> list[dict]:
    """从东方财富数据中心获取个股所属板块。

    API: RPT_F10_CORETHEME_BOARDTYPE
    参数: SECUCODE=<code>.SH/.SZ/.BJ, IS_PRECISE=1

    Returns:
        list[dict]，每条含 板块名称/入选理由/板块排名 等，
        返回精确匹配板块（IS_PRECISE=1），按 BOARD_RANK 升序。
    """
    secucode = _make_secucode(code)
    url = (
        "https://datacenter.eastmoney.com/securities/api/data/v1/get"
        "?reportName=RPT_F10_CORETHEME_BOARDTYPE"
        "&columns=SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,NEW_BOARD_CODE,BOARD_NAME,SELECTED_BOARD_REASON,IS_PRECISE,BOARD_RANK,BOARD_YIELD,DERIVE_BOARD_CODE"
        "&quoteColumns=f3~05~NEW_BOARD_CODE~BOARD_YIELD"
        f"&filter=(SECUCODE%3D%22{secucode}%22)(IS_PRECISE%3D%221%22)"
        "&pageNumber=1&pageSize=&sortTypes=1&sortColumns=BOARD_RANK&source=HSF10&client=PC"
    )
    data = _http_get_json(url)
    items = data.get("result", {}).get("data", [])
    if not items:
        return []
    # 保留中文关键字段
    result = []
    for item in items:
        result.append({
            "板块名称":       item.get("BOARD_NAME", ""),
            "板块代码":       item.get("NEW_BOARD_CODE", ""),
            "入选理由":       item.get("SELECTED_BOARD_REASON", ""),
            "板块排名":       item.get("BOARD_RANK"),
            "板块收益率":     item.get("BOARD_YIELD"),
        })
    return result


def fetch_eastmoney_profile(code: str) -> dict:
    """从东方财富数据中心获取公司档案（公司简介、主营业务、经营范围、行业背景等）。

    API: RPT_F10_CORETHEME_CONTENT
    参数: SECUCODE=<code>.SH/.SZ/.BJ, KEY_CLASSIF_CODE <> 001

    返回字段按 KEY_CLASSIF 分类：
    - 002: 经营范围
    - 003: 主营业务
    - 004: 行业背景（IS_POINT=1 的是要点）
    - 005: 核心竞争力
    - 006: 公司简介

    Returns:
        dict，失败返回 {}。
    """
    secucode = _make_secucode(code)
    # 获取全部内容条目（排除 KEY_CLASSIF_CODE=001 的不需要的类别）
    url = (
        "https://datacenter.eastmoney.com/securities/api/data/get"
        "?type=RPT_F10_CORETHEME_CONTENT"
        "&sty=SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,KEYWORD,MAINPOINT,MAINPOINT_CONTENT,KEY_CLASSIF,KEY_CLASSIF_CODE,IS_POINT,IS_HISTORY"
        "&quoteColumns="
        f"&filter=(SECUCODE%3D%22{secucode}%22)(KEY_CLASSIF_CODE%3C%3E%22001%22)"
        "&p=1&ps=&sr=1%2C1&st=KEY_CLASSIF_CODE%2CMAINPOINT&source=HSF10&client=PC"
    )
    data = _http_get_json(url)
    items = data.get("result", {}).get("data", [])
    if not items:
        return {}

    # 按 KEY_CLASSIF_CODE 提取各字段
    name = items[0].get("SECURITY_NAME_ABBR", "") if items else ""

    # 经营范围 (002)
    scope = _find_item_content(items, "002", "")
    # 主营业务 (003)
    main_biz = _find_item_content(items, "003", "")
    # 行业背景 (004)，IS_POINT=1 的是行业要点
    industry = _find_item_content(items, "004", "", is_point="1")
    # 核心竞争力 (005)
    competitive = _find_items_content(items, "005")
    # 其他可能有 006-公司简介等
    profile_text = _find_item_content(items, "006", "")

    return {
        "股票简称":   name,
        "公司简介":   profile_text,
        "主营业务":   main_biz,
        "经营范围":   scope,
        "行业背景":   industry,
        "核心竞争力": competitive,
    }


def _find_item_content(items: list[dict], classif_code: str, default: str = "",
                       is_point: str = None) -> str:
    """从 API 返回的 items 中查找 KEY_CLASSIF_CODE 匹配的第一条内容的 MAINPOINT_CONTENT。

    Args:
        items: API 返回的 data 列表
        classif_code: KEY_CLASSIF_CODE 值
        is_point: 如指定，则只匹配 IS_POINT 等于该值的条目
    """
    for item in items:
        code = str(item.get("KEY_CLASSIF_CODE", ""))
        if code != classif_code:
            continue
        if is_point is not None and str(item.get("IS_POINT", "")) != is_point:
            continue
        content = item.get("MAINPOINT_CONTENT", "")
        if content:
            return content
    return default


def _find_items_content(items: list[dict], classif_code: str) -> str:
    """从 API 返回的 items 中查找 KEY_CLASSIF_CODE 匹配的所有内容，合并起来。

    用于核心竞争力等 IS_POINT=1 的多条条目。
    """
    parts = []
    for item in items:
        code = str(item.get("KEY_CLASSIF_CODE", ""))
        if code != classif_code:
            continue
        if str(item.get("IS_POINT", "")) != "1":
            continue
        content = item.get("MAINPOINT_CONTENT", "")
        if content:
            parts.append(content)
    return "\n".join(parts)


def fetch_stock_add_stock(code: str, date_str: str) -> list[dict]:
    """获取增发记录，截取最近 2 年。"""
    if ak is None:
        return []
    try:
        df = ak.stock_add_stock(symbol=code)
        if df is None or df.empty:
            return []
        records = df.to_dict(orient="records")
        records = _records_nan_to_none(records)
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


# ---------------------------------------------------------------------------
# fundamentals 数据源
# ---------------------------------------------------------------------------

def fetch_financial_abstract(code: str, indicator: str, date_str: str = None) -> list[dict]:
    """获取财务摘要（同花顺 new_ths 接口）。"""
    if ak is None:
        return []
    try:
        df = ak.stock_financial_abstract_new_ths(symbol=code, indicator=indicator)
    except Exception:
        return []
    return _safe_df_to_records(df, date_str, years=5, column_map=_FINANCIAL_COLUMN_MAP)


def fetch_financial_profit(code: str, date_str: str) -> list[dict]:
    """获取利润表（按报告期，最近 5 年）。"""
    if ak is None:
        return []
    try:
        df = ak.stock_financial_benefit_new_ths(symbol=code, indicator="按报告期")
    except Exception:
        return []
    return _safe_df_to_records(df, date_str, years=5, column_map=_FINANCIAL_COLUMN_MAP)


def fetch_financial_debt(code: str, date_str: str) -> list[dict]:
    """获取资产负债表（按报告期，最近 5 年）。"""
    if ak is None:
        return []
    try:
        df = ak.stock_financial_debt_new_ths(symbol=code, indicator="按报告期")
    except Exception:
        return []
    return _safe_df_to_records(df, date_str, years=5, column_map=_FINANCIAL_COLUMN_MAP)


def fetch_financial_cashflow(code: str, date_str: str) -> list[dict]:
    """获取现金流量表（按报告期，最近 5 年）。"""
    if ak is None:
        return []
    try:
        df = ak.stock_financial_cash_new_ths(symbol=code, indicator="按报告期")
    except Exception:
        return []
    return _safe_df_to_records(df, date_str, years=5, column_map=_FINANCIAL_COLUMN_MAP)


def _fetch_profit_forecast(code: str, indicator: str) -> list[dict]:
    """内部函数：获取盈利预测数据。"""
    if ak is None:
        return []
    try:
        df = ak.stock_profit_forecast_ths(symbol=code, indicator=indicator)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    return _records_nan_to_none(records)


def fetch_profit_forecast_eps(code: str) -> list[dict]:
    return _fetch_profit_forecast(code, "预测年报每股收益")


def fetch_profit_forecast_net(code: str) -> list[dict]:
    return _fetch_profit_forecast(code, "预测年报净利润")


def fetch_profit_forecast_inst(code: str) -> list[dict]:
    return _fetch_profit_forecast(code, "业绩预测详表-机构")


def fetch_profit_forecast_detail(code: str) -> list[dict]:
    return _fetch_profit_forecast(code, "业绩预测详表-详细指标预测")


def fetch_revenue_structure(code: str, date_str: str) -> list[dict]:
    """获取主营构成（东方财富），截取最近 3 年。"""
    if code.startswith("6"):
        prefixed = f"SH{code}"
    elif code.startswith("0") or code.startswith("3"):
        prefixed = f"SZ{code}"
    elif code.startswith(("8", "4")):
        prefixed = f"BJ{code}"
    else:
        prefixed = f"SH{code}"
    if ak is None:
        return []
    try:
        df = ak.stock_zygc_em(symbol=prefixed)
    except Exception:
        return []
    return _safe_df_to_records(df, date_str, years=3)


# ---------------------------------------------------------------------------
# risk_signals 数据源
# ---------------------------------------------------------------------------

def _filter_by_date_cutoff(records: list[dict], date_str: str, date_key: str,
                           years: int) -> list[dict]:
    """按日期截取最近 N 年记录，保留无日期和解析失败的记录。"""
    cutoff = datetime.strptime(date_str, "%Y%m%d") - timedelta(days=years * 365)
    filtered = []
    for r in records:
        date_val = r.get(date_key, "")
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


def fetch_block_trades(code: str, date_str: str) -> list[dict]:
    """获取近 30 日大宗交易明细，按股票代码过滤。"""
    if ak is None:
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
    records = _records_nan_to_none(records)
    return [r for r in records if str(r.get("股票代码", "")) == code]


def fetch_restricted_release_em(code: str, date_str: str) -> list[dict]:
    """从东财获取限售解禁数据，保留近 2 年 + 未执行计划。"""
    if ak is None:
        return []
    try:
        df = ak.stock_restricted_release_queue_em(symbol=code)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    records = _records_nan_to_none(records)
    return _filter_by_date_cutoff(records, date_str, "解禁日期", years=2)


def fetch_restricted_release_sina(code: str, date_str: str) -> list[dict]:
    """从新浪获取限售解禁数据，保留近 2 年 + 未执行计划。"""
    if ak is None:
        return []
    try:
        df = ak.stock_restricted_release_queue_sina(symbol=code)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    records = _records_nan_to_none(records)
    return _filter_by_date_cutoff(records, date_str, "解禁日期", years=2)


def fetch_pledge(code: str) -> list[dict]:
    """获取股权质押明细，仅保留"未解押"状态。"""
    if ak is None:
        return []
    try:
        df = ak.stock_gpzy_individual_pledge_ratio_detail_em(symbol=code)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    records = _records_nan_to_none(records)
    return [r for r in records if r.get("质押状态", "") == "未解押"]


# ---------------------------------------------------------------------------
# events 数据源
# ---------------------------------------------------------------------------

def fetch_notices(code: str, date_str: str) -> list[dict]:
    """获取个股公告（近 90 日，全部类型）。"""
    if ak is None:
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
    records = df.to_dict(orient="records")
    return _records_nan_to_none(records)


# ---------------------------------------------------------------------------
# institutional 数据源
# ---------------------------------------------------------------------------

def fetch_research_visits(code: str, date_str: str) -> list[dict]:
    """获取近 30 日机构调研记录，按股票代码/名称过滤。"""
    if ak is None:
        return []
    end_date = datetime.strptime(date_str, "%Y%m%d")
    start_date = end_date - timedelta(days=30)
    all_results = []
    seen = set()
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
            records = _records_nan_to_none(records)
            for r in records:
                if (str(r.get("股票代码", "")) == code
                        or str(r.get("股票名称", "")) == code):
                    key = (str(r.get("股票代码", "")), str(r.get("日期", "")))
                    if key not in seen:
                        seen.add(key)
                        all_results.append(r)
        current += timedelta(days=1)
    return all_results


# ---------------------------------------------------------------------------
# CLI 参数解析
# ---------------------------------------------------------------------------

def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="获取A股个股基本面数据，输出结构化JSON",
    )
    parser.add_argument("--symbol", required=True, help="股票代码，纯数字，如 600183")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"),
                        help="基准日期 YYYYMMDD，默认今天")
    parser.add_argument("--output", default=None, help="输出 JSON 文件路径，默认 stdout")
    args = parser.parse_args()
    if not args.symbol.isdigit() or len(args.symbol) != 6:
        print(f"[ERROR] 股票代码格式非法: {args.symbol}，应为6位纯数字", file=sys.stderr)
        sys.exit(2)
    return args


# ---------------------------------------------------------------------------
# 板块编排
# ---------------------------------------------------------------------------

def _build_period(date_str: str, days_back: int) -> dict:
    end = datetime.strptime(date_str, "%Y%m%d")
    start = end - timedelta(days=days_back)
    return {"起始日期": start.strftime("%Y%m%d"), "截止日期": end.strftime("%Y%m%d")}


def fetch_all_sections(symbol: str, date_str: str, limiter):
    """按板块顺序拉取所有数据源，组装 sections dict。返回 (sections, errors)。"""
    errors = []
    sections = {}

    # ---- 基础信息 ----
    bi = {}
    bi_success = 0
    limiter.acquire()
    try:
        bi["实时行情"] = fetch_tencent_quote(symbol)
        bi_success += 1
    except Exception as e:
        errors.append({"板块": "基础信息", "数据源": "tencent_quote", "错误": str(e)})
        bi["实时行情"] = None
    limiter.acquire()
    try:
        bi["所属板块"] = fetch_eastmoney_boards(symbol)
        bi_success += 1
    except Exception as e:
        errors.append({"板块": "基础信息", "数据源": "eastmoney_boards", "错误": str(e)})
        bi["所属板块"] = None
    limiter.acquire()
    try:
        bi["公司档案"] = fetch_eastmoney_profile(symbol)
        bi_success += 1
    except Exception as e:
        errors.append({"板块": "基础信息", "数据源": "eastmoney_profile", "错误": str(e)})
        bi["公司档案"] = None
    limiter.acquire()
    try:
        bi["增发记录"] = fetch_stock_add_stock(symbol, date_str)
        bi_success += 1
    except Exception as e:
        errors.append({"板块": "基础信息", "数据源": "stock_add_stock", "错误": str(e)})
        bi["增发记录"] = None
    sections["基础信息"] = bi if bi_success > 0 else None

    # ---- 财务基本面 ----
    fin_success = 0
    fundamentals = {"财务报表": {}, "盈利预测": {}, "主营构成": None}
    fin_calls = [
        ("by_report", fetch_financial_abstract,
         {"code": symbol, "indicator": "按报告期", "date_str": date_str}),
        ("by_year", fetch_financial_abstract,
         {"code": symbol, "indicator": "按年度", "date_str": date_str}),
        ("利润表", fetch_financial_profit, {"code": symbol, "date_str": date_str}),
        ("资产负债表", fetch_financial_debt, {"code": symbol, "date_str": date_str}),
        ("现金流量表", fetch_financial_cashflow, {"code": symbol, "date_str": date_str}),
    ]
    for name, fn, kwargs in fin_calls:
        limiter.acquire()
        try:
            fundamentals["财务报表"][name] = fn(**kwargs)
            fin_success += 1
        except Exception as e:
            errors.append({"板块": "财务基本面", "数据源": f"financial_{name}", "错误": str(e)})
            fundamentals["财务报表"][name] = None

    forecast_calls = [
        ("预测年报每股收益", fetch_profit_forecast_eps),
        ("预测年报净利润", fetch_profit_forecast_net),
        ("业绩预测详表_机构", fetch_profit_forecast_inst),
        ("业绩预测详表_详细指标", fetch_profit_forecast_detail),
    ]
    for name, fn in forecast_calls:
        limiter.acquire()
        try:
            fundamentals["盈利预测"][name] = fn(symbol)
            fin_success += 1
        except Exception as e:
            errors.append({"板块": "财务基本面", "数据源": f"profit_forecast_{name}", "错误": str(e)})
            fundamentals["盈利预测"][name] = None

    limiter.acquire()
    try:
        fundamentals["主营构成"] = fetch_revenue_structure(symbol, date_str)
        fin_success += 1
    except Exception as e:
        errors.append({"板块": "财务基本面", "数据源": "revenue_structure", "错误": str(e)})
        fundamentals["主营构成"] = None

    by_report = fundamentals["财务报表"].pop("by_report", None)
    by_year = fundamentals["财务报表"].pop("by_year", None)
    fundamentals["财务报表"]["财务摘要"] = {"按报告期": by_report, "按年度": by_year}
    sections["财务基本面"] = fundamentals if fin_success > 0 else None

    # ---- 风险信号 ----
    risk_signals = {}
    risk_success = 0
    risk_calls = [
        ("大宗交易", fetch_block_trades, {"code": symbol, "date_str": date_str}),
        ("限售解禁_东财", fetch_restricted_release_em, {"code": symbol, "date_str": date_str}),
        ("限售解禁_新浪", fetch_restricted_release_sina, {"code": symbol, "date_str": date_str}),
        ("股权质押", fetch_pledge, {"code": symbol}),
    ]
    for name, fn, kwargs in risk_calls:
        limiter.acquire()
        try:
            if name == "大宗交易":
                risk_signals[name] = {
                    "时间范围": _build_period(date_str, 30),
                    "数据": fn(**kwargs),
                }
            elif name == "股权质押":
                risk_signals[name] = {
                    "仅未解押": True,
                    "数据": fn(**kwargs),
                }
            else:
                risk_signals[name] = fn(**kwargs)
            risk_success += 1
        except Exception as e:
            errors.append({"板块": "风险信号", "数据源": name, "错误": str(e)})
            risk_signals[name] = None
    sections["风险信号"] = risk_signals if risk_success > 0 else None

    # ---- 重大事件 ----
    limiter.acquire()
    try:
        notices = fetch_notices(symbol, date_str)
        sections["重大事件"] = {
            "公告通知": {"时间范围": _build_period(date_str, 90), "数据": notices}
        }
    except Exception as e:
        errors.append({"板块": "重大事件", "数据源": "notices", "错误": str(e)})
        sections["重大事件"] = None

    # ---- 机构动向 ----
    limiter.acquire()
    try:
        visits = fetch_research_visits(symbol, date_str)
        sections["机构动向"] = {
            "机构调研": {"时间范围": _build_period(date_str, 30), "数据": visits}
        }
    except Exception as e:
        errors.append({"板块": "机构动向", "数据源": "research_visits", "错误": str(e)})
        sections["机构动向"] = None

    return sections, errors


# ---------------------------------------------------------------------------
# 输出构建
# ---------------------------------------------------------------------------

def build_output(symbol: str, sections: dict, errors: list, date_str: str) -> dict:
    """将 sections 和 errors 组装为最终输出 dict。"""
    stock_name = symbol
    bi = sections.get("基础信息", {}) or {}
    profile = bi.get("公司档案", {}) or {}
    if profile.get("股票简称"):
        stock_name = profile["股票简称"]

    return {
        "股票代码": symbol,
        "股票名称": stock_name,
        "数据获取时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "板块数据": sections,
        "错误信息": errors,
    }


def main() -> int:
    """CLI 入口。Returns exit code。"""
    args = parse_args()
    limiter = RateLimiter(max_calls=10, window_seconds=60)
    sections, errors = fetch_all_sections(args.symbol, args.date, limiter)
    any_successful = any(v is not None for v in sections.values())
    output = build_output(args.symbol, sections, errors, args.date)

    json_str = json.dumps(output, ensure_ascii=False, indent=2, default=str,
                          allow_nan=False)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
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
    return 0 if any_successful else 1


if __name__ == "__main__":
    sys.exit(main())
