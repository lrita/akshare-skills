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
