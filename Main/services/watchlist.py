"""ウォッチリストの保存・更新処理。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from Main.domain.buying_opportunity import evaluate_buying_opportunity
from Main.models.watchitem import WatchItem

ALLOWED_WATCH_HOSTS = {"auctions.yahoo.co.jp", "paypayfleamarket.yahoo.co.jp"}


def list_watch_items() -> list[dict[str, Any]]:
    return [serialize_watch_item(item) for item in WatchItem.objects.all()]


def save_watch_item(payload: Mapping[str, Any]) -> tuple[WatchItem, bool]:
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
    item, created = WatchItem.objects.get_or_create(
        url=url,
        defaults={**defaults, "added_price": price},
    )
    if not created:
        for field, value in defaults.items():
            setattr(item, field, value)
        item.save()
    return item, created


def serialize_watch_item(item: WatchItem) -> dict[str, Any]:
    price_change = item.current_price - item.added_price
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
        "createdAt": item.created_at.isoformat(),
        "lastCheckedAt": item.last_checked_at.isoformat(),
    }


def refresh_watched_item(payload: Mapping[str, Any]) -> bool:
    """検索結果に含まれる登録済み商品の価格と判定を更新する。"""
    url = str(payload.get("url") or "").strip()
    try:
        item = WatchItem.objects.get(url=url)
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
    item.save()
    return True


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
