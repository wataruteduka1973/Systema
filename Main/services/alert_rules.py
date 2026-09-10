"""Owner-scoped alert-rule CRUD and synchronous evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from Main.domain.purchase_budget import calculate_budget
from Main.models.alertrule import AlertRule
from Main.models.purchasebudget import CostSettings
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.models.sellerlisting import SellerListing, SellerListingSnapshot
from Main.models.watchitem import WatchItem
from Main.services.notifications import create_notification

WATCH_TARGET = "watchItemId"
SAVED_SEARCH_TARGET = "savedSearchId"
SELLER_TARGET = "sellerListingId"
TARGET_FIELDS = (WATCH_TARGET, SAVED_SEARCH_TARGET, SELLER_TARGET)


class AlertRuleInputError(ValueError):
    pass


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise AlertRuleInputError(f"{field}は0以上の数値で指定してください")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise AlertRuleInputError(f"{field}は0以上の数値で指定してください") from None
    if not result.is_finite() or result < 0:
        raise AlertRuleInputError(f"{field}は0以上の数値で指定してください")
    return result


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise AlertRuleInputError(f"{field}は1以上の整数で指定してください")
    raw = str(value).strip()
    try:
        result = int(raw)
    except (TypeError, ValueError):
        raise AlertRuleInputError(f"{field}は1以上の整数で指定してください") from None
    if result < 1 or raw != str(result):
        raise AlertRuleInputError(f"{field}は1以上の整数で指定してください")
    return result


def _target_for_payload(user: AbstractBaseUser, payload: Mapping[str, Any]) -> dict[str, Any]:
    supplied = [key for key in TARGET_FIELDS if payload.get(key) is not None]
    if len(supplied) != 1:
        raise AlertRuleInputError(
            "対象はsavedSearchId、watchItemId、sellerListingIdのいずれか1件です"
        )
    key = supplied[0]
    identifier = _positive_int(payload[key], key)
    if key == WATCH_TARGET:
        item = WatchItem.objects.filter(user=user, pk=identifier).first()
        if item is None:
            raise AlertRuleInputError("ウォッチ商品が見つかりません")
        return {"watch_item": item}
    if key == SAVED_SEARCH_TARGET:
        item = SavedSearch.objects.filter(user=user, pk=identifier).first()
        if item is None:
            raise AlertRuleInputError("保存検索が見つかりません")
        return {"saved_search": item}
    item = SellerListing.objects.filter(user=user, pk=identifier).first()
    if item is None:
        raise AlertRuleInputError("出品が見つかりません")
    return {"seller_listing": item}


def _validate_rule_target(rule_type: str, target: Mapping[str, Any]) -> None:
    if ("watch_item" in target or "saved_search" in target) and rule_type not in dict(
        AlertRule.BUYER_RULE_TYPES
    ):
        raise AlertRuleInputError("購入候補には購入候補向けルールだけを設定できます")
    if "watch_item" in target and rule_type in {"new_listing", "within_budget"}:
        raise AlertRuleInputError("新着候補と購入上限内は保存検索に設定してください")
    if "seller_listing" in target and rule_type not in dict(AlertRule.SELLER_RULE_TYPES):
        raise AlertRuleInputError("出品には出品向けルールだけを設定できます")


def save_alert_rule(
    user: AbstractBaseUser, payload: Mapping[str, Any], instance: AlertRule | None = None
) -> AlertRule:
    allowed = {*TARGET_FIELDS, "ruleType", "thresholdValue", "cooldownMinutes", "isEnabled"}
    if set(payload) - allowed:
        raise AlertRuleInputError("未対応の入力項目があります")
    required = {"ruleType", "thresholdValue", "cooldownMinutes"}
    if instance is None:
        missing = required - set(payload)
        if missing:
            raise AlertRuleInputError(f"必須項目が不足しています: {', '.join(sorted(missing))}")
        target = _target_for_payload(user, payload)
        item = AlertRule(user=user, **target)
    else:
        item = instance
        target = (
            {"watch_item": item.watch_item}
            if item.watch_item_id
            else (
                {"saved_search": item.saved_search}
                if item.saved_search_id
                else {"seller_listing": item.seller_listing}
            )
        )
        if any(key in payload for key in TARGET_FIELDS):
            target = _target_for_payload(user, payload)
            item.saved_search = target.get("saved_search")
            item.watch_item = target.get("watch_item")
            item.seller_listing = target.get("seller_listing")
    rule_type = str(payload.get("ruleType", item.rule_type)).strip()
    if rule_type not in dict(AlertRule.RULE_TYPES):
        raise AlertRuleInputError("ruleTypeが不正です")
    _validate_rule_target(rule_type, target)
    item.rule_type = rule_type
    item.threshold_value = _decimal(
        payload.get("thresholdValue", item.threshold_value), "thresholdValue"
    )
    item.cooldown_minutes = _positive_int(
        payload.get("cooldownMinutes", item.cooldown_minutes), "cooldownMinutes"
    )
    if "isEnabled" in payload:
        if not isinstance(payload["isEnabled"], bool):
            raise AlertRuleInputError("isEnabledはtrueまたはfalseで指定してください")
        item.is_enabled = payload["isEnabled"]
    item.save()
    return item


def serialize_alert_rule(item: AlertRule) -> dict[str, Any]:
    target_type, target_id, target_label = (
        ("watchItem", item.watch_item_id, item.watch_item.name)
        if item.watch_item_id
        else (
            ("savedSearch", item.saved_search_id, item.saved_search.name)
            if item.saved_search_id
            else ("sellerListing", item.seller_listing_id, item.seller_listing.name)
        )
    )
    return {
        "id": item.pk,
        "targetType": target_type,
        "targetId": target_id,
        "targetLabel": target_label,
        "ruleType": item.rule_type,
        "ruleLabel": item.get_rule_type_display(),
        "thresholdValue": str(item.threshold_value),
        "isEnabled": item.is_enabled,
        "cooldownMinutes": item.cooldown_minutes,
        "lastTriggeredAt": item.last_triggered_at.isoformat() if item.last_triggered_at else None,
    }


def list_alert_rules(user: AbstractBaseUser) -> list[dict[str, Any]]:
    items = AlertRule.objects.filter(user=user).select_related(
        "watch_item", "saved_search", "seller_listing"
    )
    return [serialize_alert_rule(item) for item in items]


def _ready(rule: AlertRule, now: Any) -> bool:
    return (
        not rule.last_triggered_at
        or (now - rule.last_triggered_at).total_seconds() >= rule.cooldown_minutes * 60
    )


def _emit(
    rule: AlertRule,
    *,
    now: Any,
    message: str,
    target_url: str,
    payload: dict[str, Any],
) -> bool:
    bucket = int(now.timestamp() // (rule.cooldown_minutes * 60))
    _, created = create_notification(
        user=rule.user,
        event_type=f"alert_{rule.rule_type}",
        title="アラート条件に一致しました",
        message=message,
        target_url=target_url,
        source_type="alert_rule",
        source_id=rule.pk,
        dedupe_key=f"alert-rule:{rule.pk}:{bucket}",
        payload={"alertRuleId": rule.pk, "ruleType": rule.rule_type, **payload},
    )
    if created:
        rule.last_triggered_at = now
        rule.save(update_fields=("last_triggered_at",))
    return created


def _buyer_match(
    rule_type: str, threshold: Decimal, item: Mapping[str, Any], median: Decimal
) -> bool:
    price = Decimal(str(item.get("price") or item.get("currentPrice") or 0))
    bidding = Decimal(str(item.get("bidding") or 0))
    remaining = item.get("remainingSeconds")
    raw_decision = item.get("buyDecision")
    decision: Mapping[str, Any] = raw_decision if isinstance(raw_decision, dict) else {}
    score = Decimal(str(decision.get("score") or item.get("buyScore") or 0))
    if rule_type == "price_below":
        return price > 0 and price <= threshold
    if rule_type == "median_discount":
        return median > 0 and price > 0 and ((median - price) / median) * 100 >= threshold
    if rule_type == "ending_soon":
        return (
            isinstance(remaining, (int, float)) and 0 <= Decimal(str(remaining)) / 60 <= threshold
        )
    if rule_type == "low_bids":
        return bidding <= threshold
    if rule_type == "buy_score":
        return score >= threshold
    return False


def evaluate_watch_alert_rules(item: WatchItem, *, remaining_seconds: int | None) -> int:
    """Evaluate enabled watch rules after a successful observation."""
    if item.user_id is None:
        return 0
    now = timezone.now()
    created_count = 0
    source = {
        "price": item.current_price,
        "bidding": item.bidding,
        "remainingSeconds": remaining_seconds,
        "buyScore": item.buy_score,
    }
    for rule_id in AlertRule.objects.filter(
        user=item.user, watch_item=item, is_enabled=True
    ).values_list("pk", flat=True):
        with transaction.atomic():
            rule = AlertRule.objects.select_for_update().select_related("user").get(pk=rule_id)
            if not _ready(rule, now) or not _buyer_match(
                rule.rule_type, rule.threshold_value, source, Decimal(item.market_median)
            ):
                continue
            created_count += int(
                _emit(
                    rule,
                    now=now,
                    message=f"{item.name}が「{rule.get_rule_type_display()}」に一致しました。",
                    target_url=item.url,
                    payload={
                        "watchItemId": item.pk,
                        "currentPrice": item.current_price,
                        "marketMedian": item.market_median,
                        "bidding": item.bidding,
                        "buyScore": item.buy_score,
                        "remainingSeconds": remaining_seconds,
                        "observedAt": item.last_checked_at.isoformat(),
                    },
                )
            )
    return created_count


def _candidate_payload(item: Mapping[str, Any], run: SearchRun) -> dict[str, Any]:
    return {
        "name": str(item.get("name") or ""),
        "url": str(item.get("url") or ""),
        "currentPrice": item.get("price") or item.get("currentPrice"),
        "bidding": item.get("bidding"),
        "remainingSeconds": item.get("remainingSeconds"),
        "marketMedian": run.result_snapshot.get("medianPrice"),
        "buyDecision": item.get("buyDecision") or {},
        "observedAt": run.created_at.isoformat(),
    }


def evaluate_saved_search_alert_rules(run: SearchRun) -> int:
    """Evaluate a successful current-listing snapshot; failed runs never imply change."""
    if not run.succeeded or run.user_id is None or run.saved_search_id is None:
        return 0
    snapshot = run.result_snapshot
    items = snapshot.get("recommend_items", []) if isinstance(snapshot, dict) else []
    if not isinstance(items, list):
        return 0
    previous = (
        SearchRun.objects.filter(
            user=run.user,
            saved_search_id=run.saved_search_id,
            search_type=SearchRun.CURRENT,
            succeeded=True,
            pk__lt=run.pk,
        )
        .exclude(result_snapshot={})
        .first()
    )
    previous_items = previous.result_snapshot.get("recommend_items", []) if previous else []
    previous_urls = {
        str(item.get("url"))
        for item in previous_items
        if isinstance(item, dict) and item.get("url")
    }
    median = Decimal(str(snapshot.get("medianPrice") or 0))
    settings_record = CostSettings.objects.filter(user=run.user).first()
    assumptions = dict(settings_record.assumptions) if settings_record else {}
    now = timezone.now()
    created_count = 0
    for rule_id in AlertRule.objects.filter(
        user=run.user, saved_search_id=run.saved_search_id, is_enabled=True
    ).values_list("pk", flat=True):
        with transaction.atomic():
            rule = AlertRule.objects.select_for_update().select_related("user").get(pk=rule_id)
            if not _ready(rule, now):
                continue
            candidates: list[dict[str, Any]] = []
            for raw in items:
                if not isinstance(raw, dict):
                    continue
                matched = False
                evidence: dict[str, Any] = {}
                if rule.rule_type == "new_listing":
                    matched = (
                        previous is not None
                        and bool(raw.get("url"))
                        and raw.get("url") not in previous_urls
                    )
                elif rule.rule_type == "within_budget":
                    price = raw.get("price") or raw.get("currentPrice")
                    budget_inputs = {
                        "salePrice": int(median) if median > 0 else None,
                        **assumptions,
                    }
                    if isinstance(price, (int, float)):
                        result = calculate_budget(budget_inputs, int(price))
                        matched = result["status"] == "within_budget"
                        evidence = {"costAssumptions": assumptions, "budget": result}
                else:
                    matched = _buyer_match(rule.rule_type, rule.threshold_value, raw, median)
                if matched:
                    candidates.append({**_candidate_payload(raw, run), **evidence})
            if not candidates:
                continue
            target_url = (
                f"{reverse('profile')}?saved_search={run.saved_search_id}#saved-search-results"
            )
            created_count += int(
                _emit(
                    rule,
                    now=now,
                    message=(
                        f"保存検索「{run.saved_search.name}」で{len(candidates)}件が"
                        f"「{rule.get_rule_type_display()}」に一致しました。"
                    ),
                    target_url=target_url,
                    payload={
                        "savedSearchId": run.saved_search_id,
                        "searchRunId": run.pk,
                        "candidateCount": len(candidates),
                        "candidates": candidates[:20],
                    },
                )
            )
    return created_count


def _seller_match(
    rule: AlertRule,
    latest: SellerListingSnapshot,
    previous: SellerListingSnapshot | None,
) -> bool:
    threshold = rule.threshold_value
    if rule.rule_type == "ending_without_bids":
        return (
            latest.bidding == 0
            and latest.remaining_seconds is not None
            and 0 <= Decimal(latest.remaining_seconds) / 60 <= threshold
        )
    if rule.rule_type == "loss_risk":
        return latest.estimated_profit is not None and latest.estimated_profit <= -threshold
    if rule.rule_type == "target_profit":
        return latest.estimated_profit is not None and latest.estimated_profit >= threshold
    if rule.rule_type == "market_decline":
        return (
            previous is not None
            and previous.market_median > 0
            and (
                (Decimal(previous.market_median - latest.market_median) / previous.market_median)
                * 100
            )
            >= threshold
        )
    if rule.rule_type == "bid_stalled":
        if previous is None or latest.bidding != previous.bidding:
            return False
        elapsed_hours = (
            Decimal(str((latest.observed_at - previous.observed_at).total_seconds())) / 3600
        )
        return elapsed_hours >= threshold
    return False


def evaluate_seller_alert_rules(item: SellerListing) -> int:
    """Evaluate seller rules only after a persisted successful public-page observation."""
    snapshots = list(item.snapshots.all()[:2])
    if not snapshots:
        return 0
    latest, previous = snapshots[0], snapshots[1] if len(snapshots) > 1 else None
    now = timezone.now()
    created_count = 0
    for rule_id in AlertRule.objects.filter(
        user=item.user, seller_listing=item, is_enabled=True
    ).values_list("pk", flat=True):
        with transaction.atomic():
            rule = AlertRule.objects.select_for_update().select_related("user").get(pk=rule_id)
            if not _ready(rule, now) or not _seller_match(rule, latest, previous):
                continue
            created_count += int(
                _emit(
                    rule,
                    now=now,
                    message=f"{item.name}が「{rule.get_rule_type_display()}」に一致しました。",
                    target_url=reverse("seller_management"),
                    payload={
                        "sellerListingId": item.pk,
                        "currentPrice": latest.current_price,
                        "bidding": latest.bidding,
                        "remainingSeconds": latest.remaining_seconds,
                        "marketMedian": latest.market_median,
                        "estimatedProfit": latest.estimated_profit,
                        "observedAt": latest.observed_at.isoformat(),
                    },
                )
            )
    return created_count
