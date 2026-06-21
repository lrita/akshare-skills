#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A股实时行情与日内分钟K线数据获取工具。

用法:
    uv run python scripts/fetch_realtime.py quote --symbol 600183
    uv run python scripts/fetch_realtime.py intraday --symbol 600183

输出结构化 JSON 到 stdout，所有字段中文命名带单位。
"""
import argparse
import json
import sys
import urllib.request


def fetch_tencent_quote_verbose(code: str) -> dict:
    """从腾讯财经获取实时行情快照（完整版，含盘口数据）。

    解析 qt.gtimg.cn 返回的 ~ 分隔字符串，按语义分为行情数据、成交数据、
    盘口数据、估值数据四个分组。

    Args:
        code: 6 位股票代码，如 600183

    Returns:
        dict，含股票代码、股票名称、行情更新时间及四个分组子对象，失败返回 {}
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
        req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")
        req.add_header("Referer", "https://gu.qq.com/")
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
                "股票代码": vals[2],
                "股票名称": vals[1],
                "行情更新时间": vals[30],
                "行情数据": {
                    "当前价格(元)": float(vals[3]) if vals[3] else 0.0,
                    "昨收价(元)":   float(vals[4]) if vals[4] else 0.0,
                    "今开价(元)":   float(vals[5]) if vals[5] else 0.0,
                    "最高价(元)":   float(vals[33]) if vals[33] else 0.0,
                    "最低价(元)":   float(vals[34]) if vals[34] else 0.0,
                    "涨跌额(元)":   float(vals[31]) if vals[31] else 0.0,
                    "涨跌幅(%)":    float(vals[32]) if vals[32] else 0.0,
                    "振幅(%)":      float(vals[43]) if vals[43] else 0.0,
                    "日内均价(元)": float(vals[51]) if vals[51] else 0.0,
                },
                "成交数据": {
                    "成交量(手)":   int(float(vals[6])) if vals[6] else 0,
                    "成交额(万元)": float(vals[37]) if vals[37] else 0.0,
                    "换手率(%)":    float(vals[38]) if vals[38] else 0.0,
                    "量比":         float(vals[49]) if vals[49] else 0.0,
                    "外盘(手)":     int(float(vals[7])) if vals[7] else 0,
                    "内盘(手)":     int(float(vals[8])) if vals[8] else 0,
                },
                "盘口数据": {
                    "买一价(元)": float(vals[9]) if vals[9] else 0.0,
                    "买一量(手)": int(float(vals[10])) if vals[10] else 0,
                    "买二价(元)": float(vals[11]) if vals[11] else 0.0,
                    "买二量(手)": int(float(vals[12])) if vals[12] else 0,
                    "买三价(元)": float(vals[13]) if vals[13] else 0.0,
                    "买三量(手)": int(float(vals[14])) if vals[14] else 0,
                    "买四价(元)": float(vals[15]) if vals[15] else 0.0,
                    "买四量(手)": int(float(vals[16])) if vals[16] else 0,
                    "买五价(元)": float(vals[17]) if vals[17] else 0.0,
                    "买五量(手)": int(float(vals[18])) if vals[18] else 0,
                    "卖一价(元)": float(vals[19]) if vals[19] else 0.0,
                    "卖一量(手)": int(float(vals[20])) if vals[20] else 0,
                    "卖二价(元)": float(vals[21]) if vals[21] else 0.0,
                    "卖二量(手)": int(float(vals[22])) if vals[22] else 0,
                    "卖三价(元)": float(vals[23]) if vals[23] else 0.0,
                    "卖三量(手)": int(float(vals[24])) if vals[24] else 0,
                    "卖四价(元)": float(vals[25]) if vals[25] else 0.0,
                    "卖四量(手)": int(float(vals[26])) if vals[26] else 0,
                    "卖五价(元)": float(vals[27]) if vals[27] else 0.0,
                    "卖五量(手)": int(float(vals[28])) if vals[28] else 0,
                    "委差":         int(float(vals[50])) if vals[50] else 0,
                },
                "估值数据": {
                    "滚动市盈率":   float(vals[39]) if vals[39] else 0.0,
                    "动态市盈率":   float(vals[52]) if vals[52] else 0.0,
                    "市净率":       float(vals[46]) if vals[46] else 0.0,
                    "流通市值(亿)": float(vals[44]) if vals[44] else 0.0,
                    "总市值(亿)":   float(vals[45]) if vals[45] else 0.0,
                    "涨停价(元)":   float(vals[47]) if vals[47] else 0.0,
                    "跌停价(元)":   float(vals[48]) if vals[48] else 0.0,
                },
            }
        except (ValueError, IndexError):
            return {}
    return {}


def fetch_intraday_minute(code: str) -> dict:
    """从腾讯财经获取当日分钟级K线数据。

    解析 web.ifzq.gtimg.cn 返回的分钟K线 JSON，提取每笔分钟数据
    （时间、价格、成交量、成交额）。

    Args:
        code: 6 位股票代码，如 600183

    Returns:
        dict，含股票代码、股票名称、交易日期、分钟K线数组，失败返回 {}
    """
    if code.startswith(("6", "9")):
        prefixed = f"sh{code}"
    elif code.startswith("8"):
        prefixed = f"bj{code}"
    else:
        prefixed = f"sz{code}"

    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/minute/query"
        f"?_var=min_data&code={prefixed}"
    )
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")
        req.add_header("Referer", "https://gu.qq.com/")
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("utf-8")
    except Exception:
        return {}

    # 去掉 "min_data=" 前缀，解析 JSON
    prefix = "min_data="
    if not raw.startswith(prefix):
        return {}
    json_str = raw[len(prefix):]
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return {}

    stock_data = data.get("data", {}).get(prefixed, {})
    minute_section = stock_data.get("data", {})
    trading_date = minute_section.get("date", "")
    raw_minutes = minute_section.get("data", [])

    # 从 qt 快照提取股票名称
    qt_list = stock_data.get("qt", {}).get(prefixed, [])
    stock_name = qt_list[1] if len(qt_list) > 1 else code

    minutes = []
    for raw_str in raw_minutes:
        parts = raw_str.split()
        if len(parts) != 4:
            continue
        try:
            minutes.append({
                "时间": parts[0],
                "价格(元)": float(parts[1]),
                "成交量": int(parts[2]),
                "成交额(元)": float(parts[3]),
            })
        except (ValueError, IndexError):
            continue

    return {
        "股票代码": code,
        "股票名称": stock_name,
        "交易日期": trading_date,
        "分钟K线": minutes,
    }
