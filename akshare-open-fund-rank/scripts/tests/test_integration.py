"""集成测试 — 需要真实网络，标记为 integration"""
import os, sys, json, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
import open_fund_rank as ofr


SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "open_fund_rank.py")


def run_cli(*args):
    """运行 CLI 并返回 (returncode, stdout, stderr)"""
    result = subprocess.run(
        [sys.executable, SCRIPT_PATH] + list(args),
        capture_output=True, text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.mark.integration
class TestRealAPI:
    """真实 API 调用测试"""

    def test_api_returns_data_all(self):
        import akshare as ak
        df = ak.fund_open_fund_rank_em(symbol="全部")
        assert len(df) > 10000

    def test_api_returns_data_by_type(self):
        import akshare as ak
        for symbol in ["股票型", "混合型", "债券型", "指数型", "QDII", "FOF"]:
            df = ak.fund_open_fund_rank_em(symbol=symbol)
            assert len(df) > 0, f"symbol={symbol} 返回空数据"

    def test_api_columns_match_expected(self):
        import akshare as ak
        df = ak.fund_open_fund_rank_em(symbol="全部")
        expected_cn_cols = [
            "序号", "基金代码", "基金简称", "日期", "单位净值", "累计净值",
            "日增长率", "近1周", "近1月", "近3月", "近6月", "近1年",
            "近2年", "近3年", "今年来", "成立来", "自定义", "手续费",
        ]
        for col in expected_cn_cols:
            assert col in df.columns, f"缺少列: {col}"


@pytest.mark.integration
class TestCLIIntegration:
    """CLI 端到端集成测试"""

    def test_default_run_produces_jsonl(self):
        rc, stdout, stderr = run_cli("--top-n", "2")
        assert rc == 0
        lines = stdout.strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert "fund_code" in obj
            assert "fund_name" in obj
            assert "1y_return" in obj
            assert "fee" in obj

    def test_json_output_format(self):
        rc, stdout, stderr = run_cli("--top-n", "2", "--output", "json")
        assert rc == 0
        data = json.loads(stdout)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_filter_and_sort(self):
        rc, stdout, stderr = run_cli(
            "--symbol", "混合型",
            "--filter", "近1年>10",
            "--sort-by", "近1年",
            "--top-n", "5",
        )
        assert rc == 0
        lines = stdout.strip().split("\n")
        assert len(lines) <= 5
        returns = []
        for line in lines:
            obj = json.loads(line)
            if obj["1y_return"] is not None:
                returns.append(obj["1y_return"])
        # 降序排列
        for i in range(len(returns) - 1):
            assert returns[i] >= returns[i + 1], f"排序错误: {returns}"

    def test_invalid_symbol_exit_code_2(self):
        rc, stdout, stderr = run_cli("--symbol", "INVALID")
        assert rc == 2
        assert "[ERROR]" in stderr

    def test_invalid_sort_by_exit_code_2(self):
        rc, stdout, stderr = run_cli("--sort-by", "不存在的列")
        assert rc == 2

    def test_invalid_filter_exit_code_2(self):
        rc, stdout, stderr = run_cli("--filter", "badformat")
        assert rc == 2

    def test_top_n_zero_exit_code_2(self):
        rc, stdout, stderr = run_cli("--top-n", "0")
        assert rc == 2

    def test_empty_filter_result_exit_code_1(self):
        # 极端过滤条件，预期无数据
        rc, stdout, stderr = run_cli(
            "--symbol", "债券型",
            "--filter", "近1年>99999",
        )
        assert rc == 1
        assert "过滤后无数据" in stderr or "过滤后 0 条" in stderr

    def test_all_symbol_types_work(self):
        """确保所有 symbol 均可用"""
        for symbol in ["全部", "股票型", "混合型", "债券型", "指数型", "QDII", "FOF"]:
            rc, stdout, stderr = run_cli("--symbol", symbol, "--top-n", "1")
            assert rc == 0, f"symbol={symbol} 失败: {stderr}"

    def test_fee_column_present(self):
        rc, stdout, stderr = run_cli("--top-n", "1")
        obj = json.loads(stdout.strip().split("\n")[0])
        assert "fee" in obj
        assert isinstance(obj["fee"], str)

    def test_nan_values_output_as_null(self):
        """获取足够数据，验证 NaN 字段以 null 输出"""
        rc, stdout, stderr = run_cli("--symbol", "全部", "--sort-by", "近3年", "--order", "asc", "--top-n", "10")
        assert rc == 0
        for line in stdout.strip().split("\n"):
            json.loads(line)  # 确保每行都可解析
