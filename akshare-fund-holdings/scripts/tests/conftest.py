"""pytest configuration for akshare-fund-holdings tests."""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require real network access to akshare APIs",
    )
