#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
公募基金综合信息查询脚本
基于 akshare 多个基金 API，并发获取基金概况、净值、风险、费率、持仓等全维度数据
"""
import sys
import json
import argparse
import re
import time
import random
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np


# ---- 常量 ----

Q1_DISCLOSURE_CUTOFF_DAY = (4, 22)  # (month, day)

SECTION_ORDER = [
    "overview", "nav_history", "risk_analysis", "profit_probability",
    "asset_allocation", "fee_and_rules", "stock_holdings",
    "bond_holdings", "industry_allocation",
]


# ---- 校验 ----

def validate_code(code: str) -> None:
    """校验基金代码格式（6位纯数字）"""
    if not re.match(r"^\d{6}$", code):
        raise ValueError(
            f"非法的基金代码: '{code}'。基金代码必须为 6 位纯数字。"
        )


# ---- 日期推断 ----

def determine_portfolio_year(ref_date: date) -> int:
    """根据当前日期推断持仓查询年份。

    规则：若已过 Q1 披露截止日 (4/22)，取当前年份 - 1；否则取 - 2。
    例如：2026-06-20 → 2025; 2026-03-01 → 2024
    """
    cutoff_month, cutoff_day = Q1_DISCLOSURE_CUTOFF_DAY
    passed_cutoff = (
        ref_date.month > cutoff_month
        or (ref_date.month == cutoff_month and ref_date.day >= cutoff_day)
    )
    return ref_date.year - 1 if passed_cutoff else ref_date.year - 2


def determine_hold_date(ref_date: date) -> str:
    """推断 fund_individual_detail_hold_xq 的 date 参数 (YYYYMMDD)。

    取最近一个 Q4 的 12 月 31 日。
    """
    year = determine_portfolio_year(ref_date)
    return f"{year}1231"


# ---- API 响应解析 ----

def _df_to_records(df: pd.DataFrame, column_map: dict) -> list | None:
    """将 DataFrame 转为 dict 列表，列名映射 + NaN→None"""
    if df is None or df.empty:
        return None
    df = df.rename(columns=column_map)
    cols = list(column_map.values())
    df = df[cols].copy()
    df = df.where(df.notna(), None)
    return df.to_dict(orient="records")


def parse_overview(df: pd.DataFrame) -> dict | None:
    """解析 fund_overview_em 返回值"""
    if df is None or df.empty:
        return None
    row = df.iloc[0].to_dict()
    field_map = {
        "基金全称": "fund_full_name",
        "基金简称": "fund_name",
        "基金代码": "fund_code",
        "基金类型": "fund_type",
        "发行日期": "issue_date",
        "成立日期/规模": "establishment_date",
    }
    result = {}
    for cn_key, en_key in field_map.items():
        val = row.get(cn_key)
        result[en_key] = str(val) if val is not None else None
    # 附加字段
    extra_fields = ["净资产规模", "份额规模", "基金管理人", "基金托管人",
                    "基金经理人", "成立来分红", "管理费率", "托管费率",
                    "销售服务费率", "最高认购费率", "业绩比较基准", "跟踪标的"]
    extra_keys = ["net_asset_value", "share_size", "fund_manager", "fund_custodian",
                  "portfolio_manager", "dividends_since_inception",
                  "management_fee_rate", "custodian_fee_rate", "sales_service_fee_rate",
                  "max_subscription_fee_rate", "benchmark", "tracking_target"]
    for cn_key, en_key in zip(extra_fields, extra_keys):
        val = row.get(cn_key)
        result[en_key] = str(val) if val is not None else None
    # establishment_scale 与 establishment_date 同源
    val = row.get("成立日期/规模")
    result["establishment_scale"] = str(val) if val is not None else None
    return result


def parse_nav_history(df: pd.DataFrame) -> list | None:
    """解析 fund_open_fund_info_em 返回值"""
    if df is None or df.empty:
        return None
    df = df.copy()
    records = []
    for _, row in df.iterrows():
        d = row.get("净值日期")
        date_str = ""
        if d is not None:
            if hasattr(d, "strftime"):
                date_str = d.strftime("%Y-%m-%d")
            else:
                date_str = str(d)
        val = row.get("单位净值")
        ret = row.get("日增长率")
        def _safe_float(v):
            if v is None:
                return None
            try:
                f = float(v)
                if np.isnan(f):
                    return None
                return f
            except (ValueError, TypeError):
                return None
        records.append({
            "date": date_str,
            "unit_net_value": _safe_float(val),
            "daily_return": _safe_float(ret),
        })
    return records


def parse_risk_analysis(df: pd.DataFrame) -> list | None:
    return _df_to_records(df, {
        "周期": "period",
        "较同类风险收益比": "risk_return_rank",
        "较同类抗风险波动": "risk_resilience_rank",
        "年化波动率": "annualized_volatility",
        "年化夏普比率": "annualized_sharpe",
        "最大回撤": "max_drawdown",
    })


def parse_profit_probability(df: pd.DataFrame) -> list | None:
    return _df_to_records(df, {
        "持有时长": "holding_period",
        "盈利概率": "profit_probability",
        "平均收益": "avg_return",
    })


def parse_asset_allocation(df: pd.DataFrame) -> list | None:
    return _df_to_records(df, {
        "资产类型": "asset_type",
        "仓位占比": "allocation_ratio",
    })


def parse_fee_and_rules(
    fee_status_df: pd.DataFrame,
    fee_op_cost_df: pd.DataFrame,
    fee_redemption_df: pd.DataFrame,
    trade_rules_df: pd.DataFrame,
) -> dict | None:
    """解析 fund_fee_em (3个indicator) + fund_individual_detail_info_xq"""
    all_empty = all(
        df is None or df.empty
        for df in [fee_status_df, fee_op_cost_df, fee_redemption_df, trade_rules_df]
    )
    if all_empty:
        return None

    # 解析交易状态 (fund_fee_em, indicator="交易状态")
    status = {"purchase_status": None, "redemption_status": None, "auto_invest_status": None}
    if fee_status_df is not None and not fee_status_df.empty:
        for _, row in fee_status_df.iterrows():
            # 每行可能有多个 key-value 对（按列成对出现）
            num_cols = len(row)
            col_idx = 0
            while col_idx + 1 < num_cols:
                key = str(row.iloc[col_idx]) if row.iloc[col_idx] is not None else ""
                val = str(row.iloc[col_idx + 1]) if row.iloc[col_idx + 1] is not None else ""
                if "申购状态" in key:
                    status["purchase_status"] = val
                elif "赎回状态" in key:
                    status["redemption_status"] = val
                elif "定投状态" in key:
                    status["auto_invest_status"] = val
                col_idx += 2

    # 解析运作费用 (fund_fee_em, indicator="运作费用")
    op_cost = {"management_fee_rate": None, "custodian_fee_rate": None, "sales_service_fee_rate": None}
    if fee_op_cost_df is not None and not fee_op_cost_df.empty:
        for _, row in fee_op_cost_df.iterrows():
            key = str(row.iloc[0]) if row.iloc[0] is not None else ""
            val = str(row.iloc[1]) if row.iloc[1] is not None else ""
            if "管理费率" in key:
                op_cost["management_fee_rate"] = val
            elif "托管费率" in key:
                op_cost["custodian_fee_rate"] = val
            elif "销售服务费率" in key:
                op_cost["sales_service_fee_rate"] = val

    # 解析赎回费率表 (fund_fee_em, indicator="赎回费率")
    redemption_table = []
    if fee_redemption_df is not None and not fee_redemption_df.empty:
        df = fee_redemption_df.copy()
        df = df.where(df.notna(), None)
        for _, row in df.iterrows():
            period_val = row.get("适用期限")
            rate_val = row.get("赎回费率")
            redemption_table.append({
                "period": str(period_val) if period_val is not None else None,
                "rate": str(rate_val) if rate_val is not None else None,
            })

    # 解析交易规则 (fund_individual_detail_info_xq)
    purchase_rules = []
    redemption_rules = []
    other_fees = []
    if trade_rules_df is not None and not trade_rules_df.empty:
        for _, row in trade_rules_df.iterrows():
            fee_type = str(row["费用类型"]) if row["费用类型"] is not None else ""
            name = str(row["条件或名称"]) if row["条件或名称"] is not None else ""
            fee = row["费用"]
            fee_str = str(fee) + "%" if fee is not None else None
            if "买入规则" in fee_type:
                purchase_rules.append({"amount_range": name, "fee_rate": fee_str})
            elif "卖出规则" in fee_type:
                redemption_rules.append({"holding_period": name, "fee_rate": fee_str})
            elif "其他费用" in fee_type:
                other_fees.append({"name": name, "rate": fee_str})

    return {
        "purchase_status": status["purchase_status"],
        "redemption_status": status["redemption_status"],
        "auto_invest_status": status["auto_invest_status"],
        "management_fee_rate": op_cost["management_fee_rate"],
        "custodian_fee_rate": op_cost["custodian_fee_rate"],
        "sales_service_fee_rate": op_cost["sales_service_fee_rate"],
        "redemption_fee_table": redemption_table,
        "purchase_rules": purchase_rules,
        "redemption_rules": redemption_rules,
        "other_fees": other_fees,
    }


def parse_stock_holdings(df: pd.DataFrame) -> list | None:
    if df is None or df.empty:
        return None
    if "季度" in df.columns:
        quarter_counts = df.groupby("季度").size()
        if len(quarter_counts) > 0:
            latest_quarter = quarter_counts.idxmax()
            df = df[df["季度"] == latest_quarter]
    return _df_to_records(df, {
        "股票代码": "stock_code",
        "股票名称": "stock_name",
        "占净值比例": "net_value_ratio",
        "持股数": "shares_held",
        "持仓市值": "market_value",
        "季度": "quarter",
    })


def parse_bond_holdings(df: pd.DataFrame) -> list | None:
    if df is None or df.empty:
        return None
    if "季度" in df.columns:
        quarter_counts = df.groupby("季度").size()
        if len(quarter_counts) > 0:
            latest_quarter = quarter_counts.idxmax()
            df = df[df["季度"] == latest_quarter]
    return _df_to_records(df, {
        "债券代码": "bond_code",
        "债券名称": "bond_name",
        "占净值比例": "net_value_ratio",
        "持仓市值": "market_value",
        "季度": "quarter",
    })


def parse_industry_allocation(df: pd.DataFrame) -> list | None:
    return _df_to_records(df, {
        "行业类别": "industry_name",
        "占净值比例": "net_value_ratio",
        "市值": "market_value",
        "截止时间": "report_date",
    })


# ---- 聚合 ----

def aggregate_result(
    code: str,
    overview: dict | None,
    nav: list | None,
    risk: list | None,
    profit: list | None,
    asset_alloc: list | None,
    fee: dict | None,
    stock_holdings: list | None,
    bond_holdings: list | None,
    industry: list | None,
    errors: list,
) -> dict:
    ref_date = date.today()
    now = datetime.now()
    return {
        "meta": {
            "fund_code": code,
            "fetch_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "portfolio_year": str(determine_portfolio_year(ref_date)),
            "portfolio_date": determine_hold_date(ref_date),
            "nav_period": "成立来",
            "nav_indicator": "单位净值走势",
        },
        "overview": overview,
        "nav_history": nav,
        "risk_analysis": risk,
        "profit_probability": profit,
        "asset_allocation": asset_alloc,
        "fee_and_rules": fee,
        "stock_holdings": stock_holdings,
        "bond_holdings": bond_holdings,
        "industry_allocation": industry,
        "errors": errors,
    }


# ---- API 调用包装 ----

def _fetch_with_retry(fn_name: str, section: str, api_name: str, *args):
    """调用单个 API，失败时返回 error dict"""
    import akshare as ak
    try:
        func = getattr(ak, fn_name)
        df = func(*args)
        if df is None or (hasattr(df, "empty") and df.empty):
            return section, None, {"section": section, "error": "API returned empty data", "api": api_name}
        return section, df, None
    except Exception as e:
        return section, None, {"section": section, "error": str(e), "api": api_name}


# ---- 主函数 ----

def main() -> None:
    parser = argparse.ArgumentParser(description="公募基金综合信息查询")
    parser.add_argument("--code", required=True, help="6位基金代码，如 000001")
    args = parser.parse_args()

    try:
        validate_code(args.code)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(2)

    code = args.code
    ref_date = date.today()
    portfolio_year = determine_portfolio_year(ref_date)
    hold_date = determine_hold_date(ref_date)

    print(f"[INFO] 正在获取基金 {code} 的综合信息...", file=sys.stderr)
    print(f"[INFO] 持仓查询年份: {portfolio_year}, 配置查询日期: {hold_date}", file=sys.stderr)
    print(f"[INFO] 并发调用 API (5 workers)...", file=sys.stderr)

    # 主 API 列表
    api_calls = [
        ("fund_overview_em", "overview", code),
        ("fund_open_fund_info_em", "nav_history", code, "单位净值走势", "成立来"),
        ("fund_individual_analysis_xq", "risk_analysis", code),
        ("fund_individual_profit_probability_xq", "profit_probability", code),
        ("fund_individual_detail_hold_xq", "asset_allocation", code, hold_date),
        ("fund_portfolio_hold_em", "stock_holdings", code, str(portfolio_year)),
        ("fund_portfolio_bond_hold_em", "bond_holdings", code, str(portfolio_year)),
        ("fund_portfolio_industry_allocation_em", "industry_allocation", code, str(portfolio_year)),
    ]

    # fee_and_rules 子 API 列表
    fee_calls = [
        ("fund_fee_em", "fee_status", code, "交易状态"),
        ("fund_fee_em", "fee_op_cost", code, "运作费用"),
        ("fund_fee_em", "fee_redemption", code, "赎回费率"),
        ("fund_individual_detail_info_xq", "fee_trade_rules", code),
    ]

    results = {}
    all_errors = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for fn_name, section, *fn_args in api_calls:
            jitter = random.uniform(0.1, 0.3)
            time.sleep(jitter)
            futures[executor.submit(_fetch_with_retry, fn_name, section, fn_name, *fn_args)] = section

        fee_futures = {}
        for fn_name, sub_key, *fn_args in fee_calls:
            time.sleep(random.uniform(0.1, 0.3))
            fee_futures[executor.submit(_fetch_with_retry, fn_name, sub_key, fn_name, *fn_args)] = sub_key

        # 收集主 API 结果
        for future in as_completed(futures):
            section = futures[future]
            sec, data, error = future.result()
            if error:
                all_errors.append(error)
            results[sec] = data

        # 收集 fee API 结果
        fee_results = {}
        for future in as_completed(fee_futures):
            sub_key = fee_futures[future]
            sec, data, error = future.result()
            if error:
                all_errors.append({"section": "fee_and_rules", **error})
            fee_results[sub_key] = data

    # 解析各 API 结果
    overview = parse_overview(results.get("overview"))
    print(f"[INFO] overview: {'成功' if overview else '失败'}", file=sys.stderr)

    nav = parse_nav_history(results.get("nav_history"))
    nav_count = len(nav) if nav else 0
    print(f"[INFO] nav_history: {'成功' if nav else '失败'}{' (' + str(nav_count) + ' 条)' if nav_count else ''}", file=sys.stderr)

    risk = parse_risk_analysis(results.get("risk_analysis"))
    print(f"[INFO] risk_analysis: {'成功' if risk else '失败'}", file=sys.stderr)

    profit = parse_profit_probability(results.get("profit_probability"))
    print(f"[INFO] profit_probability: {'成功' if profit else '失败'}", file=sys.stderr)

    asset_alloc = parse_asset_allocation(results.get("asset_allocation"))
    print(f"[INFO] asset_allocation: {'成功' if asset_alloc else '失败'}", file=sys.stderr)

    fee = parse_fee_and_rules(
        fee_results.get("fee_status"),
        fee_results.get("fee_op_cost"),
        fee_results.get("fee_redemption"),
        fee_results.get("fee_trade_rules"),
    )
    print(f"[INFO] fee_and_rules: {'成功' if fee else '失败'}", file=sys.stderr)

    stock = parse_stock_holdings(results.get("stock_holdings"))
    stock_count = len(stock) if stock else 0
    stock_quarter = stock[0].get("quarter", "") if stock and len(stock) > 0 else ""
    print(f"[INFO] stock_holdings: {'成功' if stock else '失败'}{' (' + str(stock_count) + ' 条, ' + stock_quarter + ')' if stock_count else ''}", file=sys.stderr)

    bond = parse_bond_holdings(results.get("bond_holdings"))
    bond_count = len(bond) if bond else 0
    print(f"[INFO] bond_holdings: {'成功' if bond else '失败'}{' (' + str(bond_count) + ' 条)' if bond_count else ''}", file=sys.stderr)

    industry = parse_industry_allocation(results.get("industry_allocation"))
    print(f"[INFO] industry_allocation: {'成功' if industry else '失败'}", file=sys.stderr)

    output = aggregate_result(
        code=code, overview=overview, nav=nav, risk=risk, profit=profit,
        asset_alloc=asset_alloc, fee=fee, stock_holdings=stock,
        bond_holdings=bond, industry=industry, errors=all_errors,
    )

    total_sections = len(SECTION_ORDER)
    failed = len([s for s in SECTION_ORDER if output[s] is None])
    print(f"[INFO] 完成: {total_sections - failed}/{total_sections} 成功, {len(all_errors)} 错误", file=sys.stderr)

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    print()

    if all(output[s] is None for s in SECTION_ORDER):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
