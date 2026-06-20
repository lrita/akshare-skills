#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
开放基金排行查询脚本
基于东方财富开放基金排行 API，提供筛选、排序、Top-N、JSON/JSONL 输出功能
"""
import sys
import json
import argparse
import math
import re
from typing import Optional

import pandas as pd


# ---- 常量 ----

SYMBOL_CHOICES = ["全部", "股票型", "混合型", "债券型", "指数型", "QDII", "FOF"]

SORT_BY_CHOICES = [
    "日增长率", "近1周", "近1月", "近3月", "近6月",
    "近1年", "近2年", "近3年", "今年来", "成立来",
    "单位净值", "累计净值",
]

CN_TO_EN_COLUMN = {
    "基金代码": "fund_code",
    "基金简称": "fund_name",
    "日期": "date",
    "单位净值": "unit_net_value",
    "累计净值": "cumulative_net_value",
    "日增长率": "daily_return",
    "近1周": "1w_return",
    "近1月": "1m_return",
    "近3月": "3m_return",
    "近6月": "6m_return",
    "近1年": "1y_return",
    "近2年": "2y_return",
    "近3年": "3y_return",
    "今年来": "ytd_return",
    "成立来": "since_inception_return",
    "手续费": "fee",
}

OUTPUT_COLUMNS = list(CN_TO_EN_COLUMN.values())

FILTER_PATTERN = re.compile(
    r"^(.+?)(>=|<=|>|<|=)(-?\d+(?:\.\d+)?)$"
)


# ---- 校验函数 ----

def validate_symbol(value: str) -> None:
    """校验 --symbol 参数"""
    if value not in SYMBOL_CHOICES:
        raise ValueError(
            f"非法的 --symbol 值: '{value}'。"
            f"合法值: {', '.join(SYMBOL_CHOICES)}"
        )


def validate_sort_by(value: str) -> None:
    """校验 --sort-by 参数"""
    if value not in SORT_BY_CHOICES:
        raise ValueError(
            f"非法的 --sort-by 值: '{value}'。"
            f"合法值: {', '.join(SORT_BY_CHOICES)}"
        )


def validate_order(value: str) -> None:
    """校验 --order 参数"""
    if value not in ("desc", "asc"):
        raise ValueError(
            f"非法的 --order 值: '{value}'。合法值: desc, asc"
        )


def validate_top_n(value: str) -> int:
    """校验 --top-n 参数，返回整数"""
    try:
        n = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"--top-n 必须是正整数，收到: '{value}'")
    if n <= 0:
        raise ValueError(f"--top-n 必须是正整数，收到: {n}")
    return n


def validate_output(value: str) -> None:
    """校验 --output 参数"""
    if value not in ("jsonl", "json"):
        raise ValueError(
            f"非法的 --output 值: '{value}'。合法值: jsonl, json"
        )


# ---- 过滤解析 ----

def parse_filter(raw: str) -> tuple:
    """解析单个 --filter 表达式。

    参数:
        raw: 过滤表达式，如 "近1月>10" 或 "单位净值<=5.0"

    返回:
        (column_cn, operator, value) 如 ("近1月", ">", 10.0)

    异常:
        ValueError: 格式不合法
    """
    m = FILTER_PATTERN.match(raw.strip())
    if not m:
        raise ValueError(
            f"非法的 --filter 格式: '{raw}'。"
            f"期望格式: <列名><运算符><数值>，"
            f"运算符: >, >=, <, <=, =。示例: --filter 近1月>10"
        )
    col, op, val = m.group(1), m.group(2), m.group(3)
    if col not in SORT_BY_CHOICES:
        raise ValueError(
            f"非法的过滤列名: '{col}'。"
            f"合法列名: {', '.join(SORT_BY_CHOICES)}"
        )
    return col, op, float(val)


# ---- 数据处理 ----

def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """重命名中文列名为英文列名，仅保留 OUTPUT_COLUMNS 中的 16 列。"""
    result = df.rename(columns=CN_TO_EN_COLUMN)
    return result[OUTPUT_COLUMNS]


def apply_filters(
    df: pd.DataFrame, filters: list
) -> pd.DataFrame:
    """逐条应用 AND 过滤条件。

    参数:
        df: 已重命名列名的 DataFrame
        filters: [(column_cn, operator, value), ...] 列表

    返回:
        过滤后的 DataFrame

    NaN 值不满足任何比较条件，自动被排除。
    """
    for col_cn, op, val in filters:
        en_col = CN_TO_EN_COLUMN[col_cn]
        if op == ">":
            df = df[df[en_col] > val]
        elif op == ">=":
            df = df[df[en_col] >= val]
        elif op == "<":
            df = df[df[en_col] < val]
        elif op == "<=":
            df = df[df[en_col] <= val]
        elif op == "=":
            df = df[df[en_col] == val]
    return df


def _resolve_column(df: pd.DataFrame, col_name: str) -> str:
    """将列名解析为 DataFrame 中实际存在的列名。
    如果是中文名则翻译为英文，否则直接使用。
    """
    if col_name in CN_TO_EN_COLUMN:
        return CN_TO_EN_COLUMN[col_name]
    return col_name


def sort_dataframe(
    df: pd.DataFrame, sort_by: str, order: str
) -> pd.DataFrame:
    """排序 DataFrame。

    参数:
        df: 已重命名列名的 DataFrame
        sort_by: 排序列名（可为中文名或英文名）
        order: "desc" 或 "asc"

    返回:
        排序后的 DataFrame（NaN 总是排到最后）
    """
    en_col = _resolve_column(df, sort_by)
    ascending = order == "asc"
    return df.sort_values(
        by=en_col, ascending=ascending, na_position="last"
    )


def apply_top_n(df: pd.DataFrame, top_n: Optional[int]) -> pd.DataFrame:
    """取前 top_n 条。top_n 为 None 则返回全部。"""
    if top_n is None:
        return df
    return df.head(top_n)


def dataframe_to_records(df: pd.DataFrame) -> list:
    """将 DataFrame 转为 dict 列表，NaN → None，date → 字符串。"""
    # 将所有 NaN 替换为 None（JSON null）
    df = df.where(df.notna(), None)
    records = df.to_dict(orient="records")
    # 进一步确保 numpy NaN 被转换为 None
    for record in records:
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                record[key] = None
            elif key == "date" and hasattr(value, "strftime"):
                record[key] = value.strftime("%Y-%m-%d")
    return records


# ---- 输出 ----

def output_jsonl(df: pd.DataFrame, file=None) -> None:
    """以 JSONL 格式输出到 file（默认 stdout）"""
    if file is None:
        file = sys.stdout
    records = dataframe_to_records(df)
    for record in records:
        print(json.dumps(record, ensure_ascii=False), file=file)


def output_json(df: pd.DataFrame, file=None) -> None:
    """以 JSON 数组格式输出到 file（默认 stdout）"""
    if file is None:
        file = sys.stdout
    records = dataframe_to_records(df)
    print(json.dumps(records, ensure_ascii=False), file=file)


# ---- 主函数 ----

def main() -> None:
    parser = argparse.ArgumentParser(
        description="开放基金排行查询 — 基于东方财富数据中心"
    )
    parser.add_argument(
        "--symbol",
        default="全部",
        help=f"基金类型。合法值: {', '.join(SYMBOL_CHOICES)} (默认: 全部)",
    )
    parser.add_argument(
        "--filter",
        action="append",
        dest="filters_raw",
        default=[],
        help="数值过滤条件，格式: <列名><运算符><数值>。可重复指定 (AND 关系)。"
             "示例: --filter 近1月>10 --filter 近1年>30",
    )
    parser.add_argument(
        "--sort-by",
        default="近1年",
        help=f"排序字段。合法值: {', '.join(SORT_BY_CHOICES)} (默认: 近1年)",
    )
    parser.add_argument(
        "--order",
        default="desc",
        choices=["desc", "asc"],
        help="排序方向: desc (降序) 或 asc (升序) (默认: desc)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help="输出前 N 条记录 (默认: 输出全部)",
    )
    parser.add_argument(
        "--output",
        default="jsonl",
        choices=["jsonl", "json"],
        help="输出格式: jsonl 或 json (默认: jsonl)",
    )

    args = parser.parse_args()

    # 校验参数
    try:
        validate_symbol(args.symbol)
        validate_sort_by(args.sort_by)
        validate_order(args.order)
        if args.top_n is not None and args.top_n <= 0:
            raise ValueError(f"--top-n 必须是正整数，收到: {args.top_n}")
        validate_output(args.output)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(2)

    # 解析过滤条件
    parsed_filters = []
    for raw in args.filters_raw:
        try:
            parsed_filters.append(parse_filter(raw))
        except ValueError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(2)

    # 构建 filter 描述（用于日志）
    filter_desc = ", ".join(
        f"{col}{op}{val}" for col, op, val in parsed_filters
    )

    # 调用 API
    print(f"[INFO] 正在获取开放基金排行: symbol={args.symbol}", file=sys.stderr)
    try:
        import akshare as ak
        df = ak.fund_open_fund_rank_em(symbol=args.symbol)
    except Exception as e:
        print(f"[ERROR] API 调用失败: {e}", file=sys.stderr)
        sys.exit(2)

    if df.empty:
        print("[INFO] API 返回空数据", file=sys.stderr)
        if args.output == "json":
            print("[]")
        sys.exit(1)

    print(f"[INFO] 获取到 {len(df)} 条记录", file=sys.stderr)

    # 重命名列
    df = rename_columns(df)

    # 应用过滤
    if parsed_filters:
        df = apply_filters(df, parsed_filters)
        print(
            f"[INFO] 应用过滤条件: {filter_desc}; 过滤后 {len(df)} 条",
            file=sys.stderr,
        )
        if df.empty:
            print("[INFO] 过滤后无数据", file=sys.stderr)
            if args.output == "json":
                print("[]")
            sys.exit(1)

    # 排序
    order_text = "降序" if args.order == "desc" else "升序"
    top_n_text = f", 取前 {args.top_n} 条" if args.top_n else ""
    print(
        f"[INFO] 按 {args.sort_by} {order_text}排列{top_n_text}",
        file=sys.stderr,
    )
    df = sort_dataframe(df, args.sort_by, args.order)

    # 取 Top N
    df = apply_top_n(df, args.top_n)

    # 输出
    print(
        f"[INFO] 输出: {args.output} 格式, {len(df)} 条记录",
        file=sys.stderr,
    )
    if args.output == "json":
        output_json(df)
    else:
        output_jsonl(df)

    print("[INFO] 完成", file=sys.stderr)


if __name__ == "__main__":
    main()
