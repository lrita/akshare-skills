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
import re

import akshare as ak


# ---- 指数基金过滤 ----

def is_index_fund(name: str) -> bool:
    """判断基金简称是否为指数/ETF/联接/增强型基金

    规则:
    1. 数字+ETF (数字和ETF之间可能有其他字符)
    2. ETF和联接同时出现 (ETF和联接之间可能有其他字符)
    3. 含"指数"
    4. 含"增强"

    参数:
        name: 基金简称

    返回:
        bool: 应排除返回 True
    """
    # 规则 1: 数字+ETF (数字和ETF之间可能有其他字符)
    if re.search(r'\d.*ETF', name):
        return True
    # 规则 2: ETF和联接同时出现
    if 'ETF' in name and '联接' in name:
        return True
    # 规则 3: 含"指数"
    if '指数' in name:
        return True
    # 规则 4: 含"增强"
    if '增强' in name:
        return True
    return False


def filter_index_funds(funds: list[dict], exclude_index: bool = True) -> list[dict]:
    """过滤指数/ETF/联接/增强型基金

    参数:
        funds: 基金列表
        exclude_index: 是否启用过滤，默认 True

    返回:
        list[dict]: 过滤后的基金列表
    """
    if not exclude_index:
        return funds
    return [f for f in funds if not is_index_fund(f["基金简称"])]


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
        fetch_dt = datetime.strptime(fetch_time_str, "%Y-%m-%d %H:%M:%S")
        # 使用传入的 today 参数计算 age，支持测试固定日期
        ref_time = datetime.combine(today, datetime.now().time())
        age_seconds = (ref_time - fetch_dt).total_seconds()
        return age_seconds < ttl_hours * 3600
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


def fetch_fund_list(
    fund_types: list[str],
    min_scale_yi: float = 10.0,
    exclude_index: bool = True,
) -> list[dict]:
    """拉取基金列表，去重，按规模过滤

    参数:
        fund_types: 基金类型列表，如 ["股票型基金", "混合型基金"]
        min_scale_yi: 最低总募集规模（亿元），默认 10
        exclude_index: 是否排除指数/ETF/联接/增强基金，默认 True

    返回:
        list[dict]: 过滤后的基金列表，每个元素含基金代码和规模信息
    """
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

    funds = filter_index_funds(funds, exclude_index)
    return funds


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
            target_labels = [q for q, _ in target_quarters]
            if quarter not in target_labels:
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
            top_stocks: TopN 股票列表，按最新季度持仓金额降序
            quarterly_trend: {股票代码: {季度: {amount, fund_count}}}
    """
    stock_agg: dict[str, dict] = {}
    quarterly: dict[str, dict] = {}

    # 确定最新季度（用于排序）
    all_quarters: set[str] = set()
    for holdings in all_holdings.values():
        for info in holdings.values():
            all_quarters.update(info.get("quarters", {}).keys())
    latest_quarter = max(all_quarters) if all_quarters else ""

    for fund_code, holdings in all_holdings.items():
        for stock_code, info in holdings.items():
            if stock_code not in stock_agg:
                stock_agg[stock_code] = {
                    "latest_amount": 0.0,
                    "fund_count": 0,
                    "stock_name": info["stock_name"],
                }
                quarterly[stock_code] = {}
            stock_agg[stock_code]["fund_count"] += 1

            for q, amt in info.get("quarters", {}).items():
                if q == latest_quarter:
                    stock_agg[stock_code]["latest_amount"] += amt

                if q not in quarterly[stock_code]:
                    quarterly[stock_code][q] = {"amount": 0.0, "fund_count": 0}
                quarterly[stock_code][q]["amount"] += amt
                quarterly[stock_code][q]["fund_count"] += 1

    sorted_stocks = sorted(
        stock_agg.items(),
        key=lambda x: x[1]["latest_amount"],
        reverse=True,
    )
    top = sorted_stocks[:top_n]

    top_stocks = [
        {
            "rank": i + 1,
            "stock_code": code,
            "stock_name": info["stock_name"],
            "latest_holding_amount": info["latest_amount"],
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


# ---- 主流程 ----

def _run_holdings_pipeline(
    funds: list[dict],
    target_quarters: list[tuple[str, str]],
    max_workers: int,
    cache_dir: Path,
) -> tuple[dict[str, dict], list[dict]]:
    """并发拉取所有基金持仓数据"""
    all_holdings: dict[str, dict] = {}
    errors: list[dict] = []

    # 加载之前的失败记录
    failures_path = cache_dir / "failures.json"
    prev_failures = load_cache(failures_path) or {}

    # 将之前失败的基金也加入拉取队列
    failed_codes = set(prev_failures.keys())
    if failed_codes:
        print(f"Retrying {len(failed_codes)} previously failed funds...", file=sys.stderr)

    # 合并待拉取的基金列表
    all_codes_to_fetch = list(funds)
    for fc in failed_codes:
        if fc not in {f["基金代码"] for f in funds}:
            all_codes_to_fetch.append({"基金代码": fc, "基金简称": fc, "总募集规模": 0, "单位净值": 0})

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

        def _fetch_one(fund):
            code = fund["基金代码"]
            result = fetch_fund_holdings(code, target_quarters)
            if result is not None:
                cache_path = holdings_cache_dir / f"{code}.json"
                save_cache(cache_path, {
                    "fetch_time": _now_str(),
                    "quarters": [q for q, _ in target_quarters],
                    "holdings": result,
                })
                return code, result, None
            else:
                return code, None, "failed_after_retries"

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_one, f): f for f in to_fetch}
            for future in as_completed(futures):
                code, result, error = future.result()
                if result is not None:
                    all_holdings[code] = result
                    prev_failures.pop(code, None)
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
    """主流程：基金列表 → 持仓拉取 → 聚合 → 输出"""
    fund_types = [t.strip() for t in args.fund_types.split(",")]
    min_scale_yi = float(args.min_scale)
    exclude_index = args.exclude_index

    cache_dir = CACHE_BASE
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 尝试从缓存加载基金列表
    fund_list_cache = cache_dir / "fund_list.json"
    funds = None
    if is_cache_valid(fund_list_cache, ttl_hours=168, today=date.today()):
        cached = load_cache(fund_list_cache)
        if cached and "funds" in cached:
            cached_types = set(cached.get("fund_types", []))
            cached_min_yi = cached.get("min_scale_yi", 0)
            if cached_types == set(fund_types) and cached_min_yi <= min_scale_yi:
                all_cached = cached["funds"]
                funds = [f for f in all_cached if f["总募集规模"] >= min_scale_yi * 10000]

    if funds is None:
        try:
            all_funds = fetch_fund_list(fund_types, min_scale_yi, exclude_index)
        except Exception as e:
            print(f"FATAL: Failed to fetch fund list: {e}", file=sys.stderr)
            return 2
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

    target_quarters = infer_target_quarters(date.today())
    quarter_labels = [q for q, _ in target_quarters]

    total_funds = len(funds)
    all_holdings, errors = _run_holdings_pipeline(
        funds, target_quarters, args.workers, cache_dir
    )

    top_stocks, quarterly = aggregate_holdings(all_holdings, args.top_n)

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
    parser.add_argument(
        "--no-exclude-index", dest="exclude_index", action="store_false",
        help="不过滤指数/ETF/联接/增强基金",
    )

    args = parser.parse_args()
    exit_code = main_with_args(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
