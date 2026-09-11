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


@pytest.mark.parametrize(
    "text",
    [
        "email=person@example.test",
        "session_key=private-session",
        "Cookie: first=private-one; second=private-two",
        "Authorization: Bearer private-token",
        "keyword=private, query; rest",
    ],
)
def test_monitoring_sensitive_log_values_are_redacted(text):
    message, _ = filtered_message(text)
    assert "private" not in message
    assert "person@example.test" not in message


def test_preformatted_traceback_and_stack_are_removed():
    record = logging.LogRecord("test", logging.ERROR, __file__, 1, "safe", (), None)
    record.exc_text = "private exception"
    record.stack_info = "private stack"
    RedactSensitiveDataFilter().filter(record)
    assert record.exc_text is None
    assert record.stack_info is None
