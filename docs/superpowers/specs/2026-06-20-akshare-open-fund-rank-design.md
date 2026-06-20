# 开放基金排行 — 设计规格

## 概述

基于 akshare `fund_open_fund_rank_em` API，获取东方财富网开放基金排行数据，包含基金代码、净值、多周期涨幅等信息。支持按基金类型筛选、按任意指标排序、取 Top N，以 JSON 输出，供 AI Agent 检索和分析基金表现。

## CLI 接口

```bash
uv run python scripts/open_fund_rank.py \
  --symbol 全部 \
  --sort-by 近1年 \
  --order desc \
  --top-n 20 \
  --output jsonl
```

- JSON 输出到 stdout，日志/进度到 stderr
- 无缓存，每次实时查询，保证数据最新
- exit code: 0 成功, 1 空数据, 2 参数错误/API 不可用

## 参数说明

### `--symbol`（可选，默认 `全部`）

基金类型，直接传递给 akshare API 的 `symbol` 参数。

**合法值**:

| 值 | 说明 | 大约行数 |
|---|---|---|
| `全部` | 所有类型 | ~19750 |
| `股票型` | 股票型基金 | ~1060 |
| `混合型` | 混合型基金 | ~8380 |
| `债券型` | 债券型基金 | ~4770 |
| `指数型` | 指数型基金 | ~4340 |
| `QDII` | QDII 基金 | ~220 |
| `FOF` | FOF 基金 | ~980 |

### `--sort-by`（可选，默认 `近1年`）

排序字段。**合法值**:

| 值 | 输出字段名 | 说明 |
|---|---|---|
| `日增长率` | `daily_return` | 日涨跌幅 |
| `近1周` | `1w_return` | 近 1 周涨跌幅 |
| `近1月` | `1m_return` | 近 1 月涨跌幅 |
| `近3月` | `3m_return` | 近 3 月涨跌幅 |
| `近6月` | `6m_return` | 近 6 月涨跌幅 |
| `近1年` | `1y_return` | 近 1 年涨跌幅 |
| `近2年` | `2y_return` | 近 2 年涨跌幅 |
| `近3年` | `3y_return` | 近 3 年涨跌幅 |
| `今年来` | `ytd_return` | 今年以来涨跌幅 |
| `成立来` | `since_inception_return` | 成立以来涨跌幅 |
| `单位净值` | `unit_net_value` | 单位净值 |
| `累计净值` | `cumulative_net_value` | 累计净值 |

### `--order`（可选，默认 `desc`）

排序方向。**合法值**: `desc`（降序，从大到小）, `asc`（升序，从小到大）。

### `--top-n`（可选，默认无限制）

输出前 N 条记录。必须是正整数。不指定则输出全部。

### `--output`（可选，默认 `jsonl`）

输出格式。**合法值**:

| 值 | 格式 |
|---|---|
| `jsonl` | 每行一个 JSON 对象 |
| `json` | 单个 JSON 数组 |

## 核心流程

```
main()
  ├── parse_args()                           # argparse 解析参数
  ├── validate_args()                         # 校验参数合法性
  ├── df = ak.fund_open_fund_rank_em(symbol)  # 调用 API
  │     └── 失败 → exit(2)
  ├── rename columns                          # 中文列名 → 英文列名
  │     └── 仅保留 16 个输出字段
  ├── df = df.sort_values(sort_by, order)    # 排序
  ├── if top_n: df = df.head(top_n)          # 取 Top N
  └── output(df, format)                     # JSON 或 JSONL 输出到 stdout
```

**注意**：不实现 `--filter-type` 参数。`--symbol` 本身即可按类型筛选，无需二次过滤。若用户想从全部中提取某类型，直接指定 `--symbol 股票型` 等即可。

## 输出格式

### 输出字段（共 16 列）

| 字段 | 类型 | 说明 |
|---|---|---|
| `fund_code` | string | 基金代码 |
| `fund_name` | string | 基金简称 |
| `date` | string | 净值日期 (YYYY-MM-DD) |
| `unit_net_value` | float/null | 单位净值 |
| `cumulative_net_value` | float/null | 累计净值 |
| `daily_return` | float/null | 日增长率 (%) |
| `1w_return` | float/null | 近 1 周涨幅 (%) |
| `1m_return` | float/null | 近 1 月涨幅 (%) |
| `3m_return` | float/null | 近 3 月涨幅 (%) |
| `6m_return` | float/null | 近 6 月涨幅 (%) |
| `1y_return` | float/null | 近 1 年涨幅 (%) |
| `2y_return` | float/null | 近 2 年涨幅 (%) |
| `3y_return` | float/null | 近 3 年涨幅 (%) |
| `ytd_return` | float/null | 今年以来涨幅 (%) |
| `since_inception_return` | float/null | 成立来涨幅 (%) |
| `fee` | string | 手续费 (如 `0.15%`) |

- **NaN 处理**: API 返回的 NaN 统一输出为 JSON `null`
- **去掉的列**: `序号`（无业务意义）、`自定义`（空列）
- `date` 列：API 返回格式如 `2026-06-18`，直接透传

### jsonl 输出示例（默认）

```json
{"fund_code":"014915","fund_name":"财通匠心优选一年持有混合A","date":"2026-06-18","unit_net_value":4.0954,"cumulative_net_value":4.0954,"daily_return":2.83,"1w_return":23.34,"1m_return":67.32,"3m_return":145.88,"6m_return":173.96,"1y_return":473.75,"2y_return":431.94,"3y_return":394.97,"ytd_return":163.10,"since_inception_return":309.54,"fee":"0.15%"}
{"fund_code":"017490","fund_name":"财通景气甄选一年持有期混合A","date":"2026-06-18","unit_net_value":6.5682,"cumulative_net_value":6.5682,"daily_return":3.08,"1w_return":22.52,"1m_return":65.68,"3m_return":143.70,"6m_return":170.39,"1y_return":472.89,"2y_return":454.61,"3y_return":null,"ytd_return":159.83,"since_inception_return":556.82,"fee":"0.15%"}
```

### json 输出示例

```json
[
  {"fund_code":"014915","fund_name":"财通匠心优选一年持有混合A","date":"2026-06-18","unit_net_value":4.0954,"cumulative_net_value":4.0954,"daily_return":2.83,"1w_return":23.34,"1m_return":67.32,"3m_return":145.88,"6m_return":173.96,"1y_return":473.75,"2y_return":431.94,"3y_return":394.97,"ytd_return":163.10,"since_inception_return":309.54,"fee":"0.15%"},
  {"fund_code":"017490","fund_name":"财通景气甄选一年持有期混合A","date":"2026-06-18","unit_net_value":6.5682,"cumulative_net_value":6.5682,"daily_return":3.08,"1w_return":22.52,"1m_return":65.68,"3m_return":143.70,"6m_return":170.39,"1y_return":472.89,"2y_return":454.61,"3y_return":null,"ytd_return":159.83,"since_inception_return":556.82,"fee":"0.15%"}
]
```

**注意**：`unit_net_value` 和 `cumulative_net_value` 保留原始精度（最多 4 位小数），不做四舍五入。

## stderr 日志格式

与现有 skill 风格一致，使用 `[INFO]` / `[ERROR]` 前缀：

```
[INFO] 正在获取开放基金排行: symbol=全部
[INFO] 获取到 19747 条记录
[INFO] 按 近1年 降序排列, 取前 20 条
[INFO] 输出: jsonl 格式, 20 条记录
[INFO] 完成
```

## 错误处理

| 场景 | 处理 |
|---|---|
| `--symbol` 非法值 | stderr 输出合法值列表 + 示例，exit code 2 |
| `--sort-by` 非法值 | stderr 输出合法值列表 + 示例，exit code 2 |
| `--order` 非法值 | stderr 输出合法值 (`desc`/`asc`)，exit code 2 |
| `--top-n` 非正整数 | stderr 提示须为正整数，exit code 2 |
| `--output` 非法值 | stderr 输出合法值 (`jsonl`/`json`)，exit code 2 |
| API 调用超时/网络错误 | stderr 输出错误原因，exit code 2 |
| API 返回空 DataFrame | stderr 提示无数据，stdout 输出 `[]` 或空行，exit code 1 |
| `top_n` > 实际记录数 | 输出全部记录，stderr 提示实际数量 |

## 文件结构

```
akshare-open-fund-rank/
├── SKILL.md
└── scripts/
    ├── __init__.py
    ├── open_fund_rank.py          # 主脚本
    └── tests/
        ├── __init__.py
        └── test_open_fund_rank.py  # 单元测试
        └── test_integration.py     # 集成测试
```

## 测试策略

### 单元测试（mock akshare API）

- 参数校验：合法值通过，非法值报错
- 列重命名：中文列名 → 英文列名映射正确
- NaN → null 转换正确
- 排序逻辑：desc/asc 均正确
- Top-N 截取逻辑正确
- JSON/JSONL 输出格式正确，可被解析
- 空 DataFrame 处理正确

### 集成测试（真实 API，标记 `@pytest.mark.integration`）

- 真实 API 调用成功返回数据
- 各 `--symbol` 参数均可返回数据
- stdout 输出可被 `json.loads` 逐行解析
- exit code 正确

## 依赖

```bash
uv pip install akshare pandas
```

## 不做的功能

- 无缓存（每次实时查询）
- 无分页
- 无多条件组合筛选（AND/OR）
- 无自定义收益计算

## 使用示例

```bash
# 获取近 1 年涨幅最高的前 20 只基金
uv run python scripts/open_fund_rank.py --top-n 20

# 获取股票型基金，按近 3 月涨幅排序，取前 10
uv run python scripts/open_fund_rank.py --symbol 股票型 --sort-by 近3月 --top-n 10

# 获取债券型基金，按单位净值升序排列
uv run python scripts/open_fund_rank.py --symbol 债券型 --sort-by 单位净值 --order asc

# 输出 JSON 数组格式
uv run python scripts/open_fund_rank.py --symbol QDII --output json
```
