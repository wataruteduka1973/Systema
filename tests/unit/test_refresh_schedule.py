from datetime import datetime, timedelta

import pytest

from Main.domain.refresh_schedule import is_refresh_due, next_refresh_at

LAST = datetime(2026, 10, 13, 9, 0)


def due(minutes_later, interval, failed=False, last=LAST):
    return is_refresh_due(
        LAST + timedelta(minutes=minutes_later), last, interval, last_attempt_failed=failed
    )


def test_a_search_that_never_ran_is_due_now():
    assert next_refresh_at(None, 24, last_attempt_failed=False) is None
    assert is_refresh_due(LAST, None, 24, last_attempt_failed=False)


@pytest.mark.parametrize(
    ("interval", "not_yet", "due_at"),
    [(1, 49, 50), (6, 349, 350), (24, 1429, 1430)],
)
def test_the_interval_has_a_ten_minute_tolerance_for_a_late_scheduler(interval, not_yet, due_at):
    assert not due(not_yet, interval)
    assert due(due_at, interval)


def test_an_hourly_search_runs_on_every_slightly_early_wake_up():
    # The scheduler measured 59 minutes since the last attempt; waiting would skip a whole hour.
    assert due(59, 1)


def test_a_failed_attempt_is_retried_after_an_hour_whatever_the_interval():
    assert next_refresh_at(LAST, 24, last_attempt_failed=True) == LAST + timedelta(hours=1)
    assert not due(30, 24, failed=True)
    assert due(55, 24, failed=True)
