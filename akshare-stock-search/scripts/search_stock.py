#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stock search with local SQLite cache. Fast code/name/keyword/pinyin lookup for A/HK stocks."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---- tqdm patch: silence progress bars from akshare ----
os.environ.setdefault("TQDM_DISABLE", "1")
try:
    import tqdm as _tqdm_mod
    _original_tqdm_init = _tqdm_mod.tqdm.__init__

    def _tqdm_init_patched(self, *args, disable=False, **kwargs):
        return _original_tqdm_init(self, *args, disable=True, **kwargs)

    _tqdm_mod.tqdm.__init__ = _tqdm_init_patched
except ImportError:
    pass

# ---- config ----
ENV_CACHE_DIR = "AKSHARE_SKILL_CACHE_DIR"
ENV_TTL_DAYS = "AKSHARE_STOCK_CACHE_TTL_DAYS"
DEFAULT_TTL_DAYS = 7


@dataclass(slots=True)
class StockResult:
    market: str       # zh_a / hk
    code: str         # 000001
    name: str         # 平安银行
    match_type: str   # exact / prefix / fuzzy / pinyin


def _cache_dir() -> Path:
    override = os.environ.get(ENV_CACHE_DIR)
    if override:
        return Path(override)
    return Path.home() / ".cache" / "akshare-skill"


def _db_path() -> Path:
    return _cache_dir() / "stock_map.db"


def _ttl_days() -> int:
    try:
        return int(os.environ.get(ENV_TTL_DAYS, str(DEFAULT_TTL_DAYS)))
    except ValueError:
        return DEFAULT_TTL_DAYS


def _get_conn(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_map (
            market TEXT NOT NULL,
            code   TEXT NOT NULL,
            name   TEXT NOT NULL,
            pinyin TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (market, code)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_map_name ON stock_map(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_map_code ON stock_map(code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_map_pinyin ON stock_map(pinyin)")
    return conn


def _needs_refresh(db_path: Path) -> bool:
    if not db_path.exists():
        return True
    ttl = _ttl_days()
    conn = _get_conn(db_path)
    try:
        row = conn.execute("SELECT MAX(updated_at) FROM stock_map").fetchone()
        if not row or not row[0]:
            return True
        latest = datetime.fromisoformat(row[0])
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl)
        return latest < cutoff
    except Exception:
        return True
    finally:
        conn.close()


def _pinyin_initials(name: str) -> str | None:
    try:
        from pypinyin import lazy_pinyin
        result = "".join(w[0].lower() for w in lazy_pinyin(name) if w)
        return result or None
    except ImportError:
        return None


def refresh_stock_cache(*, force: bool = False) -> dict:
    """Refresh the local stock cache from akshare data sources.

    Args:
        force: If True, always refresh regardless of TTL.

    Returns:
        dict with keys: markets, total, updated_at, failed (if any).
    """
    import akshare as ak

    db_path = _db_path()
    conn = _get_conn(db_path)

    markets_map = {
        "zh_a": ak.stock_zh_a_spot,
        "hk": ak.stock_hk_spot,
    }

    try:
        if not force and not _needs_refresh(db_path):
            row = conn.execute("SELECT COUNT(*) FROM stock_map").fetchone()
            ts = conn.execute("SELECT MAX(updated_at) FROM stock_map").fetchone()
            return {"markets": len(markets_map), "total": row[0], "updated_at": ts[0] or ""}

        now_ts = datetime.now(timezone.utc).isoformat()
        total = 0
        failed: list[str] = []

        for market, fetch_func in markets_map.items():
            try:
                df = fetch_func()
            except Exception as exc:
                failed.append(market)
                print(f"Warning: failed to refresh {market}: {exc}", file=sys.stderr)
                continue

            rows = []
            for _, row in df.iterrows():
                name = str(row.get("name", "") or row.get("名称", "") or row.get("中文名称", ""))
                code = str(row.get("code", "") or row.get("代码", ""))
                if not name or not code:
                    continue
                pinyin = _pinyin_initials(name)
                rows.append((market, code, name, pinyin, now_ts))

            conn.execute("DELETE FROM stock_map WHERE market = ?", (market,))
            conn.executemany(
                "INSERT INTO stock_map (market, code, name, pinyin, updated_at) VALUES (?,?,?,?,?)",
                rows,
            )
            conn.commit()
            total += len(rows)
            print(f"Refreshed {market}: {len(rows)} stocks", file=sys.stderr)

        if failed and len(failed) == len(markets_map):
            exists = conn.execute("SELECT COUNT(*) FROM stock_map").fetchone()[0]
            if exists == 0:
                raise RuntimeError(f"All markets failed to refresh: {failed}")

        result = {"markets": len(markets_map) - len(failed), "total": total, "updated_at": now_ts}
        if failed:
            result["failed"] = failed
        return result
    finally:
        conn.close()


def _search_db(conn: sqlite3.Connection, keyword: str, market: str | None) -> list[StockResult]:
    results: list[StockResult] = []
    seen: set[tuple[str, str]] = set()
    market_filter = "AND market = ?" if market else ""
    market_params = (market,) if market else ()

    # Priority 1: exact match on code
    for row in conn.execute(
        f"SELECT market, code, name FROM stock_map WHERE code = ? {market_filter}",
        (keyword,) + market_params,
    ):
        r = StockResult(row[0], row[1], row[2], "exact")
        results.append(r)
        seen.add((r.code, r.market))

    # Priority 2: exact match on name
    for row in conn.execute(
        f"SELECT market, code, name FROM stock_map WHERE name = ? {market_filter}",
        (keyword,) + market_params,
    ):
        if (row[1], row[0]) not in seen:
            r = StockResult(row[0], row[1], row[2], "exact")
            results.append(r)
            seen.add((r.code, r.market))

    # Priority 3: prefix match on code or name
    like_prefix = f"{keyword}%"
    for row in conn.execute(
        f"SELECT market, code, name FROM stock_map WHERE (code LIKE ? OR name LIKE ?) {market_filter}",
        (like_prefix, like_prefix) + market_params,
    ):
        if (row[1], row[0]) not in seen:
            r = StockResult(row[0], row[1], row[2], "prefix")
            results.append(r)
            seen.add((r.code, r.market))

    # Priority 4: fuzzy match (contains)
    like_fuzzy = f"%{keyword}%"
    for row in conn.execute(
        f"SELECT market, code, name FROM stock_map WHERE (code LIKE ? OR name LIKE ?) {market_filter}",
        (like_fuzzy, like_fuzzy) + market_params,
    ):
        if (row[1], row[0]) not in seen:
            r = StockResult(row[0], row[1], row[2], "fuzzy")
            results.append(r)
            seen.add((r.code, r.market))

    # Priority 5: pinyin match
    if keyword.isalpha() and keyword.isascii():
        like_pinyin = f"%{keyword.lower()}%"
        for row in conn.execute(
            f"SELECT market, code, name FROM stock_map WHERE pinyin LIKE ? {market_filter}",
            (like_pinyin,) + market_params,
        ):
            if (row[1], row[0]) not in seen:
                r = StockResult(row[0], row[1], row[2], "pinyin")
                results.append(r)
                seen.add((r.code, r.market))

    return _sort_results(results)


def _sort_results(results: list[StockResult]) -> list[StockResult]:
    market_rank = {"zh_a": 0, "hk": 1}
    match_rank = {"exact": 0, "prefix": 1, "fuzzy": 2, "pinyin": 3}
    return sorted(results, key=lambda r: (
        match_rank.get(r.match_type, 9),
        market_rank.get(r.market, 9),
        r.code,
    ))


def search_stock(keyword: str, *, market: str | None = None, limit: int = 20) -> list[StockResult]:
    """Search stocks by keyword in local SQLite cache.

    Searches in priority order: exact code, exact name, prefix, fuzzy, pinyin.

    Args:
        keyword: search keyword (code, name, or pinyin initials)
        market: limit to 'zh_a' or 'hk', None for all markets
        limit: max results to return (default 20)

    Returns:
        list of StockResult sorted by match_type priority
    """
    db_path = _db_path()
    if _needs_refresh(db_path):
        refresh_stock_cache(force=False)
    if not db_path.exists():
        return []
    conn = _get_conn(db_path)
    try:
        results = _search_db(conn, keyword, market)
        return results[:limit]
    finally:
        conn.close()


VALID_MARKETS = {"zh_a", "hk"}


def _validate_market(market: str | None) -> str | None:
    if market is None:
        return None
    if market not in VALID_MARKETS:
        print(f"[ERROR] 非法 market 参数: {market}，可选值: {', '.join(sorted(VALID_MARKETS))}", file=sys.stderr)
        sys.exit(2)
    return market


def _validate_keyword(keyword: str) -> str:
    if not keyword or not keyword.strip():
        print("[ERROR] 搜索关键词不能为空", file=sys.stderr)
        sys.exit(2)
    return keyword.strip()


def _output_json(data, output_path: str | None) -> None:
    json_str = json.dumps(data, ensure_ascii=False, default=str)
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_str)
                f.write("\n")
        except Exception as e:
            print(f"[ERROR] 写入输出文件失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        sys.stdout.write(json_str)
        sys.stdout.write("\n")
        sys.stdout.flush()


def cmd_search(args) -> int:
    keyword = _validate_keyword(args.keyword)
    market = _validate_market(args.market)

    try:
        results = search_stock(keyword, market=market, limit=args.limit)
    except RuntimeError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    output = [{"market": r.market, "code": r.code, "name": r.name, "match_type": r.match_type}
              for r in results]
    _output_json(output, args.output)
    return 0


def cmd_refresh(args) -> int:
    try:
        result = refresh_stock_cache(force=args.force)
    except RuntimeError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    _output_json(result, args.output)
    return 0


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="A股/港股股票搜索")
    subparsers = parser.add_subparsers(dest="command")

    p_search = subparsers.add_parser("search", help="搜索股票")
    p_search.add_argument("keyword", help="搜索关键词（代码、名称、拼音首字母）")
    p_search.add_argument("--market", choices=sorted(VALID_MARKETS), default=None, help="限定市场")
    p_search.add_argument("--limit", type=int, default=20, help="最大返回条数（默认 20）")
    p_search.add_argument("--output", default=None, help="输出 JSON 文件路径，默认 stdout")
    p_search.set_defaults(func=cmd_search)

    p_refresh = subparsers.add_parser("refresh", help="刷新本地缓存")
    p_refresh.add_argument("--force", action="store_true", help="强制全量刷新")
    p_refresh.add_argument("--output", default=None, help="输出 JSON 文件路径，默认 stdout")
    p_refresh.set_defaults(func=cmd_refresh)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(2)

    exit_code = args.func(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
