from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction

from Main.models.savedsearch import SavedSearch
from Main.services.exceptions import SearchInputError
from Main.services.search_criteria import SearchCriteria


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


def save_saved_search(user, payload: Mapping[str, Any], instance=None) -> SavedSearch:
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
        "lastRunAt": saved_search.last_run_at.isoformat() if saved_search.last_run_at else None,
        "createdAt": saved_search.created_at.isoformat() if saved_search.created_at else None,
        "updatedAt": saved_search.updated_at.isoformat() if saved_search.updated_at else None,
    }
