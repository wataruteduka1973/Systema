"""本人所有の在庫登録・更新・購入候補変換。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from Main.domain.profitability import calculate_profitability, decimal_rate
from Main.domain.purchase_budget import calculate_budget, normalize_assumptions
from Main.models.inventoryitem import InventoryItem
from Main.models.watchitem import WatchItem
from Main.services.purchase_budget import latest_decision

INVENTORY_STATUSES = {value for value, _ in InventoryItem.STATUS_CHOICES}


def list_inventory_items(user: Any, status: str | None = None) -> list[dict[str, Any]]:
    items = InventoryItem.objects.filter(user=user).select_related("source_watch_item")
    if status:
        if status not in INVENTORY_STATUSES:
            raise ValueError("在庫状態が正しくありません")
        items = items.filter(status=status)
    return [serialize_inventory_item(item) for item in items]


def save_inventory_item(
    user: Any, payload: Mapping[str, Any], instance: InventoryItem | None = None
) -> InventoryItem:
    item = instance or InventoryItem(user=user)
    if "name" in payload or instance is None:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("商品名は必須です")
        item.name = name
    if "condition" in payload:
        item.condition = str(payload.get("condition") or "unknown")[:20]
    if "category" in payload:
        item.category = str(payload.get("category") or "").strip()[:100]
    if "acquisitionCost" in payload:
        item.acquisition_cost = _non_negative_int(payload["acquisitionCost"], "仕入価格")
    if "status" in payload:
        status = str(payload["status"])
        if status not in INVENTORY_STATUSES:
            raise ValueError("在庫状態が正しくありません")
        item.status = status
        if status == "acquired" and item.acquired_at is None:
            item.acquired_at = timezone.now()
    if "note" in payload:
        item.note = str(payload.get("note") or "")[:2000]
    item.save()
    return item


@transaction.atomic
def convert_watch_to_inventory(
    user: Any, watch_item_id: int, payload: Mapping[str, Any]
) -> tuple[InventoryItem | None, bool]:
    watch_item = WatchItem.objects.select_for_update().filter(user=user, pk=watch_item_id).first()
    if watch_item is None:
        return None, False
    existing = InventoryItem.objects.filter(source_watch_item=watch_item).first()
    if existing:
        return existing, False

    try:
        with transaction.atomic():
            item = InventoryItem.objects.create(
                user=user,
                source_watch_item=watch_item,
                name=str(payload.get("name") or watch_item.name).strip(),
                condition=str(payload.get("condition") or watch_item.condition)[:20],
                category=str(payload.get("category") or watch_item.category).strip()[:100],
                acquisition_cost=_non_negative_int(
                    payload.get("acquisitionCost", watch_item.current_price), "仕入価格"
                ),
                purchase_decision=latest_decision(watch_item),
                acquired_at=timezone.now(),
                status="acquired",
                note=str(payload.get("note") or watch_item.note)[:2000],
            )
    except IntegrityError:
        item = InventoryItem.objects.get(source_watch_item=watch_item)
        return item, False
    watch_item.lifecycle_status = "purchased"
    watch_item.save(update_fields=("lifecycle_status", "updated_at"))
    return item, True


def simulate_inventory_profit(item: InventoryItem, payload: Mapping[str, Any]) -> dict[str, Any]:
    if item.purchase_decision:
        assumptions = {**item.purchase_decision["assumptions"], **normalize_assumptions(payload)}
        return calculate_budget(assumptions, item.acquisition_cost)
    return calculate_profitability(
        sale_price=_non_negative_int(payload.get("salePrice"), "想定販売価格"),
        acquisition_cost=item.acquisition_cost,
        shipping_cost=_non_negative_int(payload.get("shippingCost", 0), "送料"),
        packaging_cost=_non_negative_int(payload.get("packagingCost", 0), "梱包費"),
        other_cost=_non_negative_int(payload.get("otherCost", 0), "その他費用"),
        fee_rate=decimal_rate(payload.get("feeRate", "0.10")),
    )


def serialize_inventory_item(item: InventoryItem) -> dict[str, Any]:
    return {
        "id": item.pk,
        "sourceWatchItemId": item.source_watch_item_id,
        "name": item.name,
        "condition": item.condition,
        "category": item.category,
        "acquisitionCost": item.acquisition_cost,
        "purchaseDecision": item.purchase_decision,
        "acquiredAt": item.acquired_at.isoformat() if item.acquired_at else None,
        "status": item.status,
        "note": item.note,
        "createdAt": item.created_at.isoformat(),
        "updatedAt": item.updated_at.isoformat(),
    }


def _non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label}は0以上の整数で指定してください")
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label}は0以上の整数で指定してください") from error
    if parsed < 0:
        raise ValueError(f"{label}は0以上の整数で指定してください")
    return parsed
