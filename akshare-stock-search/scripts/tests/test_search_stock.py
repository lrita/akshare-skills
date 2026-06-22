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
    """非法 market 参数应退出 2。"""
    code, stdout, stderr = _run("search", "000001", "--market", "xxx")
    assert code == 2, f"exit={code} stderr={stderr}"


def test_search_empty_keyword():
    """空关键词应退出 2。"""
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
