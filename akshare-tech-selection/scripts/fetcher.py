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

# ======== 同花顺技术指标 (11 个) ========

def fetch_cxg_ths(symbol: str = "创月新高", date: str | None = None) -> dict | None:
    """创新高"""
    symbol_map = {"创月新高": "4", "半年新高": "3", "一年新高": "2", "历史新高": "1"}
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = f"http://data.10jqka.com.cn/rank/cxg/board/{symbol_map[symbol]}/field/stockcode/order/asc/page/1/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_cxg_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/cxg/board/{symbol_map[symbol]}/field/stockcode/order/asc/page/{page}/ajax/1/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_cxg_ths")
        html_fixed = re.sub(r'\srowspan="\d+"', '', r.text)
        temp_df = pd.read_html(StringIO(html_fixed), header=0)[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "涨跌幅", "换手率", "最新价", "前期高点", "前期高点日期"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].str.strip("%")
    big_df["换手率"] = big_df["换手率"].str.strip("%")
    big_df["前期高点日期"] = pd.to_datetime(big_df["前期高点日期"], errors="coerce").dt.date
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["前期高点"] = pd.to_numeric(big_df["前期高点"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_cxg_ths", "创新高", ["同花顺技术指标", "趋势类"])


def fetch_cxd_ths(symbol: str = "创月新低", date: str | None = None) -> dict | None:
    """创新低"""
    symbol_map = {"创月新低": "4", "半年新低": "3", "一年新低": "2", "历史新低": "1"}
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = f"http://data.10jqka.com.cn/rank/cxd/board/{symbol_map[symbol]}/field/stockcode/order/asc/page/1/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_cxd_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/cxd/board/{symbol_map[symbol]}/field/stockcode/order/asc/page/{page}/ajax/1/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_cxd_ths")
        temp_df = pd.read_html(StringIO(r.text))[0].iloc[:, :-1]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "涨跌幅", "换手率", "最新价", "前期低点", "前期低点日期"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].str.strip("%")
    big_df["换手率"] = big_df["换手率"].str.strip("%")
    big_df["前期低点日期"] = pd.to_datetime(big_df["前期低点日期"], errors="coerce").dt.date
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["前期低点"] = pd.to_numeric(big_df["前期低点"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_cxd_ths", "创新低", ["同花顺技术指标", "趋势类"])


def fetch_lxsz_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """连续上涨"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/lxsz/field/lxts/order/desc/page/1/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_lxsz_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/lxsz/field/lxts/order/desc/page/{page}/ajax/1/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_lxsz_ths")
        temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "收盘价", "最高价", "最低价", "连涨天数", "连续涨跌幅", "累计换手率", "所属行业"]
    big_df["连续涨跌幅"] = big_df["连续涨跌幅"].str.strip("%")
    big_df["累计换手率"] = big_df["累计换手率"].str.strip("%")
    big_df["连续涨跌幅"] = pd.to_numeric(big_df["连续涨跌幅"], errors="coerce")
    big_df["累计换手率"] = pd.to_numeric(big_df["累计换手率"], errors="coerce")
    big_df["收盘价"] = pd.to_numeric(big_df["收盘价"], errors="coerce")
    big_df["最高价"] = pd.to_numeric(big_df["最高价"], errors="coerce")
    big_df["最低价"] = pd.to_numeric(big_df["最低价"], errors="coerce")
    big_df["连涨天数"] = pd.to_numeric(big_df["连涨天数"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_lxsz_ths", "连续上涨", ["同花顺技术指标", "趋势类"])


def fetch_lxxd_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """连续下跌"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/lxxd/field/lxts/order/desc/page/1/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_lxxd_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/lxxd/field/lxts/order/desc/page/{page}/ajax/1/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_lxxd_ths")
        temp_df = pd.read_html(StringIO(r.text), converters={"股票代码": str})[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "收盘价", "最高价", "最低价", "连涨天数", "连续涨跌幅", "累计换手率", "所属行业"]
    big_df["连续涨跌幅"] = big_df["连续涨跌幅"].str.strip("%")
    big_df["累计换手率"] = big_df["累计换手率"].str.strip("%")
    big_df["连续涨跌幅"] = pd.to_numeric(big_df["连续涨跌幅"], errors="coerce")
    big_df["累计换手率"] = pd.to_numeric(big_df["累计换手率"], errors="coerce")
    big_df["收盘价"] = pd.to_numeric(big_df["收盘价"], errors="coerce")
    big_df["最高价"] = pd.to_numeric(big_df["最高价"], errors="coerce")
    big_df["最低价"] = pd.to_numeric(big_df["最低价"], errors="coerce")
    big_df["连涨天数"] = pd.to_numeric(big_df["连涨天数"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_lxxd_ths", "连续下跌", ["同花顺技术指标", "趋势类"])


def fetch_cxfl_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """持续放量"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/cxfl/field/count/order/desc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_cxfl_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/cxfl/field/count/order/desc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_cxfl_ths")
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='m-table J-ajax-table')
        data = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 10:
                    item = {
                        '序号': cols[0].text.strip(),
                        '股票代码': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                        '股票简称': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                        '涨跌幅': cols[3].text.strip(),
                        '最新价': cols[4].text.strip(),
                        '成交量': cols[5].text.strip(),
                        '基准日成交量': cols[6].text.strip(),
                        '放量天数': cols[7].text.strip(),
                        '阶段涨跌幅': cols[8].text.strip(),
                        '所属行业': cols[9].find('a').text.strip() if cols[9].find('a') else cols[9].text.strip(),
                    }
                    data.append(item)
        temp_df = pd.DataFrame(data)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "涨跌幅", "最新价", "成交量", "基准日成交量", "放量天数", "阶段涨跌幅", "所属行业"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.strip("%")
    big_df["阶段涨跌幅"] = big_df["阶段涨跌幅"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["阶段涨跌幅"] = pd.to_numeric(big_df["阶段涨跌幅"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["放量天数"] = pd.to_numeric(big_df["放量天数"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_cxfl_ths", "持续放量", ["同花顺技术指标", "量价类"])


def fetch_cxsl_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """持续缩量"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/cxsl/field/count/order/desc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_cxsl_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/cxsl/field/count/order/desc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_cxsl_ths")
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='m-table J-ajax-table')
        data = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 10:
                    item = {
                        '序号': cols[0].text.strip(),
                        '股票代码': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                        '股票简称': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                        '涨跌幅': cols[3].text.strip(),
                        '最新价': cols[4].text.strip(),
                        '成交量': cols[5].text.strip(),
                        '基准日成交量': cols[6].text.strip(),
                        '放量天数': cols[7].text.strip(),
                        '阶段涨跌幅': cols[8].text.strip(),
                        '所属行业': cols[9].find('a').text.strip() if cols[9].find('a') else cols[9].text.strip(),
                    }
                    data.append(item)
        temp_df = pd.DataFrame(data)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "涨跌幅", "最新价", "成交量", "基准日成交量", "缩量天数", "阶段涨跌幅", "所属行业"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.strip("%")
    big_df["阶段涨跌幅"] = big_df["阶段涨跌幅"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["阶段涨跌幅"] = pd.to_numeric(big_df["阶段涨跌幅"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["缩量天数"] = pd.to_numeric(big_df["缩量天数"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_cxsl_ths", "持续缩量", ["同花顺技术指标", "量价类"])


def fetch_xstp_ths(symbol: str = "500日均线", date: str | None = None) -> dict | None:
    """向上突破均线"""
    symbol_map = {"5日均线": 5, "10日均线": 10, "20日均线": 20, "30日均线": 30, "60日均线": 60, "90日均线": 90, "250日均线": 250, "500日均线": 500}
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = f"http://data.10jqka.com.cn/rank/xstp/board/{symbol_map[symbol]}/order/asc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_xstp_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/xstp/board/{symbol_map[symbol]}/order/asc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_xstp_ths")
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='m-table J-ajax-table')
        data = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 8:
                    item = {
                        '序号': cols[0].text.strip(),
                        '股票代码': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                        '股票简称': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                        '最新价': cols[3].text.strip(),
                        '成交额': cols[4].text.strip(),
                        '成交量': cols[5].text.strip(),
                        '涨跌幅': cols[6].text.strip(),
                        '换手率': cols[7].text.strip(),
                    }
                    data.append(item)
        temp_df = pd.DataFrame(data)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "最新价", "成交额", "成交量", "涨跌幅", "换手率"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.strip("%")
    big_df["换手率"] = big_df["换手率"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_xstp_ths", "向上突破", ["同花顺技术指标", "突破类"])


def fetch_xxtp_ths(symbol: str = "500日均线", date: str | None = None) -> dict | None:
    """向下突破均线"""
    symbol_map = {"5日均线": 5, "10日均线": 10, "20日均线": 20, "30日均线": 30, "60日均线": 60, "90日均线": 90, "250日均线": 250, "500日均线": 500}
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = f"http://data.10jqka.com.cn/rank/xxtp/board/{symbol_map[symbol]}/order/asc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_xxtp_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/xxtp/board/{symbol_map[symbol]}/order/asc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_xxtp_ths")
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='m-table J-ajax-table')
        data = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 8:
                    item = {
                        '序号': cols[0].text.strip(),
                        '股票代码': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                        '股票简称': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                        '最新价': cols[3].text.strip(),
                        '成交额': cols[4].text.strip(),
                        '成交量': cols[5].text.strip(),
                        '涨跌幅': cols[6].text.strip(),
                        '换手率': cols[7].text.strip(),
                    }
                    data.append(item)
        temp_df = pd.DataFrame(data)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "最新价", "成交额", "成交量", "涨跌幅", "换手率"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.strip("%")
    big_df["换手率"] = big_df["换手率"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_xxtp_ths", "向下突破", ["同花顺技术指标", "突破类"])


def fetch_ljqs_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """量价齐升"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/ljqs/field/count/order/desc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_ljqs_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/ljqs/field/count/order/desc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_ljqs_ths")
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='m-table J-ajax-table')
        data = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 8:
                    item = {
                        '序号': cols[0].text.strip(),
                        '股票代码': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                        '股票简称': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                        '最新价': cols[3].text.strip(),
                        '量价齐升天数': cols[4].text.strip(),
                        '阶段涨幅': cols[5].text.strip(),
                        '累计换手率': cols[6].text.strip(),
                        '所属行业': cols[7].find('a').text.strip() if cols[7].find('a') else cols[7].text.strip(),
                    }
                    data.append(item)
        temp_df = pd.DataFrame(data)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "最新价", "量价齐升天数", "阶段涨幅", "累计换手率", "所属行业"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["阶段涨幅"] = big_df["阶段涨幅"].astype(str).str.strip("%")
    big_df["累计换手率"] = big_df["累计换手率"].astype(str).str.strip("%")
    big_df["阶段涨幅"] = pd.to_numeric(big_df["阶段涨幅"], errors="coerce")
    big_df["累计换手率"] = pd.to_numeric(big_df["累计换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["量价齐升天数"] = pd.to_numeric(big_df["量价齐升天数"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_ljqs_ths", "量价齐升", ["同花顺技术指标", "量价类"])


def fetch_ljqd_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """量价齐跌"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/rank/ljqd/field/count/order/desc/ajax/1/free/1/page/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_ljqd_ths")
    soup = BeautifulSoup(r.text, features="lxml")
    try:
        total_page = int(soup.find(name="span", attrs={"class": "page_info"}).text.split("/")[1])
    except AttributeError:
        total_page = 1
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        v_code = js_code.call("v")
        headers["Cookie"] = f"v={v_code}"
        url = f"http://data.10jqka.com.cn/rank/ljqd/field/count/order/desc/ajax/1/free/1/page/{page}/free/1/"
        r = requests.get(url, headers=headers)
        _check_thx_blocked(r, "fetch_ljqd_ths")
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='m-table J-ajax-table')
        data = []
        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 8:
                    item = {
                        '序号': cols[0].text.strip(),
                        '股票代码': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                        '股票简称': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                        '最新价': cols[3].text.strip(),
                        '量价齐跌天数': cols[4].text.strip(),
                        '阶段涨幅': cols[5].text.strip(),
                        '累计换手率': cols[6].text.strip(),
                        '所属行业': cols[7].find('a').text.strip() if cols[7].find('a') else cols[7].text.strip(),
                    }
                    data.append(item)
        temp_df = pd.DataFrame(data)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = ["序号", "股票代码", "股票简称", "最新价", "量价齐跌天数", "阶段涨幅", "累计换手率", "所属行业"]
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["阶段涨幅"] = big_df["阶段涨幅"].astype(str).str.strip("%")
    big_df["累计换手率"] = big_df["累计换手率"].astype(str).str.strip("%")
    big_df["阶段涨幅"] = pd.to_numeric(big_df["阶段涨幅"], errors="coerce")
    big_df["累计换手率"] = pd.to_numeric(big_df["累计换手率"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["量价齐跌天数"] = pd.to_numeric(big_df["量价齐跌天数"], errors="coerce")
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_ljqd_ths", "量价齐跌", ["同花顺技术指标", "量价类"])


def fetch_xzjp_ths(symbol: str | None = None, date: str | None = None) -> dict | None:
    """险资举牌"""
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_ths("ths.js")
    js_code.eval(js_content)
    v_code = js_code.call("v")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
        "Cookie": f"v={v_code}",
    }
    url = "http://data.10jqka.com.cn/ajax/xzjp/field/DECLAREDATE/order/desc/ajax/1/free/1/"
    r = requests.get(url, headers=headers)
    _check_thx_blocked(r, "fetch_xzjp_ths")
    soup = BeautifulSoup(r.text, 'html.parser')
    table = soup.find('table', class_='m-table J-ajax-table')
    data = []
    if table:
        rows = table.find('tbody').find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 8:
                item = {
                    '序号': cols[0].text.strip(),
                    '举牌公告日': cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip(),
                    '股票代码': cols[2].find('a').text.strip() if cols[2].find('a') else cols[2].text.strip(),
                    '股票简称': cols[3].text.strip(),
                    '现价': cols[4].text.strip(),
                    '涨跌幅': cols[5].text.strip(),
                    '举牌方': cols[6].text.strip(),
                    '增持数量': cols[7].find('a').text.strip() if cols[7].find('a') else cols[7].text.strip(),
                    '交易均价': cols[8].find('a').text.strip() if cols[8].find('a') else cols[8].text.strip(),
                    '增持数量占总股本比例': cols[9].find('a').text.strip() if cols[9].find('a') else cols[9].text.strip(),
                    '变动后持股总数': cols[10].find('a').text.strip() if cols[10].find('a') else cols[10].text.strip(),
                    '变动后持股比例': cols[11].find('a').text.strip() if cols[11].find('a') else cols[11].text.strip(),
                    '历史数据': cols[12].find('a').text.strip() if cols[12].find('a') else cols[12].text.strip(),
                }
                data.append(item)
    big_df = pd.DataFrame(data)
    big_df.columns = ["序号", "举牌公告日", "股票代码", "股票简称", "现价", "涨跌幅", "举牌方", "增持数量", "交易均价", "增持数量占总股本比例", "变动后持股总数", "变动后持股比例", "历史数据"]
    big_df["涨跌幅"] = big_df["涨跌幅"].astype(str).str.zfill(6)
    big_df["增持数量占总股本比例"] = big_df["增持数量占总股本比例"].astype(str).str.strip("%")
    big_df["变动后持股比例"] = big_df["变动后持股比例"].astype(str).str.strip("%")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["增持数量占总股本比例"] = pd.to_numeric(big_df["增持数量占总股本比例"], errors="coerce")
    big_df["变动后持股比例"] = pd.to_numeric(big_df["变动后持股比例"], errors="coerce")
    big_df["举牌公告日"] = pd.to_datetime(big_df["举牌公告日"], errors="coerce").dt.date
    big_df["股票代码"] = big_df["股票代码"].astype(str).str.zfill(6)
    big_df["现价"] = pd.to_numeric(big_df["现价"], errors="coerce")
    big_df["交易均价"] = pd.to_numeric(big_df["交易均价"], errors="coerce")
    del big_df["历史数据"]
    return standardize_output(big_df, "股票代码", "股票简称", "fetch_xzjp_ths", "险资举牌", ["同花顺技术指标", "资金类"])


# ======== 巨潮资讯 (1 个) ========

def fetch_forecast_cninfo(symbol: str | None = None, date: str = "20230817") -> dict | None:
    """机构评级预测"""
    def _get_file_content_cninfo(file: str = "cninfo.js") -> str:
        setting_file_path = get_ths_js(file)
        with open(setting_file_path, encoding="utf-8") as f:
            file_data = f.read()
        return file_data

    url = "http://webapi.cninfo.com.cn/api/sysapi/p_sysapi1089"
    params = {"tdate": "-".join([date[:4], date[4:6], date[6:]])}
    js_code = py_mini_racer.MiniRacer()
    js_content = _get_file_content_cninfo("cninfo.js")
    js_code.eval(js_content)
    mcode = js_code.call("getResCode1")
    headers = {
        "Accept": "*/*",
        "Accept-Enckey": mcode,
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "0",
        "Host": "webapi.cninfo.com.cn",
        "Origin": "http://webapi.cninfo.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "http://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.post(url, params=params, headers=headers)
    _check_thx_blocked(r, "fetch_forecast_cninfo")
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "证券简称", "发布日期", "前一次投资评级", "评级变化", "目标价格-上限",
        "是否首次评级", "投资评级", "研究员名称", "研究机构简称", "目标价格-下限", "证券代码",
    ]
    temp_df = temp_df[["证券代码", "证券简称", "发布日期", "研究机构简称", "研究员名称",
                        "投资评级", "是否首次评级", "评级变化", "前一次投资评级",
                        "目标价格-下限", "目标价格-上限"]]
    temp_df["目标价格-上限"] = pd.to_numeric(temp_df["目标价格-上限"], errors="coerce")
    temp_df["目标价格-下限"] = pd.to_numeric(temp_df["目标价格-下限"], errors="coerce")
    return standardize_output(temp_df, "证券代码", "证券简称", "fetch_forecast_cninfo", "机构评级", ["同花顺技术指标", "评级类"])


# ======== 东方财富涨停板 (6 个) ========

def fetch_zt_pool_strong(symbol: str | None = None, date: str = "20241231") -> dict | None:
    """强势涨停池"""
    url = "https://push2ex.eastmoney.com/getTopicQSPool"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "5000",
        "sort": "zdp:desc",
        "date": date,
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        if data_json["data"] is None:
            return None
        if len(data_json["data"]["pool"]) == 0:
            return None
        temp_df = pd.DataFrame(data_json["data"]["pool"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.columns = [
            "序号", "代码", "_", "名称", "最新价", "涨停价", "_", "涨跌幅", "成交额",
            "流通市值", "总市值", "换手率", "是否新高", "入选理由", "量比", "涨速", "涨停统计", "所属行业",
        ]
        temp_df["涨停统计"] = (
            temp_df["涨停统计"].apply(lambda x: dict(x)["days"]).astype(str)
            + "/" + temp_df["涨停统计"].apply(lambda x: dict(x)["ct"]).astype(str)
        )
        temp_df = temp_df[["序号", "代码", "名称", "涨跌幅", "最新价", "涨停价", "成交额",
                            "流通市值", "总市值", "换手率", "涨速", "是否新高", "量比",
                            "涨停统计", "入选理由", "所属行业"]]
        temp_df["最新价"] = temp_df["最新价"] / 1000
        temp_df["涨停价"] = temp_df["涨停价"] / 1000
        explained_map = {1: "60日新高", 2: "近期多次涨停", 3: "60日新高且近期多次涨停"}
        temp_df["入选理由"] = temp_df["入选理由"].apply(lambda x: explained_map[x])
        temp_df["是否新高"] = temp_df["是否新高"].apply(lambda x: "是" if x == 1 else "否")
        temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        temp_df["涨停价"] = pd.to_numeric(temp_df["涨停价"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
        temp_df["流通市值"] = pd.to_numeric(temp_df["流通市值"], errors="coerce")
        temp_df["总市值"] = pd.to_numeric(temp_df["总市值"], errors="coerce")
        temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
        temp_df["涨速"] = pd.to_numeric(temp_df["涨速"], errors="coerce")
        temp_df["量比"] = pd.to_numeric(temp_df["量比"], errors="coerce")
        return standardize_output(temp_df, "代码", "名称", "fetch_zt_pool_strong", "强势涨停", ["涨停板分析"])
    except Exception:
        return None


def fetch_zt_pool(symbol: str | None = None, date: str = "20241008") -> dict | None:
    """涨停池"""
    url = "https://push2ex.eastmoney.com/getTopicZTPool"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "10000",
        "sort": "fbt:asc",
        "date": date,
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        if data_json["data"] is None:
            return None
        if len(data_json["data"]["pool"]) == 0:
            return None
        temp_df = pd.DataFrame(data_json["data"]["pool"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.columns = [
            "序号", "代码", "_", "名称", "最新价", "涨跌幅", "成交额", "流通市值", "总市值",
            "换手率", "连板数", "首次封板时间", "最后封板时间", "封板资金", "炸板次数", "所属行业", "涨停统计",
        ]
        temp_df["涨停统计"] = (
            temp_df["涨停统计"].apply(lambda x: dict(x)["days"]).astype(str)
            + "/" + temp_df["涨停统计"].apply(lambda x: dict(x)["ct"]).astype(str)
        )
        temp_df = temp_df[["序号", "代码", "名称", "涨跌幅", "最新价", "成交额", "流通市值", "总市值",
                            "换手率", "封板资金", "首次封板时间", "最后封板时间", "炸板次数",
                            "涨停统计", "连板数", "所属行业"]]
        temp_df["首次封板时间"] = temp_df["首次封板时间"].astype(str).str.zfill(6)
        temp_df["最后封板时间"] = temp_df["最后封板时间"].astype(str).str.zfill(6)
        temp_df["最新价"] = temp_df["最新价"] / 1000
        temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
        temp_df["流通市值"] = pd.to_numeric(temp_df["流通市值"], errors="coerce")
        temp_df["总市值"] = pd.to_numeric(temp_df["总市值"], errors="coerce")
        temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
        temp_df["封板资金"] = pd.to_numeric(temp_df["封板资金"], errors="coerce")
        temp_df["炸板次数"] = pd.to_numeric(temp_df["炸板次数"], errors="coerce")
        temp_df["连板数"] = pd.to_numeric(temp_df["连板数"], errors="coerce")
        return standardize_output(temp_df, "代码", "名称", "fetch_zt_pool", "涨停池", ["涨停板分析"])
    except Exception:
        return None


def fetch_zt_pool_dtgc(symbol: str | None = None, date: str = "20241011") -> dict | None:
    """跌停股池"""
    url = "https://push2ex.eastmoney.com/getTopicDTPool"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "10000",
        "sort": "fund:asc",
        "date": date,
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        if len(data_json["data"]["pool"]) == 0:
            return None
        temp_df = pd.DataFrame(data_json["data"]["pool"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.columns = [
            "序号", "代码", "_", "名称", "最新价", "涨跌幅", "成交额", "流通市值", "总市值",
            "动态市盈率", "换手率", "封单资金", "最后封板时间", "板上成交额", "连续跌停", "开板次数", "所属行业",
        ]
        temp_df = temp_df[["序号", "代码", "名称", "涨跌幅", "最新价", "成交额", "流通市值",
                            "总市值", "动态市盈率", "换手率", "封单资金", "最后封板时间",
                            "板上成交额", "连续跌停", "开板次数", "所属行业"]]
        temp_df["最新价"] = temp_df["最新价"] / 1000
        temp_df["最后封板时间"] = temp_df["最后封板时间"].astype(str).str.zfill(6)
        temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
        temp_df["流通市值"] = pd.to_numeric(temp_df["流通市值"], errors="coerce")
        temp_df["总市值"] = pd.to_numeric(temp_df["总市值"], errors="coerce")
        temp_df["动态市盈率"] = pd.to_numeric(temp_df["动态市盈率"], errors="coerce")
        temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
        temp_df["封单资金"] = pd.to_numeric(temp_df["封单资金"], errors="coerce")
        temp_df["板上成交额"] = pd.to_numeric(temp_df["板上成交额"], errors="coerce")
        temp_df["连续跌停"] = pd.to_numeric(temp_df["连续跌停"], errors="coerce")
        temp_df["开板次数"] = pd.to_numeric(temp_df["开板次数"], errors="coerce")
        return standardize_output(temp_df, "代码", "名称", "fetch_zt_pool_dtgc", "跌停股池", ["涨停板分析"])
    except Exception:
        return None


def fetch_zt_pool_sub_new(symbol: str | None = None, date: str = "20241231") -> dict | None:
    """次新股池"""
    url = "https://push2ex.eastmoney.com/getTopicCXPooll"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "5000",
        "sort": "ods:asc",
        "date": date,
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        if len(data_json["data"]["pool"]) == 0:
            return None
        temp_df = pd.DataFrame(data_json["data"]["pool"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.columns = [
            "序号", "代码", "_", "名称", "最新价", "涨停价", "_", "涨跌幅", "成交额",
            "流通市值", "总市值", "转手率", "开板几日", "开板日期", "上市日期", "_",
            "是否新高", "涨停统计", "所属行业",
        ]
        temp_df["涨停统计"] = (
            temp_df["涨停统计"].apply(lambda x: dict(x)["days"]).astype(str)
            + "/" + temp_df["涨停统计"].apply(lambda x: dict(x)["ct"]).astype(str)
        )
        temp_df = temp_df[["序号", "代码", "名称", "涨跌幅", "最新价", "涨停价", "成交额",
                            "流通市值", "总市值", "转手率", "开板几日", "开板日期",
                            "上市日期", "是否新高", "涨停统计", "所属行业"]]
        temp_df["最新价"] = temp_df["最新价"] / 1000
        temp_df["涨停价"] = temp_df["涨停价"] / 1000
        temp_df.loc[temp_df["涨停价"] > 100000, "涨停价"] = pd.NA
        temp_df["开板日期"] = pd.to_datetime(temp_df["开板日期"], format="%Y%m%d").dt.date
        temp_df["上市日期"] = pd.to_datetime(temp_df["上市日期"], format="%Y%m%d").dt.date
        temp_df.loc[temp_df["上市日期"] == 0, "上市日期"] = pd.NaT
        temp_df["是否新高"] = temp_df["是否新高"].apply(lambda x: "是" if x == 1 else "否")
        return standardize_output(temp_df, "代码", "名称", "fetch_zt_pool_sub_new", "次新股池", ["涨停板分析"])
    except Exception:
        return None


def fetch_zt_pool_previous(symbol: str | None = None, date: str = "20240415") -> dict | None:
    """昨日涨停表现"""
    url = "https://push2ex.eastmoney.com/getYesterdayZTPool"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "5000",
        "sort": "zs:desc",
        "date": date,
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        if data_json["data"] is None:
            return None
        if len(data_json["data"]["pool"]) == 0:
            return None
        temp_df = pd.DataFrame(data_json["data"]["pool"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.columns = [
            "序号", "代码", "_", "名称", "最新价", "涨停价", "涨跌幅", "成交额",
            "流通市值", "总市值", "换手率", "振幅", "涨速", "昨日封板时间", "昨日连板数", "所属行业", "涨停统计",
        ]
        temp_df["涨停统计"] = (
            temp_df["涨停统计"].apply(lambda x: dict(x)["days"]).astype(str)
            + "/" + temp_df["涨停统计"].apply(lambda x: dict(x)["ct"]).astype(str)
        )
        temp_df = temp_df[["序号", "代码", "名称", "涨跌幅", "最新价", "涨停价", "成交额",
                            "流通市值", "总市值", "换手率", "涨速", "振幅", "昨日封板时间",
                            "昨日连板数", "涨停统计", "所属行业"]]
        temp_df["最新价"] = temp_df["最新价"] / 1000
        temp_df["涨停价"] = temp_df["涨停价"] / 1000
        temp_df["昨日封板时间"] = temp_df["昨日封板时间"].astype(str).str.zfill(6)
        return standardize_output(temp_df, "代码", "名称", "fetch_zt_pool_previous", "昨日涨停表现", ["涨停板分析"])
    except Exception:
        return None


def fetch_zt_pool_zbgc(symbol: str | None = None, date: str = "20241011") -> dict | None:
    """炸板股池"""
    url = "https://push2ex.eastmoney.com/getTopicZBPool"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "5000",
        "sort": "fbt:asc",
        "date": date,
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        if data_json["data"] is None:
            return None
        if len(data_json["data"]["pool"]) == 0:
            return None
        temp_df = pd.DataFrame(data_json["data"]["pool"])
        temp_df.reset_index(inplace=True)
        temp_df["index"] = range(1, len(temp_df) + 1)
        temp_df.columns = [
            "序号", "代码", "_", "名称", "最新价", "涨停价", "涨跌幅", "成交额",
            "流通市值", "总市值", "换手率", "首次封板时间", "炸板次数", "振幅", "涨速", "涨停统计", "所属行业",
        ]
        temp_df["涨停统计"] = (
            temp_df["涨停统计"].apply(lambda x: dict(x)["days"]).astype(str)
            + "/" + temp_df["涨停统计"].apply(lambda x: dict(x)["ct"]).astype(str)
        )
        temp_df = temp_df[["序号", "代码", "名称", "涨跌幅", "最新价", "涨停价", "成交额",
                            "流通市值", "总市值", "换手率", "涨速", "首次封板时间",
                            "炸板次数", "涨停统计", "振幅", "所属行业"]]
        temp_df["最新价"] = temp_df["最新价"] / 1000
        temp_df["涨停价"] = temp_df["涨停价"] / 1000
        temp_df["首次封板时间"] = temp_df["首次封板时间"].astype(str).str.zfill(6)
        return standardize_output(temp_df, "代码", "名称", "fetch_zt_pool_zbgc", "炸板股池", ["涨停板分析"])
    except Exception:
        return None


# ======== 东方财富异动监控 (2 个) ========

def fetch_board_change(symbol: str | None = None, date: str | None = None) -> dict | None:
    """板块异动排名"""
    url = "https://push2ex.eastmoney.com/getAllBKChanges"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wzchanges",
        "pageindex": "0",
        "pagesize": "5000",
    }
    try:
        r = requests.get(url, params=params)
        data_json = r.json()
        data_df = pd.DataFrame(data_json["data"]["allbk"])
        data_df.columns = [
            "-", "-", "板块名称", "涨跌幅", "主力净流入", "板块异动总次数", "ms", "板块具体异动类型列表及出现次数",
        ]
        data_df["板块异动最频繁个股及所属类型-买卖方向"] = [item["m"] for item in data_df["ms"]]
        data_df["板块异动最频繁个股及所属类型-股票代码"] = [item["c"] for item in data_df["ms"]]
        data_df["板块异动最频繁个股及所属类型-股票名称"] = [item["n"] for item in data_df["ms"]]
        data_df["板块异动最频繁个股及所属类型-买卖方向"] = data_df["板块异动最频繁个股及所属类型-买卖方向"].map({0: "大笔买入", 1: "大笔卖出"})
        data_df = data_df[["板块名称", "涨跌幅", "主力净流入", "板块异动总次数",
                            "板块异动最频繁个股及所属类型-股票代码",
                            "板块异动最频繁个股及所属类型-股票名称",
                            "板块异动最频繁个股及所属类型-买卖方向",
                            "板块具体异动类型列表及出现次数"]]
        data_df["涨跌幅"] = pd.to_numeric(data_df["涨跌幅"], errors="coerce")
        data_df["主力净流入"] = pd.to_numeric(data_df["主力净流入"], errors="coerce")
        data_df["板块异动总次数"] = pd.to_numeric(data_df["板块异动总次数"], errors="coerce")
        return standardize_output(data_df, "板块异动最频繁个股及所属类型-股票代码",
                                  "板块异动最频繁个股及所属类型-股票名称",
                                  "fetch_board_change", "板块异动", ["异动监控"])
    except Exception:
        return None


def fetch_changes(symbol: str = "大笔买入", date: str | None = None) -> dict | None:
    """个股盘口异动"""
    symbol_map = {
        "火箭发射": "8201", "快速反弹": "8202", "大笔买入": "8193", "封涨停板": "4",
        "打开跌停板": "32", "有大买盘": "64", "竞价上涨": "8207", "高开5日线": "8209",
        "向上缺口": "8211", "60日新高": "8213", "60日大幅上涨": "8215", "加速下跌": "8204",
        "高台跳水": "8203", "大笔卖出": "8194", "封跌停板": "8", "打开涨停板": "16",
        "有大卖盘": "128", "竞价下跌": "8208", "低开5日线": "8210", "向下缺口": "8212",
        "60日新低": "8214", "60日大幅下跌": "8216",
    }
    reversed_symbol_map = {v: k for k, v in symbol_map.items()}
    params = {
        "type": symbol_map[symbol],
        "pageindex": "0",
        "pagesize": "5000",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wzchanges",
    }
    try:
        r = requests.get("https://push2ex.eastmoney.com/getAllStockChanges", params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["allstock"])
        temp_df["tm"] = pd.to_datetime(temp_df["tm"], format="%H%M%S").dt.time
        temp_df.columns = ["时间", "代码", "_", "名称", "板块", "相关信息"]
        temp_df = temp_df[["时间", "代码", "名称", "板块", "相关信息"]]
        temp_df["板块"] = temp_df["板块"].astype(str)
        temp_df["板块"] = temp_df["板块"].map(reversed_symbol_map)
        return standardize_output(temp_df, "代码", "名称", "fetch_changes", "个股异动", ["异动监控"])
    except Exception:
        return None
