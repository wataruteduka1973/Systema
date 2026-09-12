"""HTTPに依存しない市場検索ユースケース。"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from Main.domain.auction_time import format_remaining_time, parse_duration_seconds
from Main.domain.buying_opportunity import evaluate_buying_opportunity
from Main.domain.product_condition import enrich_market_items
from Main.models.searchrun import SearchRun
from Main.services.exceptions import ExternalServiceError
from Main.services.market_statistics import (
    analyze_market_prices,
    enrich_items_with_market_comparison,
)
from Main.services.marketplace import MarketplaceProvider
from Main.services.ownership import RequestOwner
from Main.services.search_criteria import SearchCriteria
from Main.services.search_observability import (
    FAILURE_UNEXPECTED,
    SearchTimer,
    external_failure_code,
)


class SearchRepository(Protocol):
    def save_successful(self, **values: Any) -> Any: ...

    def update_run(
        self,
        run: Any,
        *,
        duration_ms: int,
        succeeded: bool = True,
        failure_code: str = "",
    ) -> None: ...

    def save_result_snapshot(self, run: Any, snapshot: Mapping[str, Any]) -> None: ...

    def save_failed(self, **values: Any) -> Any: ...


WatchRefresher = Callable[[Mapping[str, Any], RequestOwner], Any]


@dataclass(frozen=True)
class TargetSearchResult:
    payload: dict[str, Any]
    runs: tuple[Any, ...]


class TargetSearchFailure(Exception):
    def __init__(
        self,
        cause: Exception,
        *,
        search_type: str,
        active_run: Any | None,
        completed_runs: tuple[Any, ...],
        duration_ms: int,
    ) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.search_type = search_type
        self.active_run = active_run
        self.completed_runs = completed_runs
        self.duration_ms = duration_ms


def record_target_search_failure(
    failure: TargetSearchFailure,
    *,
    criteria: SearchCriteria,
    owner: RequestOwner,
    repository: SearchRepository,
    trigger: str = "manual",
    saved_search: Any | None = None,
) -> tuple[Any, ...]:
    """Web/CLI共通の安全な失敗分類で対象runを失敗として保存する。"""
    code = (
        external_failure_code(failure.cause)
        if isinstance(failure.cause, ExternalServiceError)
        else FAILURE_UNEXPECTED
    )
    runs = list(failure.completed_runs)
    if failure.active_run is None:
        run = repository.save_failed(
            owner=owner,
            keyword=criteria.keyword,
            search_type=failure.search_type,
            criteria_snapshot=criteria.snapshot(),
            trigger=trigger,
            duration_ms=failure.duration_ms,
            failure_code=code,
            saved_search=saved_search,
            record_word=failure.search_type == SearchRun.CLOSED,
        )
        runs.append(run)
    else:
        repository.update_run(
            failure.active_run,
            duration_ms=failure.duration_ms,
            succeeded=False,
            failure_code=code,
        )
    return tuple(runs)


def execute_target_search(
    *,
    criteria: SearchCriteria,
    owner: RequestOwner,
    provider: MarketplaceProvider,
    repository: SearchRepository,
    refresh_watch: WatchRefresher,
    trigger: str = "manual",
    saved_search: Any | None = None,
) -> TargetSearchResult:
    """終了/現在出品を取得・保存し、既存target応答を組み立てる。"""
    keyword = criteria.keyword
    criteria_snapshot = criteria.snapshot()
    completed_runs: list[Any] = []
    active_type = SearchRun.CLOSED
    active_run: Any | None = None
    timer = SearchTimer.start()
    try:
        closed_data = criteria.apply(
            [item.as_closed_item() for item in provider.search_closed(keyword)],
            search_type=SearchRun.CLOSED,
        )
        closed_run = repository.save_successful(
            owner=owner,
            keyword=keyword,
            search_type=SearchRun.CLOSED,
            items=closed_data,
            criteria_snapshot=criteria_snapshot,
            trigger=trigger,
            duration_ms=timer.elapsed_ms(),
            saved_search=saved_search,
            record_word=True,
        )
        active_run = closed_run
        completed_runs.append(closed_run)
        repository.update_run(closed_run, duration_ms=timer.elapsed_ms())
        closed_prices = [
            item["price"]
            for item in closed_data
            if "price" in item and isinstance(item["price"], (int, float))
        ]
        closed_names = [item["name"] for item in closed_data if "name" in item]

        active_type = SearchRun.CURRENT
        active_run = None
        timer = SearchTimer.start()
        current_data = criteria.apply(
            [
                item.as_current_item(format_remaining_time(item.time))
                for item in provider.search_current(keyword)
            ],
            search_type=SearchRun.CURRENT,
        )
        current_run = repository.save_successful(
            owner=owner,
            keyword=keyword,
            search_type=SearchRun.CURRENT,
            items=current_data,
            criteria_snapshot=criteria_snapshot,
            trigger=trigger,
            duration_ms=timer.elapsed_ms(),
            saved_search=saved_search,
            record_word=False,
        )
        active_run = current_run
        completed_runs.append(current_run)

        median_price = float(np.median(closed_prices)) if closed_prices else 0
        current_items = []
        for item in current_data:
            remaining_time = item.get("remainingTime")
            current_items.append(
                {
                    "price": item.get("currentPrice"),
                    "name": item.get("name"),
                    "url": item.get("url"),
                    "remainingTime": remaining_time,
                    "remainingSeconds": parse_duration_seconds(remaining_time),
                    "bidding": item.get("bidding", 0),
                }
            )
        enriched_items = enrich_market_items(current_items)
        enriched_items = enrich_items_with_market_comparison(enriched_items, median_price)
        for item in enriched_items:
            item["marketMedian"] = median_price
            item["buyDecision"] = evaluate_buying_opportunity(
                item["price"], item["marketMedian"], item["condition"], item["remainingSeconds"]
            )
            refresh_watch(item, owner)

        ranked_items = sorted(
            enriched_items,
            key=lambda item: (-item["buyDecision"]["score"], item["remainingSeconds"]),
        )[:30]
        response_items = [
            {
                "price": item["price"],
                "name": item["name"],
                "url": item["url"],
                "remainingTime": item["remainingTime"],
                "remainingSeconds": (
                    item["remainingSeconds"] if math.isfinite(item["remainingSeconds"]) else None
                ),
                "bidding": item["bidding"],
                "marketMedian": median_price,
                "condition": item["condition"],
                "conditionLabel": item["conditionLabel"],
                "attributes": item["attributes"],
                "attributeLabels": item["attributeLabels"],
                "buyDecision": item["buyDecision"],
                "marketComparison": item["marketComparison"],
            }
            for item in ranked_items
        ]
        payload = {
            "closed_prices": closed_prices,
            "closed_names": closed_names,
            "medianPrice": median_price,
            "marketStatistics": analyze_market_prices(
                [{"price": price} for price in closed_prices]
            ),
            "recommend_items": response_items,
        }
        repository.save_result_snapshot(current_run, payload)
        repository.update_run(current_run, duration_ms=timer.elapsed_ms())
        return TargetSearchResult(payload=payload, runs=tuple(completed_runs))
    except Exception as error:
        raise TargetSearchFailure(
            error,
            search_type=active_type,
            active_run=active_run,
            completed_runs=tuple(completed_runs),
            duration_ms=timer.elapsed_ms(),
        ) from error
