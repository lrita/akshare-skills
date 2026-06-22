# akshare-stock-search 设计规格

## 概述

将 `search_stock.py` 中的股票搜索逻辑从 `akshare_skill` 包中抽离为独立的 SKILL，直接调用 akshare 原始函数，使用 SQLite 本地缓存实现快速搜索。

## 目录结构

```
akshare-stock-search/
├── SKILL.md
└── scripts/
    ├── __init__.py
    └── search_stock.py          # 单文件自包含，~250 行
```

## CLI 接口

```bash
# 搜索股票（自动检查缓存 TTL，过期则刷新）
uv run python scripts/search_stock.py search 平安
uv run python scripts/search_stock.py search 000001 --market zh_a
uv run python scripts/search_stock.py search pabx --market zh_a    # 拼音首字母

# 手动刷新缓存
uv run python scripts/search_stock.py refresh
uv run python scripts/search_stock.py refresh --force
```

| 参数 | 说明 |
|------|------|
| `search <keyword>` | 搜索关键词 |
| `--market zh_a\|hk` | 限定市场，不传表示全部 |
| `--limit N` | 最大返回条数，默认 20 |
| `--output result.json` | 输出到文件，默认 stdout |
| `refresh` | 增量刷新（TTL 未过期则跳过） |
| `refresh --force` | 强制全量刷新 |

## 输出格式

JSON 数组到 stdout，日志到 stderr：

```json
[
  {"market": "zh_a", "code": "000001", "name": "平安银行", "match_type": "exact"},
  {"market": "zh_a", "code": "000002", "name": "万科A",   "match_type": "fuzzy"}
]
```

按 `match_type` 优先级 + `market`（A股优先）+ `code` 排序。

match_type 优先级：`exact > prefix > fuzzy > pinyin`
market 优先级：`zh_a > hk`

## 数据流

```
CLI search 平安
  ├─ 检查 ~/.cache/akshare-skill/stock_map.db
  │   └─ 不存在 或 updated_at > 7天 → 触发刷新
  ├─ 刷新阶段
  │   ├─ monkey-patch tqdm.__init__(disable=True)
  │   ├─ ak.stock_zh_a_spot() → 写入 stock_map (market=zh_a)
  │   └─ ak.stock_hk_spot()   → 写入 stock_map (market=hk)
  └─ 搜索阶段
      ├─ exact code match → name match → prefix → fuzzy → pinyin
      └─ 排序输出
```

## SQLite 表结构

```sql
CREATE TABLE stock_map (
    market TEXT NOT NULL,      -- zh_a / hk
    code   TEXT NOT NULL,      -- 000001
    name   TEXT NOT NULL,      -- 平安银行
    pinyin TEXT,               -- payh (首字母小写)
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market, code)
);
CREATE INDEX idx_stock_map_name ON stock_map(name);
CREATE INDEX idx_stock_map_code ON stock_map(code);
CREATE INDEX idx_stock_map_pinyin ON stock_map(pinyin);
```

## 缓存策略

- 缓存目录：`~/.cache/akshare-skill/stock_map.db`
- TTL：默认 7 天，环境变量 `AKSHARE_STOCK_CACHE_TTL_DAYS` 可覆盖
- 环境变量 `AKSHARE_SKILL_CACHE_DIR` 可覆盖缓存目录
- 刷新采用写入后替换模式：DELETE 旧数据 → INSERT 新数据，单事务提交

## tqdm 进度条屏蔽

在脚本开头 monkey-patch `tqdm.tqdm.__init__`，强制 `disable=True`：

```python
import tqdm
_original_tqdm_init = tqdm.tqdm.__init__

def _tqdm_init_patched(self, *args, disable=False, **kwargs):
    return _original_tqdm_init(self, *args, disable=True, **kwargs)

tqdm.tqdm.__init__ = _tqdm_init_patched
```

## 搜索优先级

每次搜索按以下顺序依次匹配，已出现的 (code, market) 组合自动跳过：

1. **exact code** — `WHERE code = ?`
2. **exact name** — `WHERE name = ?`
3. **prefix** — `WHERE code LIKE 'keyword%' OR name LIKE 'keyword%'`
4. **fuzzy** — `WHERE code LIKE '%keyword%' OR name LIKE '%keyword%'`
5. **pinyin** — `WHERE pinyin LIKE '%keyword%'`（仅当 keyword 为纯 ASCII 字母时触发）

## 错误处理与退出码

| 场景 | 行为 | exit code |
|------|------|-----------|
| 搜索成功 | JSON 输出到 stdout，日志到 stderr | 0 |
| 缓存不存在 + 所有数据源刷新失败 | stderr 输出错误，stdout 输出 `[]` | 1 |
| 单个市场刷新失败 | stderr warning，另一个市场数据仍可用 | 0 |
| 参数非法（空关键词、非法 market） | stderr 输出原因 | 2 |
| pypinyin 未安装 | 拼音字段为 NULL，拼音搜索无结果，不影响其他 | 0 |

## 依赖

- `akshare` — 必需，数据源
- `pypinyin` — 推荐安装，拼音搜索支持
- 其余全部 Python 3 标准库（sqlite3, argparse, json, dataclasses, datetime, pathlib）

## 约束

- 市场范围：只覆盖 A股（沪深京）+ 港股，不涉及美股
- 数据源函数：`ak.stock_zh_a_spot()`、`ak.stock_hk_spot()`
- 测试原则：集成测试直接调用真实 akshare API，不 mock
