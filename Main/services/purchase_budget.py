"""所有者限定の費用設定と追記型の購入判断。外部取得を行わない。"""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from typing import Any

from django.db import transaction
from django.utils import timezone

from Main.domain.purchase_budget import (
    COST_KEYS,
    INPUT_KEYS,
    calculate_budget,
    normalize_assumptions,
)
from Main.models.purchasebudget import CostSettings, PurchaseDecision
from Main.models.searchrun import SearchRun
from Main.models.watchitem import WatchItem


def cost_settings(user: Any) -> dict[str, Any]:
    record = CostSettings.objects.filter(user=user).first()
    return {key: record.assumptions.get(key) if record else None for key in COST_KEYS}


def save_cost_settings(user: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    # PUT replaces the complete reusable template, never modifies prior decisions.
    values = normalize_assumptions(payload, settings=True)
    CostSettings.objects.update_or_create(user=user, defaults={"assumptions": values})
    return cost_settings(user)


def evidence_runs(user: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": run.pk,
            "keyword": run.keyword,
            "observedAt": run.created_at.isoformat(),
            "count": run.item_count,
        }
        for run in SearchRun.objects.filter(user=user, succeeded=True, search_type="closed")[:50]
    ]


def build_evidence(user: Any, run_id: Any, note: Any) -> tuple[dict[str, Any], int | None]:
    if not isinstance(note, str) or len(note) > 2000:
        raise ValueError("売価の根拠メモは2000文字以内で指定してください")
    if run_id is None:
        return {
            "source": "manual",
            "note": note.strip(),
            "count": None,
            "observedAt": None,
            "salePeriod": None,
            "items": [],
        }, None
    if (
        isinstance(run_id, bool)
        or not str(run_id).isascii()
        or not str(run_id).isdigit()
        or len(str(run_id)) > 18
    ):
        raise ValueError("検索履歴IDが正しくありません")
    run = SearchRun.objects.get(user=user, pk=run_id, succeeded=True, search_type="closed")
    rows = list(run.items.order_by("pk").values("Name", "URL", "EndPrice", "SearchDay")[:5001])
    if not rows or len(rows) > 5000:
        raise ValueError("根拠には1〜5000件の落札検索履歴を選択してください")
    if any(not 0 <= row["EndPrice"] <= 1_000_000_000_000 for row in rows):
        raise ValueError("根拠データの価格が不正です")
    price = int(
        Decimal(str(median(row["EndPrice"] for row in rows))).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    return {
        "source": "closed_search",
        "runId": run.pk,
        "keyword": run.keyword,
        "note": note.strip(),
        "count": len(rows),
        "observedAt": run.created_at.isoformat(),
        "salePeriod": None,
        "criteria": run.criteria_snapshot,
        "items": rows,
        "median": price,
    }, price


def latest_decision(watch: WatchItem) -> dict[str, Any]:
    record = watch.purchase_decisions.first()
    return record.snapshot if record else {}


@transaction.atomic
def save_decision(user: Any, watch_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    watch = WatchItem.objects.select_for_update().get(user=user, pk=watch_id)
    if watch.lifecycle_status == "purchased" or hasattr(watch, "inventory_item"):
        raise ValueError("在庫化済みの購入判断は変更できません")
    if set(payload) - {"assumptions", "evidenceRunId", "evidenceNote", "useDefaults"}:
        raise ValueError("未対応の入力項目があります")
    raw = payload.get("assumptions", {})
    if not isinstance(raw, dict) or not isinstance(payload.get("useDefaults", False), bool):
        raise ValueError("費用設定が正しくありません")
    previous = latest_decision(watch)
    # First save uses defaults; subsequent partial saves preserve the product's assumptions.
    base = dict(previous["assumptions"]) if previous else cost_settings(user)
    if payload.get("useDefaults"):
        base.update(cost_settings(user))
    values = {key: base.get(key) for key in INPUT_KEYS}
    values.update(normalize_assumptions(raw))
    if previous and not ({"evidenceRunId", "evidenceNote"} & set(payload)):
        evidence = previous["evidence"]
        suggested = evidence.get("median") if evidence["source"] == "closed_search" else None
    else:
        evidence, suggested = build_evidence(
            user, payload.get("evidenceRunId"), payload.get("evidenceNote", "")
        )
    if suggested is not None:
        values["salePrice"] = suggested
    if suggested is None and values["salePrice"] is not None and not evidence["note"]:
        raise ValueError("手入力の想定売価には根拠メモを入力してください")
    snapshot = {
        "version": 1,
        "assumptions": values,
        "evidence": evidence,
        "candidatePrice": watch.current_price,
        "candidateObservedAt": watch.last_checked_at.isoformat(),
        "candidateUrl": watch.url,
        "savedAt": timezone.now().isoformat(),
        "result": calculate_budget(values, watch.current_price),
    }
    if previous and all(
        previous.get(key) == value for key, value in snapshot.items() if key != "savedAt"
    ):
        return previous
    PurchaseDecision.objects.create(watch_item=watch, snapshot=snapshot)
    return snapshot
