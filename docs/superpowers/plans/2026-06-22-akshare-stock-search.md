# akshare-stock-search 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将股票搜索逻辑从 akshare_skill 包抽离为独立 SKILL，直接调用 akshare 原始函数，SQLite 缓存 + TTL 过期，支持 A 股和港股搜索。

**架构：** 单文件 `scripts/search_stock.py`，~250 行，包含缓存层、数据刷新、搜索匹配、CLI 四层逻辑。SKILL.md 文档遵循现有 skill 风格。

**技术栈：** Python 3, akshare, pypinyin, SQLite (标准库)

---

### 任务 1：创建目录结构和 SKILL.md

**文件：**
- 创建：`akshare-stock-search/SKILL.md`
- 创建：`akshare-stock-search/scripts/__init__.py`

- [ ] **步骤 1：创建空 __init__.py**

```bash
mkdir -p akshare-stock-search/scripts
touch akshare-stock-search/scripts/__init__.py
```

- [ ] **步骤 2：编写 SKILL.md**

```markdown
---
name: akshare-stock-search
description: Use when the user needs to search for A-stock or HK-stock by code, name, keyword, or pinyin initials. Provides fast local SQLite-cached lookup with exact/prefix/fuzzy/pinyin matching. Use this before fetching any stock data that requires a stock code.
---

# 股票搜索

## 概述

通过代码、名称、关键词或拼音首字母搜索 A 股（沪深京）和港股，基于本地 SQLite 缓存实现毫秒级响应。缓存自动过期刷新（默认 7 天 TTL）。

## 使用方式

```bash
# 搜索股票
uv run python scripts/search_stock.py search 平安
uv run python scripts/search_stock.py search 000001 --market zh_a
uv run python scripts/search_stock.py search pabx --market zh_a

# 手动刷新缓存
uv run python scripts/search_stock.py refresh
uv run python scripts/search_stock.py refresh --force
```

## 参数说明

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `search <keyword>` | 是 | - | 搜索关键词 |
| `--market zh_a\|hk` | 否 | 全部 | 限定市场 |
| `--limit N` | 否 | 20 | 最大返回条数 |
| `--output path` | 否 | stdout | 输出 JSON 文件路径 |
| `refresh` | - | - | 增量刷新缓存 |
| `refresh --force` | - | - | 强制全量刷新 |

## 输出格式

JSON 数组到 stdout，按匹配优先级 + 市场 + 代码排序：

```json
[
  {"market": "zh_a", "code": "000001", "name": "平安银行", "match_type": "exact"},
  {"market": "zh_a", "code": "000002", "name": "万科A",   "match_type": "fuzzy"}
]
```

match_type: exact > prefix > fuzzy > pinyin

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AKSHARE_SKILL_CACHE_DIR` | `~/.cache/akshare-skill` | 缓存目录 |
| `AKSHARE_STOCK_CACHE_TTL_DAYS` | `7` | 缓存有效期（天） |

## 退出码

| code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 数据源全部失败 |
| 2 | 参数非法 |

## 依赖

```bash
uv pip install akshare pypinyin
```

pypinyin 为推荐依赖，未安装时拼音搜索自动跳过。
```

- [ ] **步骤 3：Commit**

```bash
git add akshare-stock-search/SKILL.md akshare-stock-search/scripts/__init__.py
git commit -m "docs: add SKILL.md for akshare-stock-search"
```

---

### 任务 2：实现缓存层（SQLite + TTL + 环境变量）

**文件：**
- 创建：`akshare-stock-search/scripts/search_stock.py`

- [ ] **步骤 1：编写集成测试（真实调用 akshare）**

创建测试文件 `akshare-stock-search/scripts/tests/__init__.py` 和 `akshare-stock-search/scripts/tests/test_search_stock.py`：

```bash
mkdir -p akshare-stock-search/scripts/tests
touch akshare-stock-search/scripts/tests/__init__.py
```

```python
# akshare-stock-search/scripts/tests/test_search_stock.py
"""Integration tests for search_stock.py — real akshare calls, no mocking."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "search_stock.py"


def _run(*args, **kwargs):
    """Run search_stock.py with given args, return (exit_code, stdout, stderr)."""
    env = os.environ.copy()
    env.update(kwargs.pop("env", {}))
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        capture_output=True, text=True, timeout=120, env=env, **kwargs
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def test_search_exact_code():
    """搜索精确代码应返回 exact 匹配。"""
    code, stdout, stderr = _run("search", "000001")
    assert code == 0, f"exit={code} stderr={stderr}"
    results = json.loads(stdout)
    assert len(results) >= 1
    # 000001 应该是平安银行
    top = results[0]
    assert top["code"] == "000001"
    assert top["match_type"] == "exact"


def test_search_exact_name():
    """搜索完整名称应返回 exact 匹配。"""
    code, stdout, stderr = _run("search", "平安银行")
    assert code == 0, f"exit={code} stderr={stderr}"
    results = json.loads(stdout)
    assert len(results) >= 1
    names = [r["name"] for r in results]
    assert "平安银行" in names


def test_search_fuzzy():
    """模糊搜索应返回包含关键词的结果。"""
    code, stdout, stderr = _run("search", "平安")
    assert code == 0, f"exit={code} stderr={stderr}"
    results = json.loads(stdout)
    assert len(results) >= 2  # 平安银行、中国平安 等
    for r in results:
        assert "平安" in r["name"]


def test_search_market_filter():
    """--market 应限定搜索范围。"""
    code, stdout, stderr = _run("search", "000001", "--market", "zh_a")
    assert code == 0, f"exit={code} stderr={stderr}"
    results = json.loads(stdout)
    for r in results:
        assert r["market"] == "zh_a"


def test_search_limit():
    """--limit 应限制返回条数。"""
    code, stdout, stderr = _run("search", "银行", "--limit", "5")
    assert code == 0, f"exit={code} stderr={stderr}"
    results = json.loads(stdout)
    assert len(results) <= 5


def test_search_output_file():
    """--output 应将结果写入文件。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        tmp_path = f.name
    try:
        code, stdout, stderr = _run("search", "000001", "--output", tmp_path)
        assert code == 0
        with open(tmp_path) as f:
            data = json.load(f)
        assert len(data) >= 1
        assert data[0]["code"] == "000001"
    finally:
        os.unlink(tmp_path)


def test_search_empty_result():
    """不存在的股票应返回空数组。"""
    code, stdout, stderr = _run("search", "ZZZZZZZZ_NOT_EXIST")
    assert code == 0, f"exit={code} stderr={stderr}"
    results = json.loads(stdout)
    assert results == []


def test_search_invalid_market():
    """非法 market 参数应 exit 2。"""
    code, stdout, stderr = _run("search", "000001", "--market", "xxx")
    assert code == 2, f"exit={code} stderr={stderr}"


def test_search_empty_keyword():
    """空关键词应 exit 2。"""
    code, stdout, stderr = _run("search", "")
    assert code == 2, f"exit={code} stderr={stderr}"


def test_refresh_force():
    """refresh --force 应成功执行。"""
    code, stdout, stderr = _run("refresh", "--force")
    assert code == 0, f"exit={code} stderr={stderr}"
    result = json.loads(stdout)
    assert "total" in result
    assert result["total"] > 0


def test_refresh_incremental():
    """refresh（不强制）应成功执行（首次或TTL未过期）。"""
    code, stdout, stderr = _run("refresh")
    assert code == 0, f"exit={code} stderr={stderr}"
    result = json.loads(stdout)
    assert "total" in result


def test_pinyin_search():
    """拼音搜索应返回匹配结果。"""
    code, stdout, stderr = _run("search", "payh")
    assert code == 0, f"exit={code} stderr={stderr}"
    results = json.loads(stdout)
    # payh = 平安银行拼音首字母
    if results:  # pypinyin 可选，未安装时为空
        names = [r["name"] for r in results]
        assert "平安银行" in names


def test_sort_order():
    """搜索结果应按 match_type 优先级排序。"""
    code, stdout, stderr = _run("search", "平安")
    assert code == 0, f"exit={code} stderr={stderr}"
    results = json.loads(stdout)
    match_types = [r["match_type"] for r in results]
    # exact 应排在 fuzzy/pinyin 前面
    for i in range(len(match_types) - 1):
        priority = {"exact": 0, "prefix": 1, "fuzzy": 2, "pinyin": 3}
        assert priority.get(match_types[i], 9) <= priority.get(match_types[i + 1], 9), \
            f"排序错误: {match_types[i]} before {match_types[i+1]} at index {i}"
```

- [ ] **步骤 2：运行测试验证失败**

```bash
python -m pytest akshare-stock-search/scripts/tests/test_search_stock.py -v
```

预期：全部 FAIL，因为 `search_stock.py` 还不存在。

- [ ] **步骤 3：编写缓存层代码**

```python
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
```

- [ ] **步骤 4：运行测试，确认缓存层代码可以导入（搜索功能尚不可用）**

```bash
python -c "import sys; sys.path.insert(0, 'akshare-stock-search/scripts'); from search_stock import _cache_dir, _db_path, _get_conn, StockResult; print('import OK')"
```

预期：`import OK`

- [ ] **步骤 5：Commit**

```bash
git add akshare-stock-search/scripts/search_stock.py
git commit -m "feat: add stock cache layer with tqdm patch and configurable TTL"
```

---

### 任务 3：实现数据刷新逻辑

**文件：**
- 修改：`akshare-stock-search/scripts/search_stock.py`（追加函数）

- [ ] **步骤 1：运行现有测试确认失败**

```bash
python -m pytest akshare-stock-search/scripts/tests/test_search_stock.py::test_refresh_force -v
```

预期：FAIL（refresh 命令还未实现）

- [ ] **步骤 2：追加刷新函数到 search_stock.py**

```python
def _needs_refresh(db_path: Path) -> bool:
    if not db_path.exists():
        return True
    ttl = _ttl_days()
    conn = sqlite3.connect(str(db_path))
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
        return "".join(w[0].lower() for w in lazy_pinyin(name) if w)
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
                name = str(row.get("name", "") or row.get("名称", ""))
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
```

- [ ] **步骤 3：运行 refresh 测试确认通过**

```bash
python -m pytest akshare-stock-search/scripts/tests/test_search_stock.py::test_refresh_force akshare-stock-search/scripts/tests/test_search_stock.py::test_refresh_incremental -v --timeout=120
```

预期：PASS

- [ ] **步骤 4：Commit**

```bash
git add akshare-stock-search/scripts/search_stock.py
git commit -m "feat: add refresh_stock_cache from akshare data sources"
```

---

### 任务 4：实现搜索逻辑

**文件：**
- 修改：`akshare-stock-search/scripts/search_stock.py`（追加搜索函数）

- [ ] **步骤 1：运行搜索测试确认失败**

```bash
python -m pytest akshare-stock-search/scripts/tests/test_search_stock.py::test_search_exact_code -v
```

预期：FAIL（search 函数还不存在）

- [ ] **步骤 2：追加搜索函数到 search_stock.py**

```python
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
```

- [ ] **步骤 3：运行所有搜索测试确认通过**

```bash
python -m pytest akshare-stock-search/scripts/tests/test_search_stock.py -v --timeout=120 -k "search"
```

预期：PASS

- [ ] **步骤 4：Commit**

```bash
git add akshare-stock-search/scripts/search_stock.py
git commit -m "feat: add stock search with exact/prefix/fuzzy/pinyin matching"
```

---

### 任务 5：实现 CLI

**文件：**
- 修改：`akshare-stock-search/scripts/search_stock.py`（追加 CLI 代码，尾部）

- [ ] **步骤 1：运行完整测试确认 CLI 功能缺失**

```bash
python -m pytest akshare-stock-search/scripts/tests/test_search_stock.py -v --timeout=120
```

预期：大部分 FAIL（CLI 入口还未实现）

- [ ] **步骤 2：追加 CLI 到 search_stock.py 末尾**

```python
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
```

- [ ] **步骤 3：运行全部测试确认通过**

```bash
python -m pytest akshare-stock-search/scripts/tests/test_search_stock.py -v --timeout=120
```

预期：全部 PASS

- [ ] **步骤 4：Commit**

```bash
git add akshare-stock-search/scripts/search_stock.py akshare-stock-search/scripts/tests/test_search_stock.py
git commit -m "feat: add CLI with search and refresh subcommands"
```

---

### 任务 6：最终验证与手动测试

- [ ] **步骤 1：运行全部测试（含集成测试）**

```bash
python -m pytest akshare-stock-search/scripts/tests/ -v --timeout=120
```

预期：全部 PASS

- [ ] **步骤 2：手动运行 CLI 验证**

```bash
# 先刷新缓存
python akshare-stock-search/scripts/search_stock.py refresh --force

# 精确搜索
python akshare-stock-search/scripts/search_stock.py search 000001 --limit 3

# 名称搜索
python akshare-stock-search/scripts/search_stock.py search 平安 --limit 5

# 市场过滤 + 拼音
python akshare-stock-search/scripts/search_stock.py search payh --market zh_a

# 验证输出到文件
python akshare-stock-search/scripts/search_stock.py search 000001 --output /tmp/test_search.json
```

每次命令后确认：
- stdout 输出合法 JSON
- exit code 为 0
- 无 tqdm 进度条干扰

- [ ] **步骤 3：Commit 最终调整（如有）**

```bash
git add -A
git commit -m "test: add integration tests and final verification"
```
