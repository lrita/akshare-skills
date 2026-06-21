"""集成测试 — 需要真实网络，标记为 integration"""
import os, sys, json, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "tech_selection.py")
# Longer timeout: 20 concurrent APIs on a slow/non-trading day may need up to 10 minutes
CLI_TIMEOUT = 600


def run_cli(*args, timeout=None):
    result = subprocess.run(
        [sys.executable, SCRIPT_PATH] + list(args),
        capture_output=True, text=True,
        timeout=timeout if timeout is not None else CLI_TIMEOUT,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.mark.integration
class TestRealAPI:
    def test_single_mode_lxsz_structure(self):
        """验证 single 模式的结构正确性和错误处理（非交易日数据可能为空）"""
        rc, stdout, stderr = run_cli(
            "--mode", "single", "--indicator", "fetch_lxsz_ths",
            timeout=120,
        )
        assert rc in (0, 1), f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["mode"] == "single"
        assert data["indicator"] == "fetch_lxsz_ths"
        assert "count" in data
        assert "data" in data
        assert "fetch_time" in data
        if data["data"]:
            assert "stock_code" in data["data"][0]
            assert "stock_name" in data["data"][0]
        else:
            assert len(data["errors"]) >= 1

    def test_single_mode_cxg_with_symbol(self):
        """验证带 symbol 参数的 single 模式能正常运行"""
        rc, stdout, stderr = run_cli(
            "--mode", "single",
            "--indicator", "fetch_cxg_ths",
            "--symbol", "fetch_cxg_ths=一年新高",
            timeout=120,
        )
        assert rc in (0, 1), f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["mode"] == "single"
        assert "count" in data
        assert "errors" in data

    def test_intersect_mode_structure(self):
        """验证 intersect 模式的输出结构完整"""
        rc, stdout, stderr = run_cli(
            "--mode", "intersect",
            "--indicator", "fetch_lxsz_ths,fetch_ljqs_ths",
            timeout=120,
        )
        assert rc in (0, 1), f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["mode"] == "intersect"
        assert data["total_indicators"] == 2
        assert "indicator_counts" in data
        assert "data" in data
        assert "errors" in data

    def test_scan_mode_returns_signal_data(self):
        """验证 scan 模式完整运行，输出信号聚合结构（20 个 APIs 可能需要较长时间）"""
        rc, stdout, stderr = run_cli("--mode", "scan", "--top-n", "10")
        assert rc in (0, 1), f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["mode"] == "scan"
        assert data["total_indicators"] == 20
        assert "signal_summary" in data
        assert "data" in data
        assert len(data["data"]) <= 10
        if data["data"]:
            item = data["data"][0]
            assert "signals" in item
            assert "signal_count" in item
            assert item["signal_count"] >= 1

    def test_full_mode_has_detailed_summary(self):
        """验证 full 模式的 signal_summary 包含详细的指标健康度"""
        rc, stdout, stderr = run_cli("--mode", "full", "--top-n", "5")
        assert rc in (0, 1), f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["mode"] == "full"
        summary = data["signal_summary"]
        assert "indicators" in summary
        assert len(summary["indicators"]) == 20
        for ind in summary["indicators"]:
            assert "indicator" in ind
            assert "status" in ind
            assert "total_rows" in ind

    def test_invalid_mode_exits_2(self):
        rc, stdout, stderr = run_cli("--mode", "invalid", timeout=10)
        assert rc == 2

    def test_single_missing_indicator_exits_2(self):
        rc, stdout, stderr = run_cli("--mode", "single", timeout=10)
        assert rc == 2

    def test_output_to_file(self, tmp_path):
        output_file = tmp_path / "test_output.json"
        rc, stdout, stderr = run_cli(
            "--mode", "single",
            "--indicator", "fetch_lxsz_ths",
            "--output", str(output_file),
            timeout=120,
        )
        assert rc in (0, 1)
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["mode"] == "single"
