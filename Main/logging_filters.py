"""Logging filters that remove common sensitive values before formatting."""

import logging
import re


class RedactSensitiveDataFilter(logging.Filter):
    _patterns = (
        re.compile(
            r"(?i)(password|passwd|secret|token|cookie|authorization|api[_-]?key)"
            r"(\s*[:=]\s*)([^\s,;]+)"
        ),
        re.compile(r"(?i)(keyword\s*[:=]\s*)([^,;]+)"),
        re.compile(r"(https?://[^\s?]+)\?[^\s]+"),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in self._patterns:
            if pattern.groups == 3:
                message = pattern.sub(r"\1\2[REDACTED]", message)
            else:
                message = pattern.sub(r"\1[REDACTED]", message)
        if record.exc_info:
            exception_type = record.exc_info[0]
            exception_name = exception_type.__name__ if exception_type else "Exception"
            message = f"{message} exception={exception_name}"
            record.exc_info = None
            record.exc_text = None
        record.msg = message
        record.args = ()
        return True
