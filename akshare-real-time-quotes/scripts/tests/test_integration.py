"""集成测试 --- 需要真实网络，标记为 integration"""
import json
import os
import subprocess
import sys
import pytest


SCRIPT = os.path.join(os.path.dirname(__file__), "..", "fetch_realtime.py")


@pytest.mark.integration
class TestQuoteIntegration:
    """真实网络 quote 子命令集成测试"""

    def test_quote_shanghai_stock(self):
        """上海股票 600183 实时行情"""
        result = subprocess.run(
            [sys.executable, SCRIPT, "quote", "--symbol", "600183"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["股票代码"] == "600183"
        assert data["股票名称"] != ""
        assert "行情数据" in data
        assert "当前价格(元)" in data["行情数据"]
        assert "盘口数据" in data
        # 盘口至少有委差字段
        assert "委差" in data["盘口数据"]

    def test_quote_shenzhen_stock(self):
        """深圳股票 000001 实时行情"""
        result = subprocess.run(
            [sys.executable, SCRIPT, "quote", "--symbol", "000001"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["股票代码"] == "000001"
        assert "行情数据" in data
        assert "成交数据" in data
        assert "盘口数据" in data
        assert "估值数据" in data
        # 数据类型检查
        assert isinstance(data["行情数据"]["当前价格(元)"], (int, float))

    def test_invalid_symbol_rejected(self):
        """非法代码被拒绝"""
        result = subprocess.run(
            [sys.executable, SCRIPT, "quote", "--symbol", "abc"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 2


@pytest.mark.integration
class TestIntradayIntegration:
    """真实网络 intraday 子命令集成测试"""

    def test_intraday_returns_minute_data(self):
        """上海股票日内分钟K线"""
        result = subprocess.run(
            [sys.executable, SCRIPT, "intraday", "--symbol", "600183"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["股票代码"] == "600183"
        assert data["股票名称"] != ""
        assert len(data["交易日期"]) == 8  # YYYYMMDD
        assert isinstance(data["分钟K线"], list)
        if data["分钟K线"]:
            minute = data["分钟K线"][0]
            assert len(minute["时间"]) == 4  # HHmm
            assert isinstance(minute["价格(元)"], (int, float))
            assert isinstance(minute["成交量"], int)
            assert isinstance(minute["成交额(元)"], (int, float))
