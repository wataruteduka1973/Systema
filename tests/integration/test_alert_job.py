"""run_alerts job robustness: one job at a time, time budget, and failure exit status."""

from io import StringIO
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from Main.management.commands import run_alerts
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.models.watchitem import WatchItem
from Main.services.job_lock import JobAlreadyRunning, alert_job_lock

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def local_lock_path(settings, tmp_path):
    settings.BASE_DIR = tmp_path


def _user(name):
    return get_user_model().objects.create_user(name)


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


def test_command_refuses_overlapping_job(monkeypatch):
    provider = Mock(side_effect=AssertionError("overlapping job fetched"))
    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", provider)
    SavedSearch.objects.create(user=_user("job-overlap"), name="saved", keyword="camera")
    with alert_job_lock():
        with pytest.raises(CommandError, match="already running"):
            call_command("run_alerts", stdout=StringIO())
    provider.assert_not_called()


def test_saved_search_scope_and_evaluate_only_do_not_fetch(monkeypatch):
    owner = _user("job-owner")
    saved = SavedSearch.objects.create(user=owner, name="saved", keyword="camera")
    older = SearchRun.objects.create(
        user=owner, saved_search=saved, search_type="current", keyword="camera"
    )
    latest = SearchRun.objects.create(
        user=owner, saved_search=saved, search_type="current", keyword="camera"
    )
    SearchRun.objects.filter(pk=older.pk).update(created_at=latest.created_at.replace(year=2000))
    WatchItem.objects.create(user=owner, name="unrelated", url="https://example.test/item")
    provider = Mock(side_effect=AssertionError("unexpected external I/O"))
    evaluate = Mock(return_value=0)
    watch = Mock()
    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", provider)
    monkeypatch.setattr(run_alerts, "evaluate_saved_search_alert_rules", evaluate)
    monkeypatch.setattr(run_alerts, "evaluate_watch_alert_rules", watch)

    call_command("run_alerts", evaluate_only=True, saved_search_id=saved.pk, stdout=StringIO())

    provider.assert_not_called()
    watch.assert_not_called()
    evaluate.assert_called_once()
    assert evaluate.call_args.args[0].pk == latest.pk


def test_evaluate_only_skips_a_search_whose_latest_run_failed(monkeypatch):
    owner = _user("job-stale")
    saved = SavedSearch.objects.create(user=owner, name="saved", keyword="camera")
    success = SearchRun.objects.create(
        user=owner, saved_search=saved, search_type="current", keyword="camera"
    )
    SearchRun.objects.create(
        user=owner, saved_search=saved, search_type="current", keyword="camera", succeeded=False
    )
    SearchRun.objects.filter(pk=success.pk).update(created_at=success.created_at.replace(year=2000))
    evaluate = Mock(return_value=0)
    monkeypatch.setattr(run_alerts, "evaluate_saved_search_alert_rules", evaluate)

    call_command("run_alerts", evaluate_only=True, saved_search_id=saved.pk, stdout=StringIO())

    evaluate.assert_not_called()


def test_evaluate_only_without_scope_still_evaluates_watches(monkeypatch):
    owner = _user("job-watches")
    WatchItem.objects.create(user=owner, name="watch", url="https://example.test/item")
    watch = Mock(return_value=0)
    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", Mock(side_effect=AssertionError))
    monkeypatch.setattr(run_alerts, "evaluate_watch_alert_rules", watch)

    call_command("run_alerts", evaluate_only=True, stdout=StringIO())

    watch.assert_called_once()


def test_failed_refresh_returns_nonzero_without_private_detail(monkeypatch):
    SavedSearch.objects.create(user=_user("job-failure"), name="saved", keyword="camera")
    monkeypatch.setattr(
        run_alerts, "YahooMarketplaceProvider", Mock(side_effect=ValueError("private-keyword"))
    )
    output, errors = StringIO(), StringIO()
    with pytest.raises(CommandError, match="1 failed searches") as raised:
        call_command("run_alerts", stdout=output, stderr=errors)
    assert "failed=1" in output.getvalue()
    assert "private-keyword" not in errors.getvalue() + str(raised.value)


def test_time_budget_stops_before_next_unit(monkeypatch):
    owner = _user("job-time")
    WatchItem.objects.create(user=owner, name="first", url="https://example.test/1")
    WatchItem.objects.create(user=owner, name="second", url="https://example.test/2")
    watch = Mock(return_value=0)
    times = iter([0, 0, 2])
    monkeypatch.setattr(run_alerts, "monotonic", lambda: next(times))
    monkeypatch.setattr(run_alerts, "evaluate_watch_alert_rules", watch)
    output = StringIO()
    with pytest.raises(CommandError, match="time budget exhausted"):
        call_command("run_alerts", evaluate_only=True, max_runtime_seconds=1, stdout=output)
    assert watch.call_count == 1
    assert "notifications_created=0" in output.getvalue()


def test_lock_is_released_after_command_failure(monkeypatch):
    SavedSearch.objects.create(user=_user("job-release"), name="saved", keyword="camera")
    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", Mock(side_effect=ValueError))
    with pytest.raises(CommandError, match="failed searches"):
        call_command("run_alerts", stdout=StringIO(), stderr=StringIO())
    with alert_job_lock() as check:
        check()


@pytest.mark.parametrize("option", ["user_id", "saved_search_id", "max_runtime_seconds"])
def test_invalid_command_limits_fail(option):
    with pytest.raises(CommandError, match="must be positive"):
        call_command("run_alerts", **{option: 0})


@pytest.mark.skipif(connection.vendor == "postgresql", reason="SQLite fallback only")
def test_sqlite_fallback_is_refused_in_production(settings):
    settings.IS_PRODUCTION = True
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        with alert_job_lock():
            pytest.fail("production job ran on SQLite")
