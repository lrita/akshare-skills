#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
技术指标选股 — 引擎层
实现 4 种工作模式：single / intersect / scan / full
"""
import time
import random
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import fetcher


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


def _call_fetchers_concurrent(
    ind_names: list[str],
    symbols: dict[str, str] | None = None,
    date: str | None = None,
    max_workers: int = 8,
):
    """并发调用多个 fetcher，返回 (results_dict, errors_list)"""
    if symbols is None:
        symbols = {}
    results = {}
    errors = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for ind_name in ind_names:
            sym = symbols.get(ind_name)
            time.sleep(random.uniform(0.1, 0.3))
            futures[executor.submit(_call_fetcher, ind_name, sym, date)] = ind_name

        for future in as_completed(futures):
            ind_name, result, error = future.result()
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
    max_workers: int = 8,
) -> dict:
    """多指标交集查询"""
    results, errors = _call_fetchers_concurrent(indicators, date=date, max_workers=max_workers)

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
            # Get stock_name from first indicator that has it
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
    max_workers: int = 8,
    signal_threshold: int = 1,
    top_n: int | None = None,
) -> dict:
    """全量扫描: 遍历 ALL_INDICATORS，按 stock_code 聚合信号"""
    ind_names = [ind["name"] for ind in fetcher.ALL_INDICATORS]
    results, errors = _call_fetchers_concurrent(ind_names, date=date, max_workers=max_workers)

    # 构建每个 indicator 的元信息
    ind_meta = {ind["name"]: ind for ind in fetcher.ALL_INDICATORS}

    # code -> {stock_name, signals: [...]}
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
            # 附上指标明细数据（除去 stock_code/stock_name）
            detail = {k: v for k, v in item.items() if k not in ("stock_code", "stock_name")}
            if detail:
                signal["detail"] = detail
            code_to_signals[code]["signals"].append(signal)

    # 按 signal_threshold 过滤，并按信号数降序排列
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

    # 构建 signal_summary
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
    max_workers: int = 8,
    signal_threshold: int = 1,
    top_n: int | None = None,
) -> dict:
    """全量扫描(详细版): 与 scan 类似，但 signal_summary 包含每个指标的详细健康状况"""
    ind_names = [ind["name"] for ind in fetcher.ALL_INDICATORS]
    results, errors = _call_fetchers_concurrent(ind_names, date=date, max_workers=max_workers)

    # 构建每个 indicator 的元信息
    ind_meta = {ind["name"]: ind for ind in fetcher.ALL_INDICATORS}

    # code -> {stock_name, signals: [...]}
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

    # 按 signal_threshold 过滤，并按信号数降序排列
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

    # 构建详细的 signal_summary（与 scan 不同，包含每个指标的 indicators 数组）
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
