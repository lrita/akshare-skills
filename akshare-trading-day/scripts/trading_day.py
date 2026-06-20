#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A股交易日判断脚本
基于新浪财经交易日历，提供 check/next/count 三个查询功能
"""
import sys
import json
import argparse
from datetime import date, datetime


# 交易日集合（懒加载，首次调用时从 akshare 初始化）
_trade_dates: set[date] = set()
_loaded: bool = False


def _load_trade_dates() -> None:
    """从 akshare 加载交易日历到内存集合"""
    global _trade_dates, _loaded
    if _loaded:
        return
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        _trade_dates.update(df["trade_date"].tolist())
        _loaded = True
    except Exception as e:
        raise RuntimeError(f"无法加载交易日历数据: {e}")


def is_trading_day(d: date) -> bool:
    """判断给定日期是否为 A 股交易日

    参数:
        d: 待判断的日期

    返回:
        bool: 是交易日返回 True，否则 False
    """
    _load_trade_dates()
    return d in _trade_dates


def next_trading_day(d: date) -> date | None:
    """获取下一个交易日（含当日）

    参数:
        d: 参考日期

    返回:
        date | None: 最近的下一个交易日，超出数据范围返回 None
    """
    _load_trade_dates()
    candidates = [td for td in _trade_dates if td >= d]
    if not candidates:
        return None
    return min(candidates)


def count_trading_days(start: date, end: date) -> int:
    """统计给定范围内的交易日数量（含起止日）

    参数:
        start: 开始日期
        end: 结束日期

    返回:
        int: 交易日数量
    """
    _load_trade_dates()
    if start > end:
        return 0
    return sum(1 for td in _trade_dates if start <= td <= end)


def parse_date(s: str) -> date:
    """解析 YYYY-MM-DD 日期字符串

    参数:
        s: 日期字符串

    返回:
        date: 解析结果

    异常:
        ValueError: 格式不合法
    """
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def cmd_check(args: argparse.Namespace) -> None:
    """check 子命令"""
    try:
        d = parse_date(args.date)
        _load_trade_dates()
    except ValueError:
        json.dump({"error": "invalid_date_format", "detail": f"期望 YYYY-MM-DD，收到 {args.date}"},
                  sys.stdout, ensure_ascii=False)
        sys.exit(1)
    except RuntimeError as e:
        json.dump({"error": "data_load_error", "detail": str(e)},
                  sys.stdout, ensure_ascii=False)
        sys.exit(2)

    json.dump({"is_trading_day": is_trading_day(d)}, sys.stdout, ensure_ascii=False)


def cmd_next(args: argparse.Namespace) -> None:
    """next 子命令"""
    try:
        d = parse_date(args.date)
        _load_trade_dates()
    except ValueError:
        json.dump({"error": "invalid_date_format", "detail": f"期望 YYYY-MM-DD，收到 {args.date}"},
                  sys.stdout, ensure_ascii=False)
        sys.exit(1)
    except RuntimeError as e:
        json.dump({"error": "data_load_error", "detail": str(e)},
                  sys.stdout, ensure_ascii=False)
        sys.exit(2)

    result = next_trading_day(d)
    if result is None:
        json.dump({"next_trading_day": None, "error": "out_of_range"},
                  sys.stdout, ensure_ascii=False)
    else:
        json.dump({"next_trading_day": result.strftime("%Y-%m-%d")},
                  sys.stdout, ensure_ascii=False)


def cmd_count(args: argparse.Namespace) -> None:
    """count 子命令"""
    try:
        start = parse_date(args.start)
        end = parse_date(args.end)
        _load_trade_dates()
    except ValueError:
        json.dump({"error": "invalid_date_format", "detail": "期望 YYYY-MM-DD 格式"},
                  sys.stdout, ensure_ascii=False)
        sys.exit(1)
    except RuntimeError as e:
        json.dump({"error": "data_load_error", "detail": str(e)},
                  sys.stdout, ensure_ascii=False)
        sys.exit(2)

    json.dump({"count": count_trading_days(start, end)}, sys.stdout, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="A股交易日查询")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_check = subparsers.add_parser("check", help="判断是否为交易日")
    p_check.add_argument("date", help="日期 (YYYY-MM-DD)")
    p_check.set_defaults(func=cmd_check)

    p_next = subparsers.add_parser("next", help="查询下一个交易日")
    p_next.add_argument("date", help="参考日期 (YYYY-MM-DD)")
    p_next.set_defaults(func=cmd_next)

    p_count = subparsers.add_parser("count", help="统计范围内交易日数量")
    p_count.add_argument("start", help="开始日期 (YYYY-MM-DD)")
    p_count.add_argument("end", help="结束日期 (YYYY-MM-DD)")
    p_count.set_defaults(func=cmd_count)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
