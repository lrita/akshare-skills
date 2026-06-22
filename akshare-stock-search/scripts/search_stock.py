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
