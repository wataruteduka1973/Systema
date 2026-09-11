"""検索実行の所要時間と安全な失敗分類。"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns

from Main.services.exceptions import SearchParseError

FAILURE_EXTERNAL_SERVICE = "external_service_unavailable"
FAILURE_HTML_PARSE = "html_parse_error"
FAILURE_UNEXPECTED = "unexpected_error"
FAILURE_NO_DATA = "no_data"
FAILURE_INSUFFICIENT_DATA = "insufficient_data"


def external_failure_code(error: Exception) -> str:
    return FAILURE_HTML_PARSE if isinstance(error, SearchParseError) else FAILURE_EXTERNAL_SERVICE


@dataclass(frozen=True)
class SearchTimer:
    started_at_ns: int

    @classmethod
    def start(cls) -> SearchTimer:
        return cls(started_at_ns=perf_counter_ns())

    def elapsed_ms(self) -> int:
        return max((perf_counter_ns() - self.started_at_ns) // 1_000_000, 0)
