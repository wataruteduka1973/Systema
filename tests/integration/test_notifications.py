import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.http import JsonResponse
from django.urls import reverse

from Main.models.notification import Notification
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.services.notifications import create_notification
from Main.services.ownership import RequestOwner
from Main.services.watchlist import save_watch_item
from Main.views import api

pytestmark = pytest.mark.django_db


def make_notification(user, key="event-1"):
    return create_notification(
        user=user,
        event_type="test_event",
        title="テスト通知",
        message="確認してください",
        dedupe_key=key,
        source_type="test",
        source_id=1,
    )[0]


def test_notification_api_requires_login_and_limits_items_to_owner(client):
    first = get_user_model().objects.create_user("notify-first", password="password")
    second = get_user_model().objects.create_user("notify-second", password="password")
    own = make_notification(first, "own")
    other = make_notification(second, "other")

    assert client.get(reverse("notifications")).status_code == 401
    client.force_login(first)

    response = client.get(reverse("notifications"), {"unreadOnly": "true"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [own.pk]
    assert response.json()["unreadCount"] == 1
    assert (
        client.patch(
            reverse("notification_item", args=(other.pk,)),
            json.dumps({"read": True}),
            content_type="application/json",
        ).status_code
        == 404
    )


def test_notification_read_unread_and_read_all(client):
    user = get_user_model().objects.create_user("notify-read", password="password")
    first = make_notification(user, "first")
    second = make_notification(user, "second")
    client.force_login(user)

    response = client.patch(
        reverse("notification_item", args=(first.pk,)),
        json.dumps({"read": True}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["item"]["isRead"] is True

    response = client.patch(
        reverse("notification_item", args=(first.pk,)),
        json.dumps({"read": False}),
        content_type="application/json",
    )
    assert response.json()["item"]["isRead"] is False
    assert client.post(reverse("notifications_read_all"), "{}", "application/json").json() == {
        "updatedCount": 2
    }
    assert not Notification.objects.filter(
        pk__in=(first.pk, second.pk), read_at__isnull=True
    ).exists()


def test_notification_mutations_require_csrf():
    from django.test import Client

    user = get_user_model().objects.create_user("notify-csrf", password="password")
    item = make_notification(user)
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    assert (
        client.patch(
            reverse("notification_item", args=(item.pk,)),
            json.dumps({"read": True}),
            content_type="application/json",
        ).status_code
        == 403
    )
    assert (
        client.post(reverse("notifications_read_all"), "{}", "application/json").status_code == 403
    )


def test_watch_update_creates_deduplicated_price_and_ending_notifications():
    user = get_user_model().objects.create_user("notify-watch")
    owner = RequestOwner(user=user, session_key="")
    base = {
        "name": "カメラ",
        "url": "https://auctions.yahoo.co.jp/jp/auction/notify-watch",
        "currentPrice": 5000,
        "remainingSeconds": 3600,
    }

    item, created = save_watch_item(base, owner)
    assert created is True
    assert Notification.objects.count() == 0

    save_watch_item({**base, "currentPrice": 4000}, owner)
    save_watch_item({**base, "currentPrice": 4000}, owner)

    assert Notification.objects.filter(user=user, event_type="watch_price_drop").count() == 1
    assert Notification.objects.filter(user=user, event_type="watch_ending_soon").count() == 1
    assert Notification.objects.filter(source_id=item.pk).count() == 2


def test_anonymous_watch_does_not_create_notification():
    save_watch_item(
        {
            "name": "匿名商品",
            "url": "https://auctions.yahoo.co.jp/jp/auction/notify-anonymous",
            "currentPrice": 1000,
        },
        RequestOwner(user=None, session_key="anonymous-session"),
    )
    assert Notification.objects.count() == 0


@pytest.mark.parametrize("succeeded", [True, False])
def test_saved_search_run_creates_safe_notification(client, monkeypatch, succeeded):
    user = get_user_model().objects.create_user("notify-search", password="password")
    saved = SavedSearch.objects.create(user=user, name="通知条件", keyword="カメラ")

    def fake_search(request, criteria):
        run = SearchRun.objects.create(
            user=user,
            saved_search=saved,
            keyword=criteria.keyword,
            search_type=SearchRun.CURRENT,
            item_count=3 if succeeded else 0,
            succeeded=succeeded,
            trigger="saved",
            failure_code="external_service" if not succeeded else "",
        )
        request.recorded_search_runs = [run]
        return JsonResponse({"ok": True}, status=200 if succeeded else 503)

    monkeypatch.setattr(api, "complex_market_data_logic", fake_search)
    client.force_login(user)
    response = client.post(reverse("run_saved_search", args=(saved.pk,)))

    notification = Notification.objects.get(user=user)
    assert response.status_code == (200 if succeeded else 503)
    assert notification.event_type == (
        "saved_search_succeeded" if succeeded else "saved_search_failed"
    )
    assert notification.source_id == SearchRun.objects.get().pk
    assert "external_service" not in notification.message


def test_notification_page_is_deduplicated_and_profile_shows_unread_count(client):
    user = get_user_model().objects.create_user("notify-ui", password="password")
    first, created = create_notification(
        user=user,
        event_type="test_event",
        title="通知",
        message="本文",
        dedupe_key="same-event",
        source_type="test",
        source_id=1,
    )
    second, duplicated = create_notification(
        user=user,
        event_type="test_event",
        title="別の通知",
        message="別の本文",
        dedupe_key="same-event",
        source_type="test",
        source_id=1,
    )
    client.force_login(user)

    assert created is True
    assert duplicated is False
    assert first.pk == second.pk
    assert "通知" in client.get(reverse("notifications_page")).content.decode("utf-8")
    assert ">1</span>" in client.get(reverse("profile")).content.decode("utf-8")


@pytest.mark.skipif(connection.vendor != "postgresql", reason="PostgreSQL concurrency check")
@pytest.mark.django_db(transaction=True)
def test_concurrent_notification_creation_is_deduplicated_on_postgresql():
    user = get_user_model().objects.create_user("notify-concurrent")
    barrier = Barrier(2)

    def create_once():
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            return create_notification(
                user=get_user_model().objects.get(pk=user.pk),
                event_type="test_event",
                title="同時通知",
                message="本文",
                dedupe_key="concurrent-event",
                source_type="test",
                source_id=1,
            )[1]
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        created = list(executor.map(lambda _: create_once(), range(2)))

    assert sorted(created) == [False, True]
    assert Notification.objects.filter(user=user, dedupe_key="concurrent-event").count() == 1
