"""所有者限定の出品管理と、費用を含む観測履歴の保存。"""

import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import OuterRef, QuerySet, Subquery
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from Main.domain.profitability import (
    calculate_confirmed_profit,
    calculate_profitability,
    decimal_rate,
)
from Main.domain.seller_listing import money, normalize_listing_url
from Main.domain.seller_status import ACTION_LABELS, assess_listing, listing_price
from Main.models.inventoryitem import InventoryItem
from Main.models.sellerlisting import SaleRecord, SellerListing, SellerListingSnapshot
from Main.scraping.seller_listing import fetch_listing
from Main.services.alert_rules import evaluate_seller_alert_rules
from Main.services.exceptions import SearchRateLimitError

MONEY_FIELDS = {
    "acquisitionCost": "acquisition_cost",
    "purchaseShippingCost": "purchase_shipping_cost",
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
    return SellerListing.objects.select_related("sale_record", "inventory_item").get(
        user=user, pk=listing_id
    )


def listing_queryset(user: Any, status: str = "") -> QuerySet:
    items = SellerListing.objects.filter(user=user).select_related("sale_record")
    if status:
        if status not in STATUS_VALUES:
            raise ValueError("出品状態が正しくありません")
        items = items.filter(status=status)
    return items


def listing_action(item: SellerListing, now: datetime) -> dict[str, str | int]:
    if hasattr(item, "baseline_bids"):
        baseline = item.baseline_bids
    elif item.status == "active" and item.last_checked_at is not None:
        baseline = (
            item.snapshots.filter(
                observed_at__lte=item.last_checked_at - timedelta(hours=24),
                observed_at__gte=item.last_checked_at - timedelta(hours=48),
                observed_status="active",
            )
            .values_list("bidding", flat=True)
            .first()
        )
    else:
        baseline = None
    return assess_listing(
        item,
        now=now,
        baseline_bids=baseline,
        sale_record_exists=hasattr(item, "sale_record"),
    )


def listing_page(
    user: Any, *, status: str, action: str, sort: str, page: int, size: int
) -> dict[str, Any]:
    if action and action not in ACTION_LABELS:
        raise ValueError("対応内容が正しくありません")
    if sort not in {"updated", "priority"}:
        raise ValueError("並び順が正しくありません")
    now = timezone.now()
    baseline = SellerListingSnapshot.objects.filter(
        seller_listing_id=OuterRef("pk"),
        observed_status="active",
        observed_at__lte=OuterRef("last_checked_at") - timedelta(hours=24),
        observed_at__gte=OuterRef("last_checked_at") - timedelta(hours=48),
    ).order_by("-observed_at", "-pk")
    if status and status not in STATUS_VALUES:
        raise ValueError("出品状態が正しくありません")
    items = listing_queryset(user).annotate(baseline_bids=Subquery(baseline.values("bidding")[:1]))
    ranked = []
    action_counts = {key: 0 for key in ACTION_LABELS}
    total = 0
    requires_action = 0
    urgent = 0
    for item in items.defer("purchase_decision", "note").iterator(chunk_size=200):
        assessment = listing_action(item, now)
        total += 1
        action_counts[str(assessment["status"])] += 1
        if assessment["status"] not in {"ok", "sold", "cancelled"}:
            requires_action += 1
        if assessment["priority"] == 1:
            urgent += 1
        if status and item.status != status:
            continue
        if action and assessment["status"] != action:
            continue
        end = item.ends_at.timestamp() if item.ends_at else float("inf")
        key = (
            (int(assessment["priority"]), end, -item.updated_at.timestamp(), -item.pk)
            if sort == "priority"
            else (0, 0, -item.updated_at.timestamp(), -item.pk)
        )
        ranked.append((key, item.pk, assessment))
    ranked.sort(key=lambda row: row[0])
    selected = ranked[(page - 1) * size : page * size]
    records = {
        item.pk: item
        for item in SellerListing.objects.filter(
            user=user, pk__in=[row[1] for row in selected]
        ).select_related("sale_record")
    }
    return {
        "data": [
            serialize_listing(records[pk], action_status=assessment)
            for _, pk, assessment in selected
            if pk in records
        ],
        "meta": {"page": page, "pageSize": size, "total": len(ranked)},
        "summary": {
            "total": total,
            "requiresAction": requires_action,
            "urgent": urgent,
            "saleResultMissing": action_counts["sale_result_missing"],
            "actionCounts": action_counts,
        },
    }


SALE_FIELDS = {
    "salePrice": "sale_price",
    "actualFee": "actual_fee",
    "actualShippingCost": "actual_shipping_cost",
    "actualPackagingCost": "actual_packaging_cost",
    "actualOtherCost": "actual_other_cost",
}


@transaction.atomic
def save_sale_record(user: Any, listing_id: int, payload: Mapping[str, Any]) -> SaleRecord:
    allowed = set(SALE_FIELDS) | {"soldAt"}
    if set(payload) != allowed:
        raise ValueError("販売結果の入力項目が不足しているか、未対応の項目があります")
    listing = SellerListing.objects.select_for_update().get(user=user, pk=listing_id)
    inventory = (
        InventoryItem.objects.select_for_update()
        .filter(user=user, pk=listing.inventory_item_id)
        .first()
        if listing.inventory_item_id
        else None
    )
    values = {field: money(payload[key]) for key, field in SALE_FIELDS.items()}
    if not isinstance(payload["soldAt"], str):
        raise ValueError("販売日時が正しくありません")
    sold_at = parse_datetime(payload["soldAt"])
    if sold_at is None or timezone.is_naive(sold_at):
        raise ValueError("販売日時はタイムゾーン付きの日時で指定してください")
    confirmed_profit = calculate_confirmed_profit(
        **values,
        acquisition_cost=listing.acquisition_cost,
        purchase_shipping_cost=listing.purchase_shipping_cost,
    )
    record, _ = SaleRecord.objects.update_or_create(
        seller_listing=listing,
        defaults={**values, "sold_at": sold_at, "confirmed_profit": confirmed_profit},
    )
    if listing.status != "sold":
        listing.status = "sold"
        listing.save(update_fields=("status", "updated_at"))
    if inventory and inventory.status != "sold":
        inventory.status = "sold"
        inventory.save(update_fields=("status", "updated_at"))
    return record


def serialize_sale_record(record: SaleRecord) -> dict[str, Any]:
    return {
        "salePrice": record.sale_price,
        "actualFee": record.actual_fee,
        "actualShippingCost": record.actual_shipping_cost,
        "actualPackagingCost": record.actual_packaging_cost,
        "actualOtherCost": record.actual_other_cost,
        "soldAt": record.sold_at.isoformat(),
        "confirmedProfit": record.confirmed_profit,
        "updatedAt": record.updated_at.isoformat(),
    }


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
    item.missing_cost_fields = [key for key in item.missing_cost_fields if key not in payload]
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
                item.purchase_decision = inventory.purchase_decision
                if inventory.purchase_decision:
                    assumptions = inventory.purchase_decision["assumptions"]
                    mapping = {
                        "purchaseShipping": "purchaseShippingCost",
                        "shippingCost": "shippingCostEstimate",
                        "packagingCost": "packagingCostEstimate",
                        "otherCost": "otherCostEstimate",
                        "targetProfit": "targetProfit",
                        "feeRate": "feeRate",
                    }
                    inherited = {
                        target: assumptions[key]
                        for key, target in mapping.items()
                        if assumptions[key] is not None
                    }
                    item.missing_cost_fields = [
                        target
                        for key, target in mapping.items()
                        if assumptions[key] is None and key != "targetProfit"
                    ]
                    inherited["predictedSalePrice"] = assumptions["salePrice"]
                    _apply_inputs(item, inherited, creating=False)
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
        "shipping_cost": item.shipping_cost_estimate + item.purchase_shipping_cost,
        "packaging_cost": item.packaging_cost_estimate,
        "other_cost": item.other_cost_estimate,
        "fee_rate": item.fee_rate,
    }


def predicted_price(item: SellerListing) -> tuple[int | None, str]:
    return listing_price(item)


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
        result = (
            calculate_profitability(**inputs)
            if not item.missing_cost_fields
            else {"feeEstimate": None, "estimatedProfit": None}
        )
        snapshot_inputs = {
            **inputs,
            "fee_rate": str(item.fee_rate),
            "price_source": source,
            "target_profit": item.target_profit,
            "purchase_shipping_cost": item.purchase_shipping_cost,
            "missing_cost_fields": item.missing_cost_fields,
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
    evaluate_seller_alert_rules(item)
    return item


def serialize_listing(
    item: SellerListing, *, action_status: dict[str, str | int] | None = None
) -> dict[str, Any]:
    price, source = predicted_price(item)
    profit = (
        calculate_profitability(sale_price=price, **profit_inputs(item))
        if price is not None and not item.missing_cost_fields
        else None
    )
    sale = serialize_sale_record(item.sale_record) if hasattr(item, "sale_record") else None
    return {
        "id": item.pk,
        "inventoryItemId": item.inventory_item_id,
        "purchaseDecision": item.purchase_decision,
        "missingCostFields": item.missing_cost_fields,
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
        "saleRecord": sale,
        "actionStatus": (
            action_status if action_status is not None else listing_action(item, timezone.now())
        ),
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
