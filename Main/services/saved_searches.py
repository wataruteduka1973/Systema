from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from Main.domain.refresh_schedule import REFRESH_INTERVAL_HOURS, is_refresh_due, next_refresh_at
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.services.exceptions import SearchInputError
from Main.services.search_criteria import SearchCriteria
from Main.services.search_observability import (
    FAILURE_EXTERNAL_SERVICE,
    FAILURE_HTML_PARSE,
    FAILURE_INSUFFICIENT_DATA,
    FAILURE_NO_DATA,
    FAILURE_UNEXPECTED,
)

# Fixed wording only; stored failure codes never carry upstream content.
FAILURE_REASONS = {
    FAILURE_EXTERNAL_SERVICE: "ヤフオクに接続できませんでした",
    FAILURE_HTML_PARSE: "ヤフオクのページを読み取れませんでした",
    FAILURE_NO_DATA: "検索結果が0件でした",
    FAILURE_INSUFFICIENT_DATA: "分析に必要なデータが足りませんでした",
    FAILURE_UNEXPECTED: "予期しないエラーが発生しました",
}


@dataclass(frozen=True)
class PayloadValues:
    values: Mapping[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def getlist(self, key: str) -> list[str]:
        value = self.values.get(key, [])
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)] if value not in (None, "") else []


def criteria_from_saved_search(saved_search: SavedSearch) -> SearchCriteria:
    return SearchCriteria.from_query(
        PayloadValues(
            {
                "keyword": saved_search.keyword,
                "condition": saved_search.condition,
                "minimumPrice": saved_search.minimum_price,
                "maximumPrice": saved_search.maximum_price,
                "excludedKeywords": saved_search.excluded_keywords,
                "endingWithinMinutes": saved_search.ending_within_minutes,
                "sortOrder": saved_search.sort_order,
            }
        ),
        "target",
    )


def save_saved_search(
    user: Any, payload: Mapping[str, Any], instance: SavedSearch | None = None
) -> SavedSearch:
    if not isinstance(payload, Mapping):
        raise SearchInputError("リクエスト形式が正しくありません")

    current = serialize_saved_search(instance) if instance is not None else {}
    merged = {**current, **payload}
    name = str(merged.get("name", "")).strip()
    if not name or len(name) > 100:
        raise SearchInputError("保存条件名は1文字以上100文字以内で入力してください")

    criteria = SearchCriteria.from_query(PayloadValues(merged), "target")
    active = merged.get("isActive", True)
    if not isinstance(active, bool):
        raise SearchInputError("有効状態が正しくありません")

    saved_search = instance or SavedSearch(user=user)
    saved_search.name = name
    saved_search.keyword = criteria.keyword
    saved_search.condition = criteria.condition or ""
    saved_search.minimum_price = criteria.minimum_price
    saved_search.maximum_price = criteria.maximum_price
    saved_search.excluded_keywords = list(criteria.excluded_keywords)
    saved_search.ending_within_minutes = criteria.ending_within_minutes
    saved_search.sort_order = criteria.sort_order
    saved_search.is_active = active
    interval = merged.get("refreshIntervalHours", saved_search.refresh_interval_hours)
    if isinstance(interval, bool) or interval not in REFRESH_INTERVAL_HOURS:
        raise SearchInputError("取得頻度は1、6、24時間のいずれかで指定してください")
    saved_search.refresh_interval_hours = interval
    try:
        with transaction.atomic():
            saved_search.save()
    except IntegrityError as error:
        raise SearchInputError("同じ名前の保存条件がすでにあります") from error
    return saved_search


def serialize_saved_search(saved_search: SavedSearch | None) -> dict[str, Any]:
    if saved_search is None:
        return {}
    return {
        "id": saved_search.pk,
        "name": saved_search.name,
        "keyword": saved_search.keyword,
        "condition": saved_search.condition or None,
        "minimumPrice": saved_search.minimum_price,
        "maximumPrice": saved_search.maximum_price,
        "excludedKeywords": saved_search.excluded_keywords,
        "endingWithinMinutes": saved_search.ending_within_minutes,
        "sortOrder": saved_search.sort_order,
        "isActive": saved_search.is_active,
        "refreshIntervalHours": saved_search.refresh_interval_hours,
        "refresh": refresh_status(saved_search),
        "lastRunAt": saved_search.last_run_at.isoformat() if saved_search.last_run_at else None,
        "createdAt": saved_search.created_at.isoformat() if saved_search.created_at else None,
        "updatedAt": saved_search.updated_at.isoformat() if saved_search.updated_at else None,
    }


def last_attempt_failed(saved_search: SavedSearch) -> bool:
    """Whether the newest recorded run of this search failed (it is then retried sooner)."""
    latest = (
        SearchRun.objects.filter(saved_search=saved_search, user_id=saved_search.user_id)
        .only("succeeded")
        .first()
    )
    return latest is not None and not latest.succeeded


def is_saved_search_due(saved_search: SavedSearch, now: Any = None) -> bool:
    return is_refresh_due(
        now or timezone.now(),
        saved_search.last_run_at,
        saved_search.refresh_interval_hours,
        last_attempt_failed=last_attempt_failed(saved_search),
    )


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def refresh_status(saved_search: SavedSearch) -> dict[str, Any]:
    """Last success, last failure and the next planned refresh, read from recorded runs."""
    if saved_search.pk is None:
        return {}
    runs = SearchRun.objects.filter(saved_search=saved_search, user_id=saved_search.user_id)
    success = runs.filter(succeeded=True, search_type=SearchRun.CURRENT).first()
    failure = runs.filter(succeeded=False).first()
    failed = last_attempt_failed(saved_search)
    planned = next_refresh_at(
        saved_search.last_run_at, saved_search.refresh_interval_hours, last_attempt_failed=failed
    )
    return {
        "lastAttemptAt": _iso(saved_search.last_run_at),
        "lastAttemptFailed": failed,
        "lastSuccessAt": _iso(success.created_at if success else None),
        "lastSuccessItemCount": success.item_count if success else None,
        "lastFailureAt": _iso(failure.created_at if failure else None),
        "lastFailureReason": (
            FAILURE_REASONS.get(failure.failure_code, "取得に失敗しました") if failure else None
        ),
        # None while paused, or when the search has never run and the next wake-up takes it.
        "nextRefreshAt": _iso(planned) if saved_search.is_active else None,
    }
