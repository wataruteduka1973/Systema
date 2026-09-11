"""Staff-only monitoring aggregates, filters and disclosure regression tests."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from Main.models.errorlog import ErrorLog
from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.models.watchitem import WatchItem
from Main.services.admin_monitoring import monitoring_snapshot

pytestmark = pytest.mark.django_db


def snapshot(**kwargs):
    return monitoring_snapshot(days=7, level=kwargs.get("level", ""), kind=kwargs.get("kind", ""))


def test_monitoring_empty_and_staff_access(client):
    url = reverse("developer_dashboard")
    assert client.get(url).status_code == 302
    user = get_user_model().objects.create_user("viewer", password="password")
    client.force_login(user)
    assert client.get(url).status_code == 302
    user.is_staff = True
    user.save()
    client.force_login(user)
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["totals"]["success_rate"] is None
    assert "検索記録はありません" in response.content.decode()
    assert "no-store" in response["Cache-Control"]


def test_aggregate_denominators_boundaries_actors_and_failure_labels():
    now = timezone.now()
    user = get_user_model().objects.create_user("actor")
    SearchRun.objects.create(keyword="private", user=user, duration_ms=0)
    SearchRun.objects.create(
        keyword="private",
        session_key="secret",
        duration_ms=300,
        succeeded=False,
        failure_code="html_parse_error",
        trigger="saved",
    )
    SearchRun.objects.create(
        keyword="private",
        succeeded=False,
        failure_code="private-unknown",
        trigger="private-trigger",
    )
    SearchRun.objects.all().update(created_at=now)
    boundary = SearchRun.objects.create(keyword="boundary")
    SearchRun.objects.filter(pk=boundary.pk).update(created_at=now - timedelta(days=7))
    old = SearchRun.objects.create(keyword="excluded")
    SearchRun.objects.filter(pk=old.pk).update(created_at=now - timedelta(days=7, seconds=1))
    # Keep all freshly created rows before the upper bound.
    with patch(
        "Main.services.admin_monitoring.timezone.now", return_value=now + timedelta(seconds=1)
    ):
        result = snapshot()
    assert result["totals"] == {
        "total": 3,
        "successful": 1,
        "timed": 2,
        "average_ms": 150,
        "maximum_ms": 300,
        "success_rate": 33.3,
    }
    assert {row["label"]: row["count"] for row in result["actors"]} == {
        "ログイン": 1,
        "匿名セッション": 1,
        "所有者なし": 1,
    }
    assert {row["label"] for row in result["failures"]} == {"HTML解析失敗", "未分類"}
    assert "private" not in str(result)
    with patch("Main.services.admin_monitoring.timezone.now", return_value=now):
        assert snapshot()["totals"]["total"] == 4  # Both boundaries are inclusive.


def test_error_filters_and_daily_counts():
    for code in ("404", "500", "client_error", "untrusted-code"):
        ErrorLog.objects.create(error_code=code, error_message="secret")
    assert snapshot()["error_count"] == 4
    assert snapshot(level="warning")["error_count"] == 1
    assert snapshot(kind="browser")["error_count"] == 1
    assert snapshot(kind="http", level="error")["error_count"] == 1
    assert sum(row["count"] for row in snapshot()["daily_errors"]) == 4
    assert snapshot(kind="browser", level="warning")["recent_errors"] == []


def test_dashboard_never_displays_legacy_text_or_identities(client, settings, tmp_path):
    secret = "person@example.test"
    staff = get_user_model().objects.create_user(secret, email=secret, is_staff=True)
    client.force_login(staff)
    ErrorLog.objects.create(
        error_code=secret,
        error_message="Cookie: private-cookie; keyword=private-query",
        file_path="private-path",
    )
    SearchRun.objects.create(
        keyword="private-query",
        session_key="private-session",
        succeeded=False,
        failure_code=secret,
        trigger=secret,
    )
    settings.LOG_DIR = tmp_path
    (tmp_path / "server.log").write_text("private-log", encoding="utf-8")
    response = client.get(reverse("developer_dashboard"))
    body = response.content.decode()
    for value in (
        secret,
        "private-cookie",
        "private-query",
        "private-path",
        "private-session",
        "private-log",
    ):
        assert value not in body
    assert "その他" in body


@pytest.mark.parametrize(
    "query",
    [
        {"days": "0"},
        {"days": "999999"},
        {"days": "bad"},
        {"level": "private-level"},
        {"kind": "private-kind"},
    ],
)
def test_invalid_filters_rejected_without_query_or_value_echo(client, query):
    staff = get_user_model().objects.create_user("filter-staff", is_staff=True)
    client.force_login(staff)
    with patch("Main.views.developer.monitoring_snapshot") as aggregate:
        response = client.get(reverse("developer_dashboard"), query)
    assert response.status_code == 400
    aggregate.assert_not_called()
    assert "private-" not in response.content.decode()


def test_unowned_excludes_valid_anonymous_and_concentration_threshold():
    user = get_user_model().objects.create_user("busy")
    SearchRun.objects.bulk_create([SearchRun(keyword="k", user=user) for _ in range(60)])
    SearchRun.objects.bulk_create(
        [SearchRun(keyword="k", session_key="session-a") for _ in range(59)]
    )
    orphan = SearchRun.objects.create(keyword="orphan")
    anon = SearchRun.objects.filter(session_key="session-a").first()
    WatchItem.objects.create(name="legacy", url="https://example.test/legacy")
    WatchItem.objects.create(name="anon", url="https://example.test/anon", session_key="session-a")
    scraping.objects.create(search_run=orphan, EndPrice=0, StartPrice=0)
    scraping.objects.create(search_run=anon, EndPrice=0, StartPrice=0)
    scraping.objects.create(EndPrice=0, StartPrice=0)
    result = snapshot()
    assert result["high_users"] == 1
    assert result["high_sessions"] == 0
    assert result["unowned_runs"] == 1
    assert result["unowned_watches"] == 1
    assert result["unowned_items"] == 2
    SearchRun.objects.create(keyword="k", session_key="session-a")
    assert snapshot()["high_sessions"] == 1


def test_database_aggregation_failure_has_safe_retry_state(client):
    from django.db import DatabaseError

    staff = get_user_model().objects.create_user("failure-staff", is_staff=True)
    client.force_login(staff)
    with patch(
        "Main.views.developer.monitoring_snapshot", side_effect=DatabaseError("private-sql")
    ):
        response = client.get(reverse("developer_dashboard"))
    assert response.status_code == 503
    assert "監視データを読み込めませんでした" in response.content.decode()
    assert "private-sql" not in response.content.decode()
    assert "monitoringSummary" not in response.content.decode()
