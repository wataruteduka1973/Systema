"""検索経路に依存しない検索条件の検証、正規化、適用。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from Main.domain.auction_time import parse_duration_seconds
from Main.domain.product_condition import CONDITION_LABELS, classify_product_condition
from Main.services.exceptions import SearchInputError
from Main.services.external_search import normalize_search_keyword

SEARCH_TYPES = {"closed", "current", "target", "prediction"}
SORT_ORDERS = {
    "default",
    "price-asc",
    "price-desc",
    "startPrice-asc",
    "startPrice-desc",
    "bidding-asc",
    "bidding-desc",
}


class QueryValues(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...

    def getlist(self, key: str) -> list[str]: ...


@dataclass(frozen=True)
class SearchCriteria:
    keyword: str
    search_type: str
    condition: str | None = None
    minimum_price: int = 0
    maximum_price: int | None = None
    excluded_keywords: tuple[str, ...] = ()
    ending_within_minutes: int | None = None
    sort_order: str = "default"

    @classmethod
    def from_query(cls, query: QueryValues, search_type: str) -> SearchCriteria:
        if search_type not in SEARCH_TYPES:
            raise SearchInputError("検索種別が正しくありません")

        condition = str(query.get("condition", "") or "").strip().lower() or None
        if condition is not None and condition not in CONDITION_LABELS:
            raise SearchInputError("商品状態が正しくありません")

        minimum_price = _non_negative_int(query.get("minimumPrice", 0), "最低価格")
        maximum_price = _optional_non_negative_int(query.get("maximumPrice"), "最高価格")
        if maximum_price is not None and minimum_price > maximum_price:
            raise SearchInputError("最低価格は最高価格以下にしてください")

        ending = _optional_non_negative_int(
            query.get("endingWithinMinutes"), "終了までの時間"
        )
        if ending is not None and search_type not in {"current", "target"}:
            raise SearchInputError("終了までの時間は現在出品検索でのみ指定できます")

        sort_order = str(query.get("sortOrder", "default") or "default").strip()
        if sort_order not in SORT_ORDERS:
            raise SearchInputError("並び順が正しくありません")

        return cls(
            keyword=normalize_search_keyword(query.get("keyword", "")),
            search_type=search_type,
            condition=condition,
            minimum_price=minimum_price,
            maximum_price=maximum_price,
            excluded_keywords=_excluded_keywords(query),
            ending_within_minutes=ending,
            sort_order=sort_order,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "searchType": self.search_type,
            "condition": self.condition,
            "minimumPrice": self.minimum_price,
            "maximumPrice": self.maximum_price,
            "excludedKeywords": list(self.excluded_keywords),
            "endingWithinMinutes": self.ending_within_minutes,
            "sortOrder": self.sort_order,
        }

    def apply(
        self, items: list[Mapping[str, Any]], *, search_type: str | None = None
    ) -> list[dict[str, Any]]:
        effective_search_type = search_type or self.search_type
        normalized: list[dict[str, Any]] = []
        for source in items:
            item = dict(source)
            title = str(item.get("name") or item.get("Name") or "")
            folded_title = title.casefold()
            if any(word.casefold() in folded_title for word in self.excluded_keywords):
                continue

            price = _item_number(item, "currentPrice", "price", "EndPrice")
            if price < self.minimum_price:
                continue
            if self.maximum_price is not None and price > self.maximum_price:
                continue

            item_condition = str(item.get("condition") or "")
            if not item_condition:
                item.update(classify_product_condition(title))
                item_condition = str(item["condition"])
            if self.condition is not None and item_condition != self.condition:
                continue

            if self.ending_within_minutes is not None and effective_search_type in {
                "current",
                "target",
            }:
                remaining_seconds = _remaining_seconds(item)
                if remaining_seconds > self.ending_within_minutes * 60:
                    continue
            normalized.append(item)

        if self.sort_order != "default":
            key, direction = self.sort_order.rsplit("-", 1)
            fields = {
                "price": ("currentPrice", "price", "EndPrice"),
                "startPrice": ("startPrice", "StartPrice"),
                "bidding": ("bidding", "Bidding", "bidCount"),
            }[key]
            normalized.sort(
                key=lambda item: _item_number(item, *fields), reverse=direction == "desc"
            )
        return normalized


def _non_negative_int(value: Any, label: str) -> int:
    try:
        parsed = int(str(value or "0"))
    except (TypeError, ValueError) as error:
        raise SearchInputError(f"{label}は0以上の整数で入力してください") from error
    if parsed < 0:
        raise SearchInputError(f"{label}は0以上の整数で入力してください")
    return parsed


def _optional_non_negative_int(value: Any, label: str) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return _non_negative_int(value, label)


def _excluded_keywords(query: QueryValues) -> tuple[str, ...]:
    raw_values = query.getlist("excludedKeywords")
    if not raw_values:
        raw_values = [str(query.get("excludedKeywords", "") or "")]
    words = [word.strip() for raw in raw_values for word in raw.split(",") if word.strip()]
    unique = tuple(dict.fromkeys(words))
    if len(unique) > 20 or any(len(word) > 50 for word in unique):
        raise SearchInputError("除外キーワードは20件以内、各50文字以内で指定してください")
    return unique


def _item_number(item: Mapping[str, Any], *fields: str) -> int:
    for field in fields:
        value = item.get(field)
        if isinstance(value, bool) or value is None:
            continue
        try:
            return int(float(str(value).replace(",", "")))
        except ValueError:
            continue
    return 0


def _remaining_seconds(item: Mapping[str, Any]) -> float:
    for field in ("remainingSeconds", "remaining_seconds"):
        value = item.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return parse_duration_seconds(item.get("remainingTime"))
