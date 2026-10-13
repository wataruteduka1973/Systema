"""The owner's latest saved closed-auction market for a keyword, used to judge current listings."""

from __future__ import annotations

from typing import Any

from Main.models.searchrun import SearchRun
from Main.services.market_statistics import (
    analyze_market_prices,
    enrich_items_with_market_comparison,
)
from Main.services.ownership import RequestOwner, owner_query


def saved_closed_market(owner: RequestOwner, keyword: str) -> dict[str, Any] | None:
    """Summarize the newest successful saved closed run, or None when there is no usable one.

    Reads stored rows only; it never contacts Yahoo.
    """
    run = (
        SearchRun.objects.filter(
            owner_query(owner), keyword=keyword, search_type=SearchRun.CLOSED, succeeded=True
        )
        .exclude(item_count=0)
        .first()
    )
    if run is None:
        return None
    statistics = analyze_market_prices(
        {"price": price} for price in run.items.values_list("EndPrice", flat=True)
    )
    if not statistics["median"]:
        return None
    return {
        "median": statistics["median"],
        "q1": statistics["q1"],
        "q3": statistics["q3"],
        "count": statistics["count"],
        "searchedAt": run.created_at.isoformat(),
    }


def compare_with_closed_market(
    items: list[dict[str, Any]], closed_market: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Add `closedMarketComparison` (same rule as `marketComparison`) against the saved closed median."""
    if closed_market is None:
        return [{**item, "closedMarketComparison": None} for item in items]
    compared = enrich_items_with_market_comparison(items, closed_market["median"])
    return [
        {**item, "closedMarketComparison": result["marketComparison"]}
        for item, result in zip(items, compared, strict=True)
    ]
