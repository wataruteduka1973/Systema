"""ウォッチ価格履歴から購入判断用の要約を算出する。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol


class SnapshotValue(Protocol):
    price: int
    bidding: int
    observed_at: Any


def analyze_watch_history(snapshots: Sequence[SnapshotValue], market_median: int) -> dict[str, Any]:
    if not snapshots:
        return {
            "observationCount": 0,
            "hasEnoughData": False,
            "trend": "insufficient",
            "trendLabel": "分析材料不足",
        }

    first = snapshots[0]
    current = snapshots[-1]
    prices = [snapshot.price for snapshot in snapshots]
    minimum_price = min(prices)
    maximum_price = max(prices)
    minimum_snapshot = next(snapshot for snapshot in snapshots if snapshot.price == minimum_price)
    price_change = current.price - first.price
    price_change_rate = round(price_change / first.price * 100, 1) if first.price else None
    bid_change = current.bidding - first.bidding
    market_difference = current.price - market_median if market_median else None
    discount_rate = (
        round((market_median - current.price) / market_median * 100, 1) if market_median else None
    )
    if len(snapshots) < 2:
        trend, trend_label = "insufficient", "分析材料不足"
    elif price_change < 0:
        trend, trend_label = "down", "値下がり"
    elif price_change > 0:
        trend, trend_label = "up", "値上がり"
    else:
        trend, trend_label = "flat", "横ばい"

    return {
        "observationCount": len(snapshots),
        "hasEnoughData": len(snapshots) >= 2,
        "trend": trend,
        "trendLabel": trend_label,
        "firstPrice": first.price,
        "currentPrice": current.price,
        "minimumPrice": minimum_price,
        "maximumPrice": maximum_price,
        "minimumObservedAt": minimum_snapshot.observed_at.isoformat(),
        "priceChange": price_change,
        "priceChangeRate": price_change_rate,
        "bidChange": bid_change,
        "marketDifference": market_difference,
        "marketDiscountRate": discount_rate,
    }
