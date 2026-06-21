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
