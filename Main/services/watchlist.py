"""ウォッチリストの保存・更新処理。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

from django.db import transaction
from django.utils import timezone

from Main.domain.buying_opportunity import evaluate_buying_opportunity
from Main.models.watchitem import WatchItem, WatchPriceSnapshot
from Main.services.ownership import RequestOwner, owner_query
from Main.services.watchlist_analysis import analyze_watch_history

ALLOWED_WATCH_HOSTS = {"auctions.yahoo.co.jp", "paypayfleamarket.yahoo.co.jp"}
LIFECYCLE_STATUSES = {"active", "purchased", "skipped", "ended", "archived"}
SNAPSHOT_MIN_INTERVAL = timedelta(minutes=15)


def list_watch_items(
    owner: RequestOwner,
    *,
    lifecycle_status: str | None = None,
    priority: int | None = None,
    condition: str | None = None,
) -> list[dict[str, Any]]:
    items = WatchItem.objects.filter(owner_query(owner)).prefetch_related("price_snapshots")
    if lifecycle_status:
        if lifecycle_status not in LIFECYCLE_STATUSES:
            raise ValueError("ウォッチ状態が正しくありません")
        items = items.filter(lifecycle_status=lifecycle_status)
    if priority is not None:
        if priority not in range(4):
            raise ValueError("優先度は0から3で指定してください")
        items = items.filter(priority=priority)
    if condition:
        items = items.filter(condition=condition[:20])
    return [serialize_watch_item(item) for item in items]


@transaction.atomic
def save_watch_item(payload: Mapping[str, Any], owner: RequestOwner) -> tuple[WatchItem, bool]:
    name = str(payload.get("name") or "").strip()
    url = str(payload.get("url") or "").strip()
    if not name:
        raise ValueError("商品名は必須です")
    if not _is_allowed_url(url):
        raise ValueError("Yahoo!オークションの商品URLを指定してください")

    price = _non_negative_int(payload.get("currentPrice", payload.get("price")))
    median_price = _non_negative_int(payload.get("marketMedian"))
    bidding = _non_negative_int(payload.get("bidding"))
    condition = str(payload.get("condition") or "unknown")[:20]
    remaining_seconds = payload.get("remainingSeconds")
    decision = evaluate_buying_opportunity(price, median_price, condition, remaining_seconds)

    defaults = {
        "name": name,
        "search_keyword": str(payload.get("searchKeyword") or "")[:255],
        "current_price": price,
        "bidding": bidding,
        "remaining_time": str(payload.get("remainingTime") or "")[:100],
        "condition": condition,
        "condition_label": str(payload.get("conditionLabel") or "未分類")[:50],
        "market_median": median_price,
        "buy_status": decision["status"],
        "buy_label": decision["label"],
        "buy_score": decision["score"],
        "buy_reason": decision["reason"],
    }
    item, created = WatchItem.objects.select_for_update().get_or_create(
        **owner.model_values,
        url=url,
        defaults={**defaults, "added_price": price},
    )
    if not created:
        price_changed = item.current_price != price
        for field, value in defaults.items():
            setattr(item, field, value)
        if price_changed:
            item.last_price_change_at = timezone.now()
        item.save()
    _record_snapshot(
        item,
        remaining_seconds=_optional_non_negative_int(payload.get("remainingSeconds")),
        force=created,
    )
    return item, created


def serialize_watch_item(item: WatchItem) -> dict[str, Any]:
    price_change = item.current_price - item.added_price
    snapshots = list(item.price_snapshots.all())
    return {
        "id": item.pk,
        "name": item.name,
        "url": item.url,
        "searchKeyword": item.search_keyword,
        "currentPrice": item.current_price,
        "addedPrice": item.added_price,
        "priceChange": price_change,
        "bidding": item.bidding,
        "remainingTime": item.remaining_time,
        "condition": item.condition,
        "conditionLabel": item.condition_label,
        "marketMedian": item.market_median,
        "buyDecision": {
            "status": item.buy_status,
            "label": item.buy_label,
            "score": item.buy_score,
            "reason": item.buy_reason,
        },
        "note": item.note,
        "priority": item.priority,
        "category": item.category,
        "lifecycleStatus": item.lifecycle_status,
        "endedAt": item.ended_at.isoformat() if item.ended_at else None,
        "archivedAt": item.archived_at.isoformat() if item.archived_at else None,
        "lastPriceChangeAt": (
            item.last_price_change_at.isoformat() if item.last_price_change_at else None
        ),
        "historyAnalysis": analyze_watch_history(snapshots, item.market_median),
        "createdAt": item.created_at.isoformat(),
        "lastCheckedAt": item.last_checked_at.isoformat(),
    }


@transaction.atomic
def refresh_watched_item(payload: Mapping[str, Any], owner: RequestOwner) -> bool:
    """検索結果に含まれる登録済み商品の価格と判定を更新する。"""
    url = str(payload.get("url") or "").strip()
    try:
        item = WatchItem.objects.select_for_update().get(owner_query(owner), url=url)
    except WatchItem.DoesNotExist:
        return False

    price = _non_negative_int(payload.get("price", payload.get("currentPrice")))
    median_price = _non_negative_int(payload.get("marketMedian"))
    decision = evaluate_buying_opportunity(
        price,
        median_price,
        str(payload.get("condition") or item.condition),
        payload.get("remainingSeconds"),
    )
    price_changed = item.current_price != price
    item.name = str(payload.get("name") or item.name)
    item.current_price = price
    item.bidding = _non_negative_int(payload.get("bidding"))
    item.remaining_time = str(payload.get("remainingTime") or "")[:100]
    item.condition = str(payload.get("condition") or item.condition)[:20]
    item.condition_label = str(payload.get("conditionLabel") or item.condition_label)[:50]
    item.market_median = median_price
    item.buy_status = decision["status"]
    item.buy_label = decision["label"]
    item.buy_score = decision["score"]
    item.buy_reason = decision["reason"]
    if price_changed:
        item.last_price_change_at = timezone.now()
    item.save()
    _record_snapshot(
        item,
        remaining_seconds=_optional_non_negative_int(payload.get("remainingSeconds")),
    )
    return True


@transaction.atomic
def update_watch_item(
    item_id: int, payload: Mapping[str, Any], owner: RequestOwner
) -> WatchItem | None:
    try:
        item = WatchItem.objects.select_for_update().get(owner_query(owner), pk=item_id)
    except WatchItem.DoesNotExist:
        return None

    if "note" in payload:
        item.note = str(payload["note"] or "")[:2000]
    if "category" in payload:
        item.category = str(payload["category"] or "").strip()[:100]
    if "priority" in payload:
        item.priority = _priority_value(payload["priority"])
    if "lifecycleStatus" in payload:
        lifecycle_status = str(payload["lifecycleStatus"])
        if lifecycle_status not in LIFECYCLE_STATUSES:
            raise ValueError("ウォッチ状態が正しくありません")
        now = timezone.now()
        item.lifecycle_status = lifecycle_status
        if lifecycle_status == "ended" and item.ended_at is None:
            item.ended_at = now
        if lifecycle_status == "archived":
            item.archived_at = item.archived_at or now
        else:
            item.archived_at = None
    item.save()
    return item


def serialize_watch_snapshots(item: WatchItem) -> dict[str, Any]:
    snapshots = list(item.price_snapshots.all())
    return {
        "itemId": item.pk,
        "snapshots": [
            {
                "price": snapshot.price,
                "bidding": snapshot.bidding,
                "remainingSeconds": snapshot.remaining_seconds,
                "condition": snapshot.condition,
                "observedAt": snapshot.observed_at.isoformat(),
            }
            for snapshot in snapshots
        ],
        "analysis": analyze_watch_history(snapshots, item.market_median),
    }


def _record_snapshot(
    item: WatchItem, *, remaining_seconds: int | None, force: bool = False
) -> None:
    latest = item.price_snapshots.order_by("-observed_at", "-pk").first()
    significant_change = (
        latest is None
        or latest.price != item.current_price
        or latest.bidding != item.bidding
        or latest.condition != item.condition
    )
    interval_elapsed = (
        latest is not None and timezone.now() - latest.observed_at >= SNAPSHOT_MIN_INTERVAL
    )
    if force or significant_change or interval_elapsed:
        WatchPriceSnapshot.objects.create(
            watch_item=item,
            price=item.current_price,
            bidding=item.bidding,
            remaining_seconds=remaining_seconds,
            condition=item.condition,
        )


def _is_allowed_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and parsed.hostname in ALLOWED_WATCH_HOSTS


def _non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if not isinstance(value, (int, float, str)):
        return 0
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def _optional_non_negative_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return _non_negative_int(value)


def _priority_value(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("優先度は0から3で指定してください")
    try:
        priority = int(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError("優先度は0から3で指定してください") from error
    if priority not in range(4):
        raise ValueError("優先度は0から3で指定してください")
    return priority
