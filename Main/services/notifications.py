"""Owner-scoped in-app notification creation and read state."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from Main.models.notification import Notification
from Main.models.searchrun import SearchRun
from Main.models.watchitem import WatchItem, WatchPriceSnapshot

PRICE_DROP = "watch_price_drop"
ENDING_SOON = "watch_ending_soon"
SAVED_SEARCH_SUCCEEDED = "saved_search_succeeded"
SAVED_SEARCH_FAILED = "saved_search_failed"
ENDING_SOON_SECONDS = 24 * 60 * 60
# Filters for the notification page. Unknown categories are rejected by the API.
CATEGORIES = {
    "alert": Q(event_type__startswith="alert_"),
    "failure": Q(event_type=SAVED_SEARCH_FAILED),
    "watch": Q(event_type__startswith="watch_"),
    "update": Q(event_type=SAVED_SEARCH_SUCCEEDED),
}


def create_notification(
    *,
    user: AbstractBaseUser,
    event_type: str,
    title: str,
    message: str,
    dedupe_key: str,
    target_url: str = "",
    source_type: str,
    source_id: int | None,
    payload: dict[str, Any] | None = None,
) -> tuple[Notification, bool]:
    values = {
        "event_type": event_type,
        "title": title,
        "message": message,
        "target_url": target_url,
        "source_type": source_type,
        "source_id": source_id,
        "payload": payload or {},
    }
    try:
        with transaction.atomic():
            return Notification.objects.get_or_create(
                user=user,
                dedupe_key=dedupe_key,
                defaults=values,
            )
    except IntegrityError:
        # A concurrent PostgreSQL transaction may win after get_or_create's lookup.
        return Notification.objects.get(user=user, dedupe_key=dedupe_key), False


def serialize_notification(item: Notification) -> dict[str, Any]:
    return {
        "id": item.pk,
        "eventType": item.event_type,
        "title": item.title,
        "message": item.message,
        "targetUrl": item.target_url,
        "sourceType": item.source_type,
        "sourceId": item.source_id,
        "payload": item.payload,
        "createdAt": item.created_at.isoformat(),
        "readAt": item.read_at.isoformat() if item.read_at else None,
        "isRead": item.read_at is not None,
    }


def notification_page(
    user: AbstractBaseUser,
    *,
    unread_only: bool,
    page: int,
    page_size: int,
    category: str = "",
) -> dict[str, Any]:
    queryset = Notification.objects.filter(user=user)
    if category:
        if category not in CATEGORIES:
            raise ValueError("categoryはalert、failure、watch、updateのいずれかで指定してください")
        queryset = queryset.filter(CATEGORIES[category])
    if unread_only:
        queryset = queryset.filter(read_at__isnull=True)
    total = queryset.count()
    start = (page - 1) * page_size
    return {
        "items": [serialize_notification(item) for item in queryset[start : start + page_size]],
        "page": page,
        "pageSize": page_size,
        "total": total,
        "hasNext": start + page_size < total,
        "unreadCount": Notification.objects.filter(user=user, read_at__isnull=True).count(),
    }


def set_read_state(
    user: AbstractBaseUser, notification_id: int, *, read: bool
) -> Notification | None:
    item = Notification.objects.filter(user=user, pk=notification_id).first()
    if item is None:
        return None
    item.read_at = timezone.now() if read else None
    item.save(update_fields=("read_at",))
    return item


def mark_all_read(user: AbstractBaseUser) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).update(
        read_at=timezone.now()
    )


def notify_watch_observation(
    item: WatchItem,
    *,
    previous_price: int,
    remaining_seconds: int | None,
    snapshot: WatchPriceSnapshot | None,
) -> None:
    if item.user_id is None:
        return
    if item.current_price < previous_price and snapshot is not None:
        create_notification(
            user=item.user,
            event_type=PRICE_DROP,
            title="ウォッチ商品の価格が下がりました",
            message=f"{item.name}が{previous_price:,}円から{item.current_price:,}円になりました。",
            target_url=item.url,
            source_type="watch_item",
            source_id=item.pk,
            dedupe_key=f"watch-price-drop:{item.pk}:{snapshot.pk}",
            payload={"previousPrice": previous_price, "currentPrice": item.current_price},
        )
    if remaining_seconds is not None and 0 < remaining_seconds <= ENDING_SOON_SECONDS:
        day_bucket = timezone.localdate().isoformat()
        create_notification(
            user=item.user,
            event_type=ENDING_SOON,
            title="ウォッチ商品の終了が近づいています",
            message=f"{item.name}は24時間以内に終了する見込みです。",
            target_url=item.url,
            source_type="watch_item",
            source_id=item.pk,
            dedupe_key=f"watch-ending-soon:{item.pk}:{day_bucket}",
            payload={"remainingSeconds": remaining_seconds},
        )


def _daily_update_message(payload: dict[str, Any]) -> str:
    searches = payload["searches"]
    latest = max(searches.values(), key=lambda entry: entry["lastRunId"])
    return (
        f"保存検索{len(searches)}件を計{payload['runCount']}回更新しました。"
        f"最新は「{latest['name']}」の{latest['itemCount']}件です。"
    )


def _record_daily_update(run: SearchRun) -> None:
    """Fold a successful saved-search run into the owner's one update notification for the day.

    Successful runs are routine (the scheduler refreshes every hour), so they no longer create one
    notification each. The summary keeps its read state; re-recording the same run is a no-op.
    """
    day = timezone.localdate()
    entry = {
        "name": run.saved_search.name,
        "itemCount": run.item_count,
        "lastRunId": run.pk,
        "lastRunAt": run.created_at.isoformat(),
    }
    payload = {
        "date": day.isoformat(),
        "runCount": 1,
        "searches": {str(run.saved_search_id): entry},
    }
    with transaction.atomic():
        item, created = create_notification(
            user=run.user,
            event_type=SAVED_SEARCH_SUCCEEDED,
            title=f"今日の保存検索の更新（{day.month}/{day.day}）",
            message=_daily_update_message(payload),
            target_url=reverse("profile"),
            source_type="search_run",
            source_id=run.pk,
            dedupe_key=f"saved-search-daily:{day.isoformat()}",
            payload=payload,
        )
        if created:
            return
        item = Notification.objects.select_for_update().get(pk=item.pk)
        summary = dict(item.payload)
        searches = dict(summary.get("searches") or {})
        previous = searches.get(str(run.saved_search_id))
        if previous and previous.get("lastRunId", 0) >= run.pk:
            return
        searches[str(run.saved_search_id)] = entry
        summary.update(searches=searches, runCount=int(summary.get("runCount") or 0) + 1)
        item.payload = summary
        item.message = _daily_update_message(summary)
        item.source_id = run.pk
        item.save(update_fields=("payload", "message", "source_id"))


def notify_saved_search_run(run: SearchRun) -> None:
    if run.user_id is None or run.saved_search_id is None:
        return
    target_url = f"{reverse('profile')}?saved_search={run.saved_search_id}#saved-search-results"
    if run.succeeded:
        _record_daily_update(run)
    else:
        create_notification(
            user=run.user,
            event_type=SAVED_SEARCH_FAILED,
            title=f"保存検索「{run.saved_search.name}」を更新できませんでした"[:200],
            message="外部データの取得または分析に失敗しました。時間をおいて再実行してください。",
            target_url=target_url,
            source_type="search_run",
            source_id=run.pk,
            dedupe_key=f"saved-search-failed:{run.pk}",
            payload={"savedSearchId": run.saved_search_id, "failureCode": run.failure_code},
        )
