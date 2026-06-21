"""pytest configuration for akshare-tech-selection"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires network)"
    )
