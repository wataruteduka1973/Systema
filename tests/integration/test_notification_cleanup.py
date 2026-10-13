"""Readable notifications: one daily update summary, named titles, richer candidates, filters."""

from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from Main.models.alertrule import AlertRule
from Main.models.notification import Notification
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.services.alert_rules import _alert_title, _candidate_payload
from Main.services.notifications import create_notification, notify_saved_search_run

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user("notify-cleanup", password="password")


def _run(user, saved, *, item_count=5, succeeded=True):
    return SearchRun.objects.create(
        user=user,
        saved_search=saved,
        keyword=saved.keyword,
        search_type=SearchRun.CURRENT,
        item_count=item_count,
        succeeded=succeeded,
        failure_code="" if succeeded else "external_service_unavailable",
    )


def test_successful_runs_fold_into_one_daily_summary_that_keeps_its_read_state(user):
    camera = SavedSearch.objects.create(user=user, name="カメラ", keyword="カメラ")
    lens = SavedSearch.objects.create(user=user, name="レンズ", keyword="レンズ")
    notify_saved_search_run(_run(user, camera, item_count=10))
    summary = Notification.objects.get(user=user)
    summary.read_at = summary.created_at
    summary.save()

    notify_saved_search_run(_run(user, lens, item_count=7))
    notify_saved_search_run(_run(user, camera, item_count=12))

    summary.refresh_from_db()
    assert Notification.objects.filter(user=user).count() == 1
    assert summary.title.startswith("今日の保存検索の更新")
    assert summary.payload["runCount"] == 3
    assert {
        entry["name"]: entry["itemCount"] for entry in summary.payload["searches"].values()
    } == {
        "カメラ": 12,
        "レンズ": 7,
    }
    assert summary.message == "保存検索2件を計3回更新しました。最新は「カメラ」の12件です。"
    assert summary.read_at is not None  # routine updates do not resurface as unread


def test_failed_run_is_its_own_notification_naming_the_saved_search(user):
    saved = SavedSearch.objects.create(user=user, name="Switch 本体", keyword="switch")

    notify_saved_search_run(_run(user, saved, item_count=0, succeeded=False))

    failure = Notification.objects.get(user=user)
    assert failure.event_type == "saved_search_failed"
    assert failure.title == "保存検索「Switch 本体」を更新できませんでした"
    assert "external_service" not in failure.message


def test_alert_titles_name_the_target_and_condition(user):
    saved = SavedSearch.objects.create(user=user, name="ミラーレス", keyword="ミラーレス")
    rule = AlertRule(user=user, saved_search=saved, rule_type="median_discount", threshold_value=20)

    assert _alert_title(rule) == "ミラーレス：相場との差が指定率以上"


def test_candidates_carry_a_safe_image_and_the_market_difference():
    run = SimpleNamespace(
        result_snapshot={"medianPrice": 50000}, created_at=SimpleNamespace(isoformat=lambda: "t")
    )
    safe = _candidate_payload(
        {
            "name": "a",
            "url": "u",
            "price": 38000,
            "imageUrl": "https://auctions.c.yimg.jp/x.jpg",
            "marketComparison": {"differenceRate": -24.0},
        },
        run,
    )
    unsafe = _candidate_payload({"name": "b", "imageUrl": "http://evil.example/x.jpg"}, run)

    assert (safe["imageUrl"], safe["differenceRate"]) == ("https://auctions.c.yimg.jp/x.jpg", -24.0)
    assert (unsafe["imageUrl"], unsafe["differenceRate"]) == ("", None)


def test_notifications_api_filters_by_category(client, user):
    for index, event_type in enumerate(
        ["alert_price_below", "saved_search_failed", "watch_price_drop", "saved_search_succeeded"]
    ):
        create_notification(
            user=user,
            event_type=event_type,
            title=event_type,
            message="",
            dedupe_key=f"k{index}",
            source_type="test",
            source_id=None,
        )
    client.force_login(user)

    def titles(category):
        response = client.get(reverse("notifications"), {"category": category})
        assert response.status_code == 200
        return [item["title"] for item in response.json()["items"]]

    assert titles("alert") == ["alert_price_below"]
    assert titles("failure") == ["saved_search_failed"]
    assert titles("watch") == ["watch_price_drop"]
    assert titles("update") == ["saved_search_succeeded"]
    assert len(titles("")) == 4
    assert client.get(reverse("notifications"), {"category": "other"}).status_code == 400
