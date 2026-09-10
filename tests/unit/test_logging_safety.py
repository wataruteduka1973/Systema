import logging
from unittest.mock import Mock

import pytest

import manage
from Main.logging_filters import RedactSensitiveDataFilter


def filtered_message(message, exc_info=None):
    record = logging.LogRecord("test", logging.ERROR, __file__, 1, message, (), exc_info)
    RedactSensitiveDataFilter().filter(record)
    return record.getMessage(), record.exc_info


def test_logging_filter_redacts_credentials_keywords_and_url_queries():
    message, _ = filtered_message(
        "password=plain token:abc keyword: camera lens url=https://example.test/path?secret=yes"
    )
    assert "plain" not in message
    assert "abc" not in message
    assert "camera lens" not in message
    assert "secret=yes" not in message
    assert message.count("[REDACTED]") >= 3


def test_logging_filter_removes_exception_text():
    try:
        raise ValueError("password=plain")
    except ValueError:
        message, exc_info = filtered_message("failed", exc_info=__import__("sys").exc_info())
    assert message == "failed exception=ValueError"
    assert exc_info is None


def test_management_command_failure_logs_no_arguments(monkeypatch):
    mocked_logger = Mock()
    monkeypatch.setattr(manage, "logger", mocked_logger)

    with pytest.raises(RuntimeError):
        manage.execute_management_command(
            lambda argv: (_ for _ in ()).throw(RuntimeError("password=plain")),
            ["manage.py", "run_alerts", "--password=plain"],
        )

    assert mocked_logger.error.call_args.args == (
        "management_command_failed command=%s failure=%s",
        "run_alerts",
        "RuntimeError",
    )
