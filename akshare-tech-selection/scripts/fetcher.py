#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
技术指标选股 — 数据获取层
直接 HTTP 请求 20 个技术选股 API，统一列名标准化和代码格式
"""
import os
import sys
import re
import time
from io import StringIO

import pandas as pd
import numpy as np
import requests
import py_mini_racer
from bs4 import BeautifulSoup

from akshare.datasets import get_ths_js


# ---- 常量 ----

ALL_INDICATORS = [
    # 第 1 类：同花顺技术指标 (11 个)
    {
        "name": "fetch_cxg_ths",
        "api": "stock_rank_cxg_ths",
        "category": "创新高",
        "categories": ["同花顺技术指标", "趋势类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": True,
        "default_symbol": "创月新高",
        "needs_date": False,
    },
    {
        "name": "fetch_cxd_ths",
        "api": "stock_rank_cxd_ths",
        "category": "创新低",
        "categories": ["同花顺技术指标", "趋势类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": True,
        "default_symbol": "创月新低",
        "needs_date": False,
    },
    {
        "name": "fetch_lxsz_ths",
        "api": "stock_rank_lxsz_ths",
        "category": "连续上涨",
        "categories": ["同花顺技术指标", "趋势类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_lxxd_ths",
        "api": "stock_rank_lxxd_ths",
        "category": "连续下跌",
        "categories": ["同花顺技术指标", "趋势类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_cxfl_ths",
        "api": "stock_rank_cxfl_ths",
        "category": "持续放量",
        "categories": ["同花顺技术指标", "量价类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_cxsl_ths",
        "api": "stock_rank_cxsl_ths",
        "category": "持续缩量",
        "categories": ["同花顺技术指标", "量价类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_xstp_ths",
        "api": "stock_rank_xstp_ths",
        "category": "向上突破",
        "categories": ["同花顺技术指标", "突破类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": True,
        "default_symbol": "500日均线",
        "needs_date": False,
    },
    {
        "name": "fetch_xxtp_ths",
        "api": "stock_rank_xxtp_ths",
        "category": "向下突破",
        "categories": ["同花顺技术指标", "突破类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": True,
        "default_symbol": "500日均线",
        "needs_date": False,
    },
    {
        "name": "fetch_ljqs_ths",
        "api": "stock_rank_ljqs_ths",
        "category": "量价齐升",
        "categories": ["同花顺技术指标", "量价类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_ljqd_ths",
        "api": "stock_rank_ljqd_ths",
        "category": "量价齐跌",
        "categories": ["同花顺技术指标", "量价类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_xzjp_ths",
        "api": "stock_rank_xzjp_ths",
        "category": "险资举牌",
        "categories": ["同花顺技术指标", "资金类"],
        "code_col": "股票代码",
        "name_col": "股票简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    # 第 2 类：巨潮资讯 (1 个)
    {
        "name": "fetch_forecast_cninfo",
        "api": "stock_rank_forecast_cninfo",
        "category": "机构评级",
        "categories": ["同花顺技术指标", "评级类"],
        "code_col": "证券代码",
        "name_col": "证券简称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    # 第 3 类：涨停板分析 (6 个)
    {
        "name": "fetch_zt_pool_strong",
        "api": "stock_zt_pool_strong_em",
        "category": "强势涨停",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    {
        "name": "fetch_zt_pool",
        "api": "stock_zt_pool_em",
        "category": "涨停池",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    {
        "name": "fetch_zt_pool_dtgc",
        "api": "stock_zt_pool_dtgc_em",
        "category": "跌停股池",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    {
        "name": "fetch_zt_pool_sub_new",
        "api": "stock_zt_pool_sub_new_em",
        "category": "次新股池",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    {
        "name": "fetch_zt_pool_previous",
        "api": "stock_zt_pool_previous_em",
        "category": "昨日涨停表现",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    {
        "name": "fetch_zt_pool_zbgc",
        "api": "stock_zt_pool_zbgc_em",
        "category": "炸板股池",
        "categories": ["涨停板分析"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": True,
    },
    # 第 4 类：异动监控 (2 个)
    {
        "name": "fetch_board_change",
        "api": "stock_board_change_em",
        "category": "板块异动",
        "categories": ["异动监控"],
        "code_col": "板块异动最频繁个股及所属类型-股票代码",
        "name_col": "板块异动最频繁个股及所属类型-股票名称",
        "needs_symbol": False,
        "default_symbol": None,
        "needs_date": False,
    },
    {
        "name": "fetch_changes",
        "api": "stock_changes_em",
        "category": "个股异动",
        "categories": ["异动监控"],
        "code_col": "代码",
        "name_col": "名称",
        "needs_symbol": True,
        "default_symbol": "大笔买入",
        "needs_date": False,
    },
]

# 按名称快速查找
INDICATOR_MAP = {ind["name"]: ind for ind in ALL_INDICATORS}

# 导出列表（20 个 fetcher 函数名，由后续任务填充实现）
__all__ = [ind["name"] for ind in ALL_INDICATORS]


# ---- 同花顺 JS 解密 ----

def _get_file_content_ths(file: str = "ths.js") -> str:
    """获取同花顺 JS 文件内容"""
    setting_file_path = get_ths_js(file)
    with open(setting_file_path, encoding="utf-8") as f:
        file_data = f.read()
    return file_data


# ---- 反爬检测 ----

def _check_thx_blocked(response: requests.Response, api_name: str) -> None:
    """
    检测同花顺/巨潮 API 是否被反爬拦截。
    命中则输出 AI 可读提示并 os._exit(1)。
    """
    if response.status_code == 403:
        print(
            f"[BLOCKED] {api_name}: HTTP 403 Forbidden — "
            f"被反爬虫系统拦截，请等待 1 小时后重试",
            file=sys.stderr,
        )
        os._exit(1)
    # 部分情况返回 200 但内容是验证页面
    text_lower = response.text.lower()
    block_signals = ["验证", "滑块", "captcha", "请在下方输入"]
    if any(s in text_lower for s in block_signals) or len(response.text.strip()) < 200:
        print(
            f"[BLOCKED] {api_name}: 返回异常页面 — "
            f"被反爬虫系统拦截，请等待 1 小时后重试",
            file=sys.stderr,
        )
        os._exit(1)


# ---- 工具函数 ----

def normalize_stock_code(code: str | None) -> str | None:
    """标准化股票代码：去除 SZ/SH/BJ 等前缀，补零到 6 位"""
    if code is None:
        return None
    code = str(code).strip().upper()
    if code == "":
        return ""
    for prefix in ("SZ", "SH", "BJ"):
        if code.startswith(prefix):
            code = code[len(prefix):]
    code = code.zfill(6)
    return code


def _nan_to_none(obj):
    """递归将 NaN 转为 None（用于 JSON 序列化）"""
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _nan_to_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_nan_to_none(v) for v in obj]
    return obj


def standardize_output(
    df: pd.DataFrame | None,
    code_col: str,
    name_col: str,
    indicator: str,
    category: str,
    categories: list[str],
) -> dict | None:
    """将 DataFrame 转为标准化 dict。"""
    if df is None or df.empty:
        return None
    df = df.copy()
    df = df.where(df.notna(), None)
    records = df.to_dict(orient="records")
    for record in records:
        if code_col in record:
            record["stock_code"] = normalize_stock_code(record.get(code_col))
        else:
            record["stock_code"] = None
        record["stock_name"] = record.get(name_col)
    records = _nan_to_none(records)
    return {
        "indicator": indicator,
        "category": category,
        "categories": categories,
        "count": len(records),
        "data": records,
    }


# ---- 20 个 Fetcher 函数 ----
# （以下由后续任务填充）
