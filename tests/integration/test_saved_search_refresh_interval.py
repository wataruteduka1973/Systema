"""Per-saved-search refresh intervals, refresh status, and the scheduler honouring them."""

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from Main.management.commands import run_alerts
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.services.saved_searches import refresh_status
from tests.integration.test_alert_command_usecase import CurrentFailureProvider, SuccessfulProvider

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user("refresh-owner", password="password")


def _saved(user, name, *, interval=1, hours_ago=None):
    saved = SavedSearch.objects.create(
        user=user, name=name, keyword=name, refresh_interval_hours=interval
    )
    if hours_ago is not None:
        SavedSearch.objects.filter(pk=saved.pk).update(
            last_run_at=timezone.now() - timedelta(hours=hours_ago)
        )
        saved.refresh_from_db()
    return saved


def _run_alerts(monkeypatch, provider=SuccessfulProvider, **options):
    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", provider)
    output = StringIO()
    call_command("run_alerts", stdout=output, **options)
    return output.getvalue()


def _refreshed(saved):
    return SearchRun.objects.filter(saved_search=saved, trigger="scheduled").exists()


def test_existing_and_new_saved_searches_default_to_hourly(user):
    assert _saved(user, "既定").refresh_interval_hours == 1


def test_the_database_rejects_an_unsupported_interval(user):
    with pytest.raises(IntegrityError), transaction.atomic():
        _saved(user, "不正", interval=3)


def test_scheduler_refreshes_only_searches_whose_interval_has_passed(user, monkeypatch):
    never = _saved(user, "未取得", interval=24)
    hourly = _saved(user, "毎時", interval=1, hours_ago=1)
    daily_due = _saved(user, "毎日・期限", interval=24, hours_ago=24)
    daily_waiting = _saved(user, "毎日・待機", interval=24, hours_ago=3)
    six_waiting = _saved(user, "6時間・待機", interval=6, hours_ago=5)

    output = _run_alerts(monkeypatch)

    assert "saved_searches_refreshed=3" in output
    assert "not_due=2" in output
    assert [_refreshed(item) for item in (never, hourly, daily_due)] == [True, True, True]
    assert [_refreshed(item) for item in (daily_waiting, six_waiting)] == [False, False]


def test_a_failed_daily_search_is_retried_on_the_next_hourly_run(user, monkeypatch):
    daily = _saved(user, "毎日", interval=24)
    with pytest.raises(CommandError, match="1 failed searches"):
        _run_alerts(monkeypatch, provider=CurrentFailureProvider)
    SavedSearch.objects.filter(pk=daily.pk).update(last_run_at=timezone.now() - timedelta(hours=1))

    output = _run_alerts(monkeypatch)

    assert "saved_searches_refreshed=1" in output
    status = refresh_status(SavedSearch.objects.get(pk=daily.pk))
    assert status["lastAttemptFailed"] is False
    assert status["lastFailureReason"] == "ヤフオクに接続できませんでした"
    assert status["lastSuccessItemCount"] == 1


def test_a_named_search_runs_even_before_its_interval(user, monkeypatch):
    waiting = _saved(user, "毎日", interval=24, hours_ago=1)

    _run_alerts(monkeypatch, saved_search_id=waiting.pk)

    assert _refreshed(waiting)


def test_refresh_status_reports_success_failure_and_next_run(user):
    saved = _saved(user, "状況", interval=6, hours_ago=2)
    assert refresh_status(saved)["lastSuccessAt"] is None
    SearchRun.objects.create(
        user=user, saved_search=saved, keyword="状況", search_type=SearchRun.CURRENT, item_count=8
    )

    status = refresh_status(saved)

    assert status["lastSuccessItemCount"] == 8
    assert status["lastAttemptFailed"] is False
    assert status["nextRefreshAt"] == (saved.last_run_at + timedelta(hours=6)).isoformat()
    saved.is_active = False
    assert refresh_status(saved)["nextRefreshAt"] is None


def test_api_updates_the_interval_and_rejects_other_values(client, user):
    saved = _saved(user, "API")
    client.force_login(user)
    url = reverse("saved_search_item", args=[saved.pk])

    response = client.patch(url, {"refreshIntervalHours": 24}, content_type="application/json")

    assert response.status_code == 200
    assert response.json()["item"]["refreshIntervalHours"] == 24
    assert "refresh" in response.json()["item"]
    for value in (3, "6", True):
        bad = client.patch(url, {"refreshIntervalHours": value}, content_type="application/json")
        assert bad.status_code == 400
    # Other edits keep the chosen interval.
    client.patch(url, {"name": "API改名"}, content_type="application/json")
    assert SavedSearch.objects.get(pk=saved.pk).refresh_interval_hours == 24


def test_another_users_saved_search_cannot_be_changed(client, user):
    saved = _saved(user, "他人")
    other = get_user_model().objects.create_user("refresh-other")
    client.force_login(other)

    response = client.patch(
        reverse("saved_search_item", args=[saved.pk]),
        {"refreshIntervalHours": 24},
        content_type="application/json",
    )

    assert response.status_code == 404
    assert SavedSearch.objects.get(pk=saved.pk).refresh_interval_hours == 1
