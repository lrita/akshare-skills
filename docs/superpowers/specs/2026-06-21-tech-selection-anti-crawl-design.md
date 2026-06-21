# akshare-tech-selection 反爬虫适配与限流改造 设计规格

## 概述

针对 akshare 技术选股 API 的反爬虫机制进行适配改造。核心变化：(1) 放弃依赖 akshare 库直接调用这 20 个 API，改为在 fetcher 层直接实现 HTTP 请求；(2) 引入全局速率限制器（每分钟最多 5 次）；(3) 被反爬拦截时输出 AI 可读提示并优雅退出。

## 架构

```
CLI (tech_selection.py)   — 移除 --workers 参数
    │
    ▼
engine.py                   — 去掉 ThreadPoolExecutor，改为顺序循环调用
    │  每次调用 fetcher 前 → rate_limiter.acquire()（阻塞等待直到允许）
    │
    ▼
ratelimit.py                — 全局滑动窗口限流器（每分钟 5 次 + 随机 jitter）
    │
    ▼
fetcher.py                  — 全部 20 个 API 直接 HTTP 请求，不依赖 akshare
    ├── _check_thx_blocked() — 反爬检测（403 / 验证页面），命中则输出提示 → os._exit(1)
    ├── _make_ths_headers()  — 同花顺 JS 解密 headers 生成
    ├── 11 个同花顺 fetcher   — requests + BeautifulSoup
    ├── 1 个巨潮 fetcher       — requests.post + py_mini_racer
    └── 8 个东方财富 fetcher   — requests + JSON API
```

**数据流向**：

```
CLI (argparse)
    │
    ▼
engine.py (按 mode 分发)
    │
    ├── rate_limiter.acquire()  ← 每次 API 调用前阻塞等待
    │
    ├── single   → 调用 1 个 fetcher → 直接输出
    ├── intersect → 顺序调用 N 个 fetcher → 取股票代码交集 → 输出
    ├── scan     → 顺序调用全部 20 个 fetcher → 按股票聚合信号 → 输出
    └── full     → scan + 详细指标级汇总统计 → 输出
    │
    ▼
fetcher.py (每个函数: HTTP 请求 → _check_thx_blocked → 解析 → standardize_output)
```

**依赖变化**：
- 移除：`akshare` 库依赖（fetcher 层不再 import akshare）
- 新增：`ratelimit.py` 文件（轻量，无需额外依赖）
- 保留：`pandas`、`py_mini_racer`、`requests`、`beautifulsoup4`

---

## RateLimiter 层设计（`ratelimit.py`，新建，约 40 行）

```python
class RateLimiter:
    """滑动窗口限流器：每分钟最多 5 次调用"""

    def __init__(self, max_calls_per_minute=5):
        self._max_calls = max_calls_per_minute
        self._timestamps = []  # 调用时间戳列表

    def acquire(self, min_jitter=0.5, max_jitter=2.0):
        """
        阻塞直到可以发起新调用。
        1. 清理 60 秒之前的记录
        2. 如果窗口内已有 max_calls 次 → sleep(剩余时间 + random(min_jitter, max_jitter))
        3. 否则直接放行 + 记录当前时间戳
        """
```

- 全局单例：`_RATE_LIMITER = RateLimiter(5)`，定义在 `ratelimit.py`
- 由 `engine.py` 导入，在每次调用 `_call_fetcher` 之前执行 `_RATE_LIMITER.acquire()`
- 限流对所有 20 个 API 统一生效（同花顺 + 东方财富 + 巨潮共享一个窗口）
- jitter 范围 0.5-2.0 秒，避免请求间隔过于规律

## 反爬检测设计（`fetcher.py`）

### 检测函数

```python
def _check_thx_blocked(response, api_name):
    """
    检测同花顺/巨潮 API 是否被反爬拦截。
    命中则输出 AI 可读提示并 os._exit(1)。
    """
    if response.status_code == 403:
        print(
            f"[BLOCKED] {api_name}: HTTP 403 Forbidden — "
            f"被反爬虫系统拦截，请等待 1 小时后重试",
            file=sys.stderr,
        )
        os._exit(1)
    # 部分情况返回 200 但内容是验证页面
    text_lower = response.text.lower()
    block_signals = ["验证", "滑块", "captcha", "请在下方输入"]
    if any(s in text_lower for s in block_signals) or len(response.text.strip()) < 200:
        print(
            f"[BLOCKED] {api_name}: 返回异常页面 — "
            f"被反爬虫系统拦截，请等待 1 小时后重试",
            file=sys.stderr,
        )
        os._exit(1)
```

### 适用范围

- 同花顺 11 个 API — 每次 requests 后立即调用
- 巨潮 1 个 API — 同上
- 东方财富 8 个 API — 不调用（JSON API，稳定）。但 `try/except` 兜底，HTTP 403 时返回 None + 记录 error

## API 重写清单（`fetcher.py`）

### 同花顺类（11 个，来自 `stock_technology_ths.py`）

| fetcher 名称 | 原始 akshare API | 数据来源 |
|-------------|-----------------|---------|
| `fetch_cxg_ths` | `stock_rank_cxg_ths` | `data.10jqka.com.cn` |
| `fetch_cxd_ths` | `stock_rank_cxd_ths` | `data.10jqka.com.cn` |
| `fetch_lxsz_ths` | `stock_rank_lxsz_ths` | `data.10jqka.com.cn` |
| `fetch_lxxd_ths` | `stock_rank_lxxd_ths` | `data.10jqka.com.cn` |
| `fetch_cxfl_ths` | `stock_rank_cxfl_ths` | `data.10jqka.com.cn` |
| `fetch_cxsl_ths` | `stock_rank_cxsl_ths` | `data.10jqka.com.cn` |
| `fetch_xstp_ths` | `stock_rank_xstp_ths` | `data.10jqka.com.cn` |
| `fetch_xxtp_ths` | `stock_rank_xxtp_ths` | `data.10jqka.com.cn` |
| `fetch_ljqs_ths` | `stock_rank_ljqs_ths` | `data.10jqka.com.cn` |
| `fetch_ljqd_ths` | `stock_rank_ljqd_ths` | `data.10jqka.com.cn` |
| `fetch_xzjp_ths` | `stock_rank_xzjp_ths` | `data.10jqka.com.cn` |

**改造方式**：复制 akshare 源码中对应函数的逻辑，改动：
1. `exit()` → `_check_thx_blocked() + os._exit(1)`
2. 去掉 tqdm 进度条
3. 保持原始列名、数据类型、返回 DataFrame
4. 经 `standardize_output()` 标准化后返回

### 巨潮类（1 个，来自 `stock_rank_forecast.py`）

| fetcher 名称 | 原始 akshare API | 数据来源 |
|-------------|-----------------|---------|
| `fetch_forecast_cninfo` | `stock_rank_forecast_cninfo` | `webapi.cninfo.com.cn` |

**改造方式**：复制 akshare 源码，加上 `_check_thx_blocked()`。

### 东方财富类（8 个，来自 `stock_ztb_em.py` 和 `stock_pankou_em.py`）

| fetcher 名称 | 原始 akshare API | 数据来源 |
|-------------|-----------------|---------|
| `fetch_zt_pool_strong` | `stock_zt_pool_strong_em` | `push2ex.eastmoney.com` |
| `fetch_zt_pool` | `stock_zt_pool_em` | `push2ex.eastmoney.com` |
| `fetch_zt_pool_dtgc` | `stock_zt_pool_dtgc_em` | `push2ex.eastmoney.com` |
| `fetch_zt_pool_sub_new` | `stock_zt_pool_sub_new_em` | `push2ex.eastmoney.com` |
| `fetch_zt_pool_previous` | `stock_zt_pool_previous_em` | `push2ex.eastmoney.com` |
| `fetch_zt_pool_zbgc` | `stock_zt_pool_zbgc_em` | `push2ex.eastmoney.com` |
| `fetch_board_change` | `stock_board_change_em` | `push2ex.eastmoney.com` |
| `fetch_changes` | `stock_changes_em` | `push2ex.eastmoney.com` |

**改造方式**：复制 akshare 源码，纯 JSON API，无需反爬检测。HTTP 403 时 `try/except` 返回 None。

## fetcher.py 结构调整

### 删除

- `import akshare as ak`
- `_make_fetcher` 闭包函数
- 模块末尾的 `for _ind in ALL_INDICATORS` 动态生成循环
- `ALL_INDICATORS` 中每个条目的 `arg_map` 字段

### 改为

- 20 个显式定义的 `fetch_xxx()` 函数（每个 ~30-80 行）
- `ALL_INDICATORS` 保留为元数据注册表（用于 scan/full 遍历），但仅保留 `name`、`api`、`category`、`categories`、`code_col`、`name_col`、`needs_symbol`、`default_symbol`、`needs_date` 字段，不再需要 `arg_map`
- `__all__` 列表保持不变

### 新增私有函数

- `_get_file_content_ths(file)` — 获取同花顺 JS 文件内容
- `_make_ths_headers(js_code)` — 生成带 Cookie 的 headers
- `_check_thx_blocked(response, api_name)` — 反爬检测

## Engine 层改动（`engine.py`）

### 删除

- `from concurrent.futures import ThreadPoolExecutor, as_completed`
- `_call_fetchers_concurrent` 函数
- 所有 `max_workers` 参数（函数签名 + 调用处）

### 新增

- `from ratelimit import _RATE_LIMITER`
- `_call_fetchers_sequential` 函数

```python
def _call_fetchers_sequential(
    ind_names: list[str],
    symbols: dict[str, str] | None = None,
    date: str | None = None,
):
    """顺序调用多个 fetcher（受全局 RateLimiter 管控），返回 (results_dict, errors_list)"""
    if symbols is None:
        symbols = {}
    results = {}
    errors = []

    for ind_name in ind_names:
        _RATE_LIMITER.acquire()
        sym = symbols.get(ind_name)
        ind_name, result, error = _call_fetcher(ind_name, sym, date)
        if error:
            errors.append(error)
        if result:
            results[ind_name] = result

    return results, errors
```

### 函数签名变化

```python
# 旧
run_intersect(indicators, symbol=None, date=None, max_workers=8)
run_scan(symbol=None, date=None, max_workers=8, ...)
run_full(symbol=None, date=None, max_workers=8, ...)

# 新
run_intersect(indicators, symbol=None, date=None)
run_scan(symbol=None, date=None, ...)
run_full(symbol=None, date=None, ...)
```

## CLI 改动（`tech_selection.py`）

### 删除

- `--workers` 参数
- 所有对 `engine.run_*` 传 `max_workers` 的调用

### 其他

- tqdm monkey-patch 可以移除（fetcher 不再通过 akshare 调用，但保留也无害）
- 其余逻辑不变

## SKILL.md 改动

- 删除 `--workers` 参数说明
- `--workers` 使用示例需同步清理
- 新增"速率限制"说明节："所有 API 调用受全局速率限制，每分钟最多 5 次，调用间隔随机 0.5-2.0 秒"
- 新增"反爬虫"说明："当遇到 HTTP 403 或验证页面时，程序会输出被拦截提示并退出，请等待 1 小时后重试"

## 错误处理

| 场景 | 行为 |
|------|------|
| 同花顺 API HTTP 403 | 输出 BLOCKED 提示 → `os._exit(1)` |
| 同花顺 API 返回验证页面 | 输出 BLOCKED 提示 → `os._exit(1)` |
| 东方财富 API HTTP 403 | try/except 捕获 → 返回 None → 记录 error |
| 东方财富 API 返回空数据 | 返回 None → 记录 null_data error |
| 全部 API 返回 None | exit code 1，输出 errors |
| 参数错误 | exit code 2，stderr 输出原因 |
| 超过速率限制 | `rate_limiter.acquire()` 自动等待，不报错 |

### exit code

| code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 被反爬拦截 或 全部 API 失败 |
| 2 | 参数错误 |

## 测试策略

### 单元测试

- `test_fetcher.py`：mock `requests`，验证各 fetcher 的 HTML/JSON 解析逻辑
- `test_fetcher.py`：mock `requests` 返回 403/验证页面，验证 `_check_thx_blocked` 触发 `os._exit(1)`
- `test_engine.py`：mock fetcher，验证 `run_single`/`run_intersect` 中 rate_limiter 被调用
- `test_ratelimit.py`：新建，验证滑动窗口限流逻辑

### 集成测试

- 保持现有 `test_integration.py` 结构
- 超时需加长（顺序调用 20 个 API，按 5 次/分钟 = 至少 4 分钟）

### 删除的测试

- `TestCLIParsing` 中 `test_parse_workers_default` — `--workers` 参数已移除

## 文件清单

| 操作 | 文件 |
|------|------|
| 新建 | `akshare-tech-selection/scripts/ratelimit.py` |
| 重写 | `akshare-tech-selection/scripts/fetcher.py`（20 个显式 fetcher + 反爬检测） |
| 修改 | `akshare-tech-selection/scripts/engine.py`（并发 → 顺序，+rate_limiter） |
| 修改 | `akshare-tech-selection/scripts/tech_selection.py`（去掉 --workers） |
| 修改 | `akshare-tech-selection/SKILL.md`（去掉 --workers，新增限流说明） |
| 修改 | `akshare-tech-selection/scripts/tests/test_fetcher.py`（适配新 fetcher + 反爬测试） |
| 修改 | `akshare-tech-selection/scripts/tests/test_engine.py`（添加 rate_limiter 测试，删除 workers 测试） |
| 新建 | `akshare-tech-selection/scripts/tests/test_ratelimit.py` |

## 依赖变化

```bash
# 不再需要
uv pip install akshare

# 仍然需要
uv pip install pandas py_mini_racer requests beautifulsoup4
```

注意：`py_mini_racer` 是 akshare 的依赖，如果用户已安装 akshare 则已具备；如果去掉 akshare 则需要显式安装。实际建议保留 akshare 依赖（用于 `ths.js` 和 `cninfo.js` 文件查找），但从 fetcher 中不再 import akshare。
