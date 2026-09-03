"""所有者限定の出品管理と、費用を含む観測履歴の保存。"""

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from Main.domain.profitability import calculate_profitability, decimal_rate
from Main.domain.seller_listing import money, normalize_listing_url
from Main.models.inventoryitem import InventoryItem
from Main.models.sellerlisting import SellerListing, SellerListingSnapshot
from Main.scraping.seller_listing import fetch_listing
from Main.services.exceptions import SearchRateLimitError

MONEY_FIELDS = {
    "acquisitionCost": "acquisition_cost",
    "shippingCostEstimate": "shipping_cost_estimate",
    "packagingCostEstimate": "packaging_cost_estimate",
    "otherCostEstimate": "other_cost_estimate",
    "targetProfit": "target_profit",
    "marketMedian": "market_median",
}
STATUS_VALUES = {value for value, _ in SellerListing.STATUS_CHOICES}


class ListingConflictError(ValueError):
    pass


def owned_listing(user: Any, listing_id: int) -> SellerListing:
    return SellerListing.objects.get(user=user, pk=listing_id)


def listing_queryset(user: Any, status: str = "") -> QuerySet:
    items = SellerListing.objects.filter(user=user)
    if status:
        if status not in STATUS_VALUES:
            raise ValueError("出品状態が正しくありません")
        items = items.filter(status=status)
    return items


def _apply_inputs(item: SellerListing, payload: Mapping[str, Any], *, creating: bool) -> None:
    allowed = set(MONEY_FIELDS) | {
        "name",
        "condition",
        "note",
        "status",
        "feeRate",
        "predictedSalePrice",
    }
    if creating:
        allowed |= {"url", "inventoryItemId"}
    if set(payload) - allowed:
        raise ValueError("未対応の入力項目があります。認証情報や計算済み利益は送信できません")
    for key, field in MONEY_FIELDS.items():
        if key in payload:
            setattr(item, field, money(payload[key]))
    if "predictedSalePrice" in payload:
        item.predicted_sale_price = (
            None if payload["predictedSalePrice"] is None else money(payload["predictedSalePrice"])
        )
    if "feeRate" in payload:
        rate = decimal_rate(payload["feeRate"])
        if rate != rate.quantize(Decimal("0.00001")):
            raise ValueError("手数料率は小数点以下5桁以内で指定してください")
        item.fee_rate = rate
    for key, limit in (("name", 1000), ("note", 2000), ("condition", 20)):
        if key in payload:
            value = payload[key]
            if (
                not isinstance(value, str)
                or len(value) > limit
                or (key == "name" and not value.strip())
            ):
                raise ValueError(f"{key}の入力が正しくありません")
            setattr(item, key, value.strip())
    if "status" in payload:
        if not isinstance(payload["status"], str) or payload["status"] not in STATUS_VALUES:
            raise ValueError("出品状態が正しくありません")
        item.status = payload["status"]


def create_listing(user: Any, payload: Mapping[str, Any]) -> SellerListing:
    url, external_id = normalize_listing_url(payload.get("url"))
    item = SellerListing(user=user, url=url, external_listing_id=external_id, name=external_id)
    inventory_id = payload.get("inventoryItemId")
    try:
        with transaction.atomic():
            if inventory_id is not None:
                if (
                    isinstance(inventory_id, bool)
                    or re.fullmatch(r"[0-9]{1,19}", str(inventory_id)) is None
                    or not 1 <= int(str(inventory_id)) <= 9_223_372_036_854_775_807
                ):
                    raise ValueError("在庫IDが正しくありません")
                inventory = (
                    InventoryItem.objects.select_for_update()
                    .filter(user=user, pk=inventory_id)
                    .first()
                )
                if inventory is None:
                    raise SellerListing.DoesNotExist
                item.inventory_item = inventory
                item.name = inventory.name
                item.condition = inventory.condition
                item.acquisition_cost = inventory.acquisition_cost
            _apply_inputs(item, payload, creating=True)
            item.save()
    except IntegrityError as error:
        raise ListingConflictError("この出品はすでに登録されています") from error
    return item


@transaction.atomic
def update_listing(user: Any, listing_id: int, payload: Mapping[str, Any]) -> SellerListing:
    item = SellerListing.objects.select_for_update().get(user=user, pk=listing_id)
    _apply_inputs(item, payload, creating=False)
    item.save()
    return item


def enforce_refresh_limit(user: Any) -> None:
    limit = getattr(settings, "SELLER_REFRESH_RATE_LIMIT", 10)
    window = getattr(settings, "SELLER_REFRESH_RATE_WINDOW_SECONDS", 60)
    key = f"seller-refresh:{user.pk}"
    if cache.add(key, 1, timeout=window):
        return
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window)
        return
    if count > limit:
        raise SearchRateLimitError(window)


def profit_inputs(item: SellerListing) -> dict[str, Any]:
    return {
        "acquisition_cost": item.acquisition_cost,
        "shipping_cost": item.shipping_cost_estimate,
        "packaging_cost": item.packaging_cost_estimate,
        "other_cost": item.other_cost_estimate,
        "fee_rate": item.fee_rate,
    }


def predicted_price(item: SellerListing) -> tuple[int | None, str]:
    if item.predicted_sale_price is not None:
        return item.predicted_sale_price, "manual"
    if item.last_checked_at is not None:
        return item.current_price, "currentPrice"
    if item.market_median:
        return item.market_median, "manualMarketMedian"
    return None, "unknown"


def remaining_seconds(item: SellerListing) -> int | None:
    return max(0, int((item.ends_at - timezone.now()).total_seconds())) if item.ends_at else None


def refresh_listing(user: Any, listing_id: int) -> SellerListing:
    initial = owned_listing(user, listing_id)
    enforce_refresh_limit(user)
    observation = fetch_listing(initial.url)  # No DB transaction across external I/O.
    observed_at = timezone.now()
    with transaction.atomic():
        item = SellerListing.objects.select_for_update().get(user=user, pk=listing_id)
        if item.updated_at != initial.updated_at:
            raise ListingConflictError("取得中に出品が変更されました。再度更新してください")
        item.name = observation.name
        item.current_price = observation.current_price
        item.start_price = observation.start_price
        item.buyout_price = observation.buyout_price
        item.starts_at = observation.starts_at
        item.bidding = observation.bidding
        item.ends_at = observation.ends_at
        item.observed_status = observation.status
        if item.status in {"draft", "active", "ended"}:
            item.status = observation.status
        item.last_checked_at = observed_at
        item.save()
        price, source = predicted_price(item)
        inputs = profit_inputs(item)
        inputs["sale_price"] = price
        result = calculate_profitability(**inputs)
        snapshot_inputs = {
            **inputs,
            "fee_rate": str(item.fee_rate),
            "price_source": source,
            "target_profit": item.target_profit,
        }
        SellerListingSnapshot.objects.create(
            seller_listing=item,
            current_price=item.current_price,
            bidding=item.bidding,
            remaining_seconds=remaining_seconds(item),
            market_median=item.market_median,
            predicted_sale_price=price,
            estimated_fee=result["feeEstimate"],
            estimated_profit=result["estimatedProfit"],
            calculation_inputs=snapshot_inputs,
            observed_status=observation.status,
            observed_at=observed_at,
        )
    return item


def serialize_listing(item: SellerListing) -> dict[str, Any]:
    price, source = predicted_price(item)
    profit = (
        calculate_profitability(sale_price=price, **profit_inputs(item))
        if price is not None
        else None
    )
    return {
        "id": item.pk,
        "inventoryItemId": item.inventory_item_id,
        "url": item.url,
        "externalListingId": item.external_listing_id,
        "name": item.name,
        "condition": item.condition,
        "status": item.status,
        "observedStatus": item.observed_status,
        "currentPrice": item.current_price if item.last_checked_at else None,
        "startPrice": item.start_price if item.last_checked_at else None,
        "buyoutPrice": item.buyout_price,
        "startsAt": item.starts_at.isoformat() if item.starts_at else None,
        "bidding": item.bidding if item.last_checked_at else None,
        "endsAt": item.ends_at.isoformat() if item.ends_at else None,
        "remainingSeconds": remaining_seconds(item),
        "lastCheckedAt": item.last_checked_at.isoformat() if item.last_checked_at else None,
        "updatedAt": item.updated_at.isoformat(),
        "feeRate": str(item.fee_rate),
        "note": item.note,
        "predictedSalePrice": item.predicted_sale_price,
        "priceSource": source,
        **{key: getattr(item, field) for key, field in MONEY_FIELDS.items()},
        "profit": profit,
    }


def serialize_snapshot(item: SellerListingSnapshot) -> dict[str, Any]:
    return {
        "id": item.pk,
        "observedAt": item.observed_at.isoformat(),
        "currentPrice": item.current_price,
        "bidding": item.bidding,
        "remainingSeconds": item.remaining_seconds,
        "marketMedian": item.market_median,
        "predictedSalePrice": item.predicted_sale_price,
        "estimatedFee": item.estimated_fee,
        "estimatedProfit": item.estimated_profit,
        "calculationInputs": item.calculation_inputs,
        "observedStatus": item.observed_status,
    }
