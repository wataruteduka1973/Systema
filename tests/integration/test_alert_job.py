from io import StringIO
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from Main.management.commands import run_alerts
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.models.watchitem import WatchItem
from Main.services.job_lock import JobAlreadyRunning, alert_job_lock

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def local_lock_path(settings, tmp_path):
    settings.BASE_DIR = tmp_path


def test_second_job_cannot_enter_and_exception_releases_lock():
    with pytest.raises(ValueError):
        with alert_job_lock() as check:
            check()
            with pytest.raises(JobAlreadyRunning):
                with alert_job_lock():
                    pytest.fail("second job acquired lock")
            raise ValueError("job failure")
    with alert_job_lock() as check:
        check()


def test_command_refuses_overlapping_job():
    with alert_job_lock():
        with pytest.raises(CommandError, match="already running"):
            call_command("run_alerts", evaluate_only=True)


def test_saved_search_scope_and_evaluate_only_do_not_fetch(monkeypatch):
    owner = get_user_model().objects.create_user("job-owner")
    saved = SavedSearch.objects.create(user=owner, name="saved", keyword="camera")
    run = SearchRun.objects.create(
        user=owner, saved_search=saved, search_type="current", keyword="camera"
    )
    WatchItem.objects.create(user=owner, name="unrelated", url="https://example.test/item")
    fetch = Mock(side_effect=AssertionError("unexpected external I/O"))
    evaluate = Mock(return_value=0)
    watch = Mock()
    monkeypatch.setattr(run_alerts, "complex_market_data_logic", fetch)
    monkeypatch.setattr(run_alerts, "evaluate_saved_search_alert_rules", evaluate)
    monkeypatch.setattr(run_alerts, "evaluate_watch_alert_rules", watch)
    call_command("run_alerts", evaluate_only=True, saved_search_id=saved.pk, stdout=StringIO())
    fetch.assert_not_called()
    watch.assert_not_called()
    assert evaluate.call_args.args[0].pk == run.pk


def test_failed_refresh_returns_nonzero(monkeypatch):
    owner = get_user_model().objects.create_user("job-failure")
    SavedSearch.objects.create(user=owner, name="saved", keyword="camera")
    monkeypatch.setattr(
        run_alerts, "complex_market_data_logic", Mock(side_effect=ValueError("private-keyword"))
    )
    errors = StringIO()
    with pytest.raises(CommandError, match="failed searches"):
        call_command("run_alerts", stdout=StringIO(), stderr=errors)
    assert "private-keyword" not in errors.getvalue()


def test_time_budget_stops_before_next_unit(monkeypatch):
    owner = get_user_model().objects.create_user("job-time")
    WatchItem.objects.create(user=owner, name="watch", url="https://example.test/item")
    times = iter([0, 2])
    monkeypatch.setattr(run_alerts, "monotonic", lambda: next(times))
    with pytest.raises(CommandError, match="time budget exhausted"):
        call_command("run_alerts", evaluate_only=True, max_runtime_seconds=1)


@pytest.mark.parametrize("option", ["user_id", "saved_search_id", "max_runtime_seconds"])
def test_invalid_command_limits_fail(option):
    with pytest.raises(CommandError, match="must be positive"):
        call_command("run_alerts", **{option: 0})
