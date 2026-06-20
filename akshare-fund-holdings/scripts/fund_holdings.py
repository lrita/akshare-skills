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
