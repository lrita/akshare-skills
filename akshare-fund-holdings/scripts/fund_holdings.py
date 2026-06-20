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
