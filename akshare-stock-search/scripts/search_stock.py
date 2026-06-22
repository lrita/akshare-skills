#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stock search with local SQLite cache. Fast code/name/keyword/pinyin lookup for A/HK stocks."""
from __future__ import annotations

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
