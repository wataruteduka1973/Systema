"""When the scheduler refreshes a saved search.

The in-app scheduler wakes about once an hour, a little later each time. A search is due when its
interval has passed since the last attempt, minus a tolerance so that an hourly search is not pushed
to every second wake-up. After a failed attempt the search is retried on the next hourly wake-up
whatever its interval, so a transient error does not leave a daily search stale for a whole day.
"""

from __future__ import annotations

from datetime import datetime, timedelta

REFRESH_INTERVAL_HOURS = (1, 6, 24)
SCHEDULE_TOLERANCE = timedelta(minutes=10)
RETRY_AFTER_FAILURE = timedelta(hours=1)


def next_refresh_at(
    last_attempt_at: datetime | None, interval_hours: int, *, last_attempt_failed: bool
) -> datetime | None:
    """The time the next refresh is planned for; None means it has never run and is due now."""
    if last_attempt_at is None:
        return None
    wait = RETRY_AFTER_FAILURE if last_attempt_failed else timedelta(hours=interval_hours)
    return last_attempt_at + wait


def is_refresh_due(
    now: datetime,
    last_attempt_at: datetime | None,
    interval_hours: int,
    *,
    last_attempt_failed: bool,
) -> bool:
    planned = next_refresh_at(
        last_attempt_at, interval_hours, last_attempt_failed=last_attempt_failed
    )
    return planned is None or now >= planned - SCHEDULE_TOLERANCE
