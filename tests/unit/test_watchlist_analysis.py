from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from Main.services.watchlist_analysis import analyze_watch_history


@pytest.mark.unit
def test_watch_history_analysis_summarizes_price_bid_and_market_changes():
    first_at = datetime(2026, 9, 1, tzinfo=UTC)
    snapshots = [
        SimpleNamespace(price=10000, bidding=1, observed_at=first_at),
        SimpleNamespace(price=8000, bidding=4, observed_at=first_at + timedelta(hours=2)),
        SimpleNamespace(price=9000, bidding=6, observed_at=first_at + timedelta(hours=4)),
    ]

    result = analyze_watch_history(snapshots, market_median=12000)

    assert result["observationCount"] == 3
    assert result["trend"] == "down"
    assert result["minimumPrice"] == 8000
    assert result["priceChange"] == -1000
    assert result["priceChangeRate"] == -10.0
    assert result["bidChange"] == 5
    assert result["marketDiscountRate"] == 25.0
    assert result["minimumObservedAt"] == (first_at + timedelta(hours=2)).isoformat()


@pytest.mark.unit
def test_watch_history_analysis_marks_single_observation_as_insufficient():
    snapshot = SimpleNamespace(
        price=7000,
        bidding=0,
        observed_at=datetime(2026, 9, 1, tzinfo=UTC),
    )

    result = analyze_watch_history([snapshot], market_median=0)

    assert result["hasEnoughData"] is False
    assert result["trend"] == "insufficient"
    assert result["marketDifference"] is None
    assert result["marketDiscountRate"] is None


@pytest.mark.unit
def test_watch_history_analysis_handles_empty_history():
    assert analyze_watch_history([], market_median=10000) == {
        "observationCount": 0,
        "hasEnoughData": False,
        "trend": "insufficient",
        "trendLabel": "分析材料不足",
    }
