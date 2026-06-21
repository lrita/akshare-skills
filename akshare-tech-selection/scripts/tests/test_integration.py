"""集成测试 — 需要真实网络，标记为 integration"""
import os
import sys
import json
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "tech_selection.py")


def run_cli(*args):
    result = subprocess.run(
        [sys.executable, SCRIPT_PATH] + list(args),
        capture_output=True, text=True,
        timeout=180,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.mark.integration
class TestRealAPI:
    def test_single_mode_lxsz_returns_data(self):
        rc, stdout, stderr = run_cli("--mode", "single", "--indicator", "fetch_lxsz_ths")
        assert rc == 0, f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["mode"] == "single"
        assert data["indicator"] == "fetch_lxsz_ths"
        assert data["count"] > 0
        assert len(data["data"]) > 0
        assert "stock_code" in data["data"][0]
        assert "stock_name" in data["data"][0]

    def test_single_mode_cxg_with_symbol(self):
        rc, stdout, stderr = run_cli(
            "--mode", "single",
            "--indicator", "fetch_cxg_ths",
            "--symbol", "fetch_cxg_ths=一年新高",
        )
        assert rc == 0, f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["count"] > 0

    def test_intersect_mode_two_indicators(self):
        rc, stdout, stderr = run_cli(
            "--mode", "intersect",
            "--indicator", "fetch_lxsz_ths,fetch_ljqs_ths",
        )
        assert rc == 0, f"stderr: {stderr}"
        data = json.loads(stdout)
        assert data["mode"] == "intersect"
        assert data["total_indicators"] == 2
        assert data["succeeded_indicators"] >= 1

    def test_scan_mode_returns_signal_data(self):
        rc, stdout, stderr = run_cli("--mode", "scan", "--top-n", "10")
        assert rc == 0, f"stderr: {stderr}"
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
        rc, stdout, stderr = run_cli("--mode", "full", "--top-n", "5")
        assert rc == 0, f"stderr: {stderr}"
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
        rc, stdout, stderr = run_cli("--mode", "invalid")
        assert rc == 2

    def test_single_missing_indicator_exits_2(self):
        rc, stdout, stderr = run_cli("--mode", "single")
        assert rc == 2

    def test_output_to_file(self, tmp_path):
        output_file = tmp_path / "test_output.json"
        rc, stdout, stderr = run_cli(
            "--mode", "single",
            "--indicator", "fetch_lxsz_ths",
            "--output", str(output_file),
        )
        assert rc == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["mode"] == "single"
