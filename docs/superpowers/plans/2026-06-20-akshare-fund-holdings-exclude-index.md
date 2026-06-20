# 指数/ETF/增强基金过滤 实现计划

> **目标：** 在 fetch_fund_list 中添加基金简称关键词过滤，排除指数基金、ETF、ETF联接、增强型基金

**架构：** 新增 `is_index_fund()` 纯函数，用 5 条正则规则判断是否排除；在 `fetch_fund_list` 末尾加一个过滤步骤；在 `main_with_args` 和 `main` 中新增 `--no-exclude-index` 参数

**技术栈：** Python 3 标准库 re 模块

---

### 任务 1：实现过滤并添加测试

**文件：**
- 修改：`akshare-fund-holdings/scripts/fund_holdings.py`
- 修改：`akshare-fund-holdings/scripts/tests/test_fund_holdings.py`

- [ ] **步骤 1：编写失败测试**

在 `test_fund_holdings.py` 的 `TestFundListFetch` 类末尾追加：

```python
    def test_exclude_index_funds(self):
        """验证指数/ETF/联接/增强基金被排除"""
        test_cases = [
            ("博时央企结构调整ETF", True),     # 以ETF结尾
            ("华夏沪深300ETF联接A", True),     # 数字+ETF, ETF+联接
            ("沪深300ETF工银", True),          # 数字+ETF
            ("传媒ETF", True),                 # 以ETF结尾
            ("银华中债1-3年国开行债券指数A", True), # 含"指数"
            ("易方达上证50增强A", True),        # 含"增强"
            ("诺安沪深300增强A", True),         # 含"增强"(数字+增强)
            ("嘉实成长增强混合", True),          # 含"增强"
            ("广发稳泰多元机遇三个月持有混合(ETF-FOF)A", False),  # ETF-FOF保留
            ("易方达沪深300精选增强A", True),    # 含"增强"
        ]
        for name, expected in test_cases:
            assert fund_holdings.is_index_fund(name) == expected, \
                f"is_index_fund('{name}') should be {expected}"

    def test_exclude_index_disabled(self):
        """排除功能关闭时不过滤"""
        import pandas as pd
        funds = [
            {"基金代码": "510300", "基金简称": "沪深300ETF", "总募集规模": 3296860.0, "单位净值": 4.97},
            {"基金代码": "070011", "基金简称": "嘉实策略", "总募集规模": 4191700.0, "单位净值": 0.916},
        ]
        result = fund_holdings.filter_index_funds(funds, exclude_index=False)
        assert len(result) == 2
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py::TestFundListFetch::test_exclude_index_funds -v
```

预期：FAIL，`is_index_fund` 未定义。

- [ ] **步骤 3：实现 `is_index_fund` 和 `filter_index_funds`**

在 `fund_holdings.py` 的 `# ---- 缓存管理 ----` 之前（即文件已有的代码段之间）插入：

```python
# ---- 指数基金过滤 ----

import re


def is_index_fund(name: str) -> bool:
    """判断基金简称是否为指数/ETF/联接/增强型基金

    规则:
    1. 数字+ETF (数字和ETF之间可能有其他字符)
    2. 简称以ETF结尾
    3. ETF和联接同时出现 (ETF和联接之间可能有其他字符)
    4. 含"指数"
    5. 含"增强"

    参数:
        name: 基金简称

    返回:
        bool: 应排除返回 True
    """
    # 规则 1: 数字+ETF (数字和ETF之间可能有其他字符)
    if re.search(r'\d.*ETF', name):
        return True
    # 规则 2: 简称以ETF结尾
    if name.endswith('ETF'):
        return True
    # 规则 3: ETF和联接同时出现
    if 'ETF' in name and '联接' in name:
        return True
    # 规则 4: 含"指数"
    if '指数' in name:
        return True
    # 规则 5: 含"增强"
    if '增强' in name:
        return True
    return False


def filter_index_funds(funds: list[dict], exclude_index: bool = True) -> list[dict]:
    """过滤指数/ETF/联接/增强型基金

    参数:
        funds: 基金列表
        exclude_index: 是否启用过滤，默认 True

    返回:
        list[dict]: 过滤后的基金列表
    """
    if not exclude_index:
        return funds
    return [f for f in funds if not is_index_fund(f["基金简称"])]
```

然后将 `import re` 移到文件顶部（与已有 imports 放在一起，替换函数内独立的 `import re`）。

- [ ] **步骤 4：修改 `fetch_fund_list` 签名，加入过滤参数**

```python
# 函数签名改为:
def fetch_fund_list(
    fund_types: list[str],
    min_scale_yi: float = 10.0,
    exclude_index: bool = True,
) -> list[dict]:

# 在 return funds 之前加一行:
    funds = filter_index_funds(funds, exclude_index)
```

- [ ] **步骤 5：修改 `main_with_args` 和 `main`**

在 `main_with_args` 中，提取 `exclude_index` 参数并传给 `fetch_fund_list`：
```python
    exclude_index = args.exclude_index
    # ...
    all_funds = fetch_fund_list(fund_types, min_scale_yi, exclude_index)
```

在 `main` 中添加参数：
```python
    parser.add_argument(
        "--no-exclude-index", dest="exclude_index", action="store_false",
        help="不过滤指数/ETF/联接/增强基金",
    )
```

- [ ] **步骤 6：运行全部测试**

```bash
cd /Users/huyanqing.16/lib/python/akshare-skills && uv run pytest akshare-fund-holdings/scripts/tests/test_fund_holdings.py -v -m "not integration"
```

预期：25 个测试全部 PASS。

- [ ] **步骤 7：更新 SKILL.md**

在参数说明表中新增一行：

```
| `--no-exclude-index` | - | 不过滤指数/ETF/联接/增强基金 |
```

- [ ] **步骤 8：Commit**

```bash
git add akshare-fund-holdings/scripts/fund_holdings.py akshare-fund-holdings/scripts/tests/test_fund_holdings.py akshare-fund-holdings/SKILL.md
git commit -m "feat: add index/ETF/enhanced fund exclusion filter"
```
