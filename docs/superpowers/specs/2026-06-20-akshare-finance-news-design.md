# 财经快讯 (akshare-finance-news) SKILL 设计规格

**日期**: 2026-06-20
**状态**: 已确认

---

## 1. 概述

构建一个名为 `akshare-finance-news` 的 SKILL，供 HermesAgent 等外部 AI Agent 通过 GitHub 安装使用。该 skill 从 4 个财经数据源获取最新快讯，过滤时间范围，提取完整内容，输出结构化 JSON 供大模型分析对 A 股的影响。

## 2. 项目范围

仅包含一个 skill：`akshare-finance-news/`。未来其他 akshare 相关 skill 按相同的扁平目录结构独立添加。

## 3. 目录结构

```
akshare-finance-news/
  SKILL.md                    # 使用说明、触发条件、输出格式
  scripts/
    fetch_news.py             # 核心数据获取脚本
    tests/
      __init__.py
      test_filter.py          # 时间过滤逻辑测试
      test_fetch.py           # API mock 测试
      test_dedup.py           # 去重逻辑测试
      test_integration.py     # 端到端集成测试（需要真实网络）
```

## 4. 数据流水线

### 数据源

| API | 数据源 | 数据量 | 有独立链接？ |
|-----|--------|--------|-------------|
| `stock_info_cjzc_em()` | 东财财经早餐 | 400条 | 是 |
| `stock_info_global_em()` | 东财全球快讯 | 200条 | 是 |
| `stock_info_global_sina()` | 新浪财经快讯 | 20条 | 否（内容已包含） |
| `stock_info_global_ths()` | 同花顺财经直播 | 20条 | 是 |

### 处理流程

1. **并发获取**：4 个 API 调用并发发起（asyncio），各自获取原始数据
2. **时间过滤**：每条记录检查发布时间，保留满足 `发布时间 >= 昨日15:00:00` 的记录。时间阈值在脚本运行时自动计算
3. **去重**：按标题相似度去重，不同源可能报道同一新闻
4. **内容获取**：有链接的并发抓取完整文章（伪装浏览器）；新浪无链接，直接使用返回的内容字段
5. **组装输出**：统一结构化为 JSON，输出到 stdout

### 并发策略

- 4 个 API 调用并发发起
- 链接内容抓取使用信号量控制，最多 5 并发
- 每个链接间随机延迟 1-3 秒
- 总超时时间 600 秒

## 5. 反爬策略

链接内容抓取时采用以下措施：

- User-Agent：真实浏览器标识（Chrome macOS 最新版）
- 完整请求头：Accept、Accept-Language、Accept-Encoding、Cache-Control、Referer
- 请求间隔：随机 1-3 秒延迟
- 超时：单次请求 15 秒，失败重试 1 次（间隔 2 秒）
- 重试后仍失败：跳过该链接，使用摘要作为 content 降级

## 6. 输出格式

脚本将结构化 JSON 输出到 stdout，运行日志输出到 stderr。

```json
{
  "fetch_time": "2026-06-20 14:30:00",
  "total_count": 15,
  "news": [
    {
      "title": "央行下调基准利率至14.25%",
      "time": "2026-06-20 00:28:26",
      "content": "完整新闻正文..."
    },
    {
      "title": "伊朗否认邀请IAEA核查",
      "time": "2026-06-19 22:46:23",
      "content": "伊朗外交部发言人巴加埃19日在社交媒体发文..."
    }
  ],
  "errors": [
    {"title": "某新闻标题", "error": "timeout"}
  ]
}
```

字段说明：
- `fetch_time`：脚本执行时间
- `total_count`：去重后有效新闻数
- `news[].title`：新闻标题
- `news[].time`：发布时间 (YYYY-MM-DD HH:MM:SS)
- `news[].content`：完整内容（有链接的抓取全文，新浪使用返回值）
- `errors[]`：获取失败的记录，含标题和错误类型

注意：输出不含 `url` 和 `source` 字段，避免触发 AI Agent 的二次抓取。

## 7. 错误处理

分层容错，单点失败不阻塞全局：

### API 调用层

- 单个 API 超时（30秒）或报错 → 记录到 `errors[]`，其余 API 继续
- 空返回或字段缺失 → 跳过该源，不中断

### 链接抓取层

- 超时 15 秒、HTTP 4xx/5xx、HTML 解析失败 → 重试 1 次（间隔 2 秒）
- 重试后仍失败 → 使用 API 返回的摘要作为 `content` 降级

### 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 全部成功 |
| 1 | 部分成功（有 errors 但仍有 news） |
| 2 | 完全失败（无 news，所有源均失败） |

## 8. 环境与依赖

- Python 版本：≥ 3.10
- 包管理器：`uv`
- 依赖：`akshare`、`requests`、`beautifulsoup4`

开发环境：
```bash
uv pip install akshare requests beautifulsoup4
```

测试：
```bash
uv run pytest scripts/tests/ -v
```

## 9. SKILL.md 触发条件

当用户提到以下关键词或场景时，Agent 应调用此 skill：
- 财经新闻、财经快讯
- 新闻对 A 股的影响
- 盘前新闻分析
- 最近财经事件汇总

SKILL.md 中提供分析 prompt，Agent 将 JSON 新闻数据与此 prompt 一起提交给大模型。

## 10. 测试策略

| 测试文件 | 内容 | 类型 |
|----------|------|------|
| `test_filter.py` | 时间过滤逻辑：各种时间格式、边界值、跨天场景 | 单元测试 |
| `test_fetch.py` | Mock akshare API 和 requests，验证错误处理 | 单元测试 |
| `test_dedup.py` | 标题相似度去重：完全匹配、部分匹配、不匹配 | 单元测试 |
| `test_integration.py` | 端到端真实网络调用（可选标记） | 集成测试 |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-20 | 初始版本 |
