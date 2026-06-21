#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
技术指标选股 — CLI 入口
支持 4 种工作模式：single / intersect / scan / full
"""
import sys
import os
import json
import argparse
from datetime import date, datetime, time

# Monkey-patch tqdm to disable progress bars globally.
# akshare uses tqdm progress bars that write to stderr, which can cause
# subprocess hangs in certain environments (e.g. CI, background shells).
# This must execute BEFORE importing engine (which imports fetcher → akshare).
os.environ.setdefault("TQDM_DISABLE", "1")
try:
    import tqdm as _tqdm_module
    _original_tqdm_init = _tqdm_module.tqdm.__init__

    def _patched_tqdm_init(self, *args, **kwargs):
        kwargs.setdefault("disable", True)
        _original_tqdm_init(self, *args, **kwargs)

    _tqdm_module.tqdm.__init__ = _patched_tqdm_init
except ImportError:
    pass

import engine


class _DateEncoder(json.JSONEncoder):
    """Custom JSON encoder that converts date/datetime objects to ISO strings."""

    def default(self, obj):
        if isinstance(obj, (date, datetime, time)):
            return obj.isoformat()
        return super().default(obj)


VALID_MODES = ("single", "intersect", "scan", "full")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="技术指标选股工作台 — 基于 akshare 20 个技术选股 API",
    )
    parser.add_argument(
        "--mode", required=True,
        choices=VALID_MODES,
        help="工作模式: single / intersect / scan / full",
    )
    parser.add_argument(
        "--indicator",
        help="指标名 (single: 单个; intersect: 逗号分隔多个)",
    )
    parser.add_argument(
        "--date",
        default=date.today().strftime("%Y%m%d"),
        help="日期 YYYYMMDD，默认今天 (作用于涨停板类+机构评级)",
    )
    parser.add_argument(
        "--symbol",
        action="append",
        default=[],
        help="格式 indicator_name=value，可重复。如 --symbol fetch_cxg_ths=一年新高",
    )
    parser.add_argument(
        "--signal-threshold",
        type=int,
        default=1,
        help="scan/full 中只返回 signal_count >= N 的股票，默认 1",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help="只返回前 N 条结果，默认全量",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="并发数，默认 8",
    )
    parser.add_argument(
        "--output",
        help="输出 JSON 文件路径，默认 stdout",
    )
    return parser.parse_args(argv)


def _parse_symbols(raw_symbols: list[str]) -> dict[str, str]:
    """解析 --symbol 参数为 dict"""
    result = {}
    for item in raw_symbols:
        if "=" in item:
            key, value = item.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def main() -> None:
    args = parse_args()

    # 参数校验
    if args.mode in ("single", "intersect") and not args.indicator:
        print(f"[ERROR] --mode {args.mode} 需要 --indicator 参数", file=sys.stderr)
        sys.exit(2)

    # 解析 symbol 参数
    symbols = _parse_symbols(args.symbol)

    # 路由到对应模式
    if args.mode == "single":
        sym = symbols.get(args.indicator)
        result = engine.run_single(args.indicator, symbol=sym, date=args.date)
        if args.top_n and result["data"]:
            result["data"] = result["data"][:args.top_n]
            result["count"] = len(result["data"])

    elif args.mode == "intersect":
        indicators = [s.strip() for s in args.indicator.split(",") if s.strip()]
        if not indicators:
            print("[ERROR] --indicator 不能为空", file=sys.stderr)
            sys.exit(2)
        # engine.run_intersect accepts symbol as a single str (backward compat),
        # so for intersect we pass date and max_workers; the symbols dict
        # is not directly supported by the engine for intersect mode
        result = engine.run_intersect(
            indicators, date=args.date, max_workers=args.workers,
        )
        if args.top_n and result["data"]:
            result["data"] = result["data"][:args.top_n]
            result["intersect_count"] = len(result["data"])

    elif args.mode == "scan":
        result = engine.run_scan(
            date=args.date,
            signal_threshold=args.signal_threshold,
            top_n=args.top_n,
            max_workers=args.workers,
        )

    elif args.mode == "full":
        result = engine.run_full(
            date=args.date,
            signal_threshold=args.signal_threshold,
            top_n=args.top_n,
            max_workers=args.workers,
        )

    else:
        print(f"[ERROR] 未知 mode: {args.mode}", file=sys.stderr)
        sys.exit(2)

    # 输出
    output_json = json.dumps(result, ensure_ascii=False, indent=2, cls=_DateEncoder)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
            f.write("\n")
    else:
        print(output_json)

    # exit code
    failed = result.get("errors", [])
    succeeded = result.get("succeeded_indicators", 0)

    if failed and succeeded == 0:
        os._exit(1)
    os._exit(0)


if __name__ == "__main__":
    main()
