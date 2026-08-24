from pathlib import Path

import pytest

SLOW_TESTS = {"tests/integration/test_data_migration.py"}


def pytest_collection_modifyitems(items):
    """テスト配置をマーカーへ反映し、選択実行の分類を一元化する。"""
    for item in items:
        path = Path(str(item.path)).as_posix()
        if "/tests/" in path:
            path = f"tests/{path.split('/tests/', 1)[1]}"

        if path.startswith("tests/unit/"):
            item.add_marker(pytest.mark.unit)
        elif path.startswith("tests/integration/"):
            item.add_marker(pytest.mark.integration)
        elif path.startswith("tests/e2e/"):
            item.add_marker(pytest.mark.e2e)

        if path in SLOW_TESTS or "backtest" in item.name:
            item.add_marker(pytest.mark.slow)
