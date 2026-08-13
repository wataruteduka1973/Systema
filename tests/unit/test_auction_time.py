from datetime import datetime, timezone

import pytest

from Main.domain.auction_time import format_remaining_time, parse_duration_seconds


@pytest.mark.unit
def test_parse_duration_seconds_handles_compound_duration():
    assert parse_duration_seconds("2日5時間20分") == 192000


@pytest.mark.unit
def test_parse_duration_seconds_rejects_unknown_value():
    assert parse_duration_seconds(None) == float("inf")
    assert parse_duration_seconds("不明") == float("inf")


@pytest.mark.unit
def test_format_remaining_time_is_independent_from_django():
    now = datetime(2026, 8, 13, 0, 0, tzinfo=timezone.utc)
    assert format_remaining_time("2026-08-14T02:30:00+00:00", now=now) == "1日2時間30分"
