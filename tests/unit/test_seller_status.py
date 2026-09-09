from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from Main.domain.seller_status import assess_listing, listing_price

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def listing(**changes):
    values = dict(
        status="active",
        missing_cost_fields=[],
        last_checked_at=NOW,
        predicted_sale_price=10000,
        current_price=8000,
        market_median=0,
        acquisition_cost=5000,
        purchase_shipping_cost=0,
        shipping_cost_estimate=500,
        packaging_cost_estimate=100,
        other_cost_estimate=100,
        target_profit=1000,
        ends_at=NOW + timedelta(days=3),
        bidding=2,
        fee_rate=Decimal("0.1"),
    )
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"missing_cost_fields": ["shippingCostEstimate"]}, "cost_incomplete"),
        ({"predicted_sale_price": None, "last_checked_at": None}, "price_missing"),
        ({"last_checked_at": None}, "needs_refresh"),
        ({"acquisition_cost": 9500}, "loss_risk"),
        ({"target_profit": 4000}, "target_unmet"),
        ({"ends_at": NOW + timedelta(hours=24), "bidding": 0}, "ending_without_bids"),
        ({"ends_at": NOW + timedelta(hours=24)}, "ending_soon"),
        ({"ends_at": NOW}, "status_check"),
        ({"status": "ended"}, "status_check"),
        ({"last_checked_at": NOW - timedelta(hours=24)}, "stale"),
        ({"status": "sold", "acquisition_cost": 99999}, "sale_result_missing"),
        ({}, "ok"),
    ],
)
def test_status_boundaries(changes, expected):
    assert assess_listing(listing(**changes), now=NOW)["status"] == expected


def test_zero_is_a_price_and_matches_profit_display():
    item = listing(predicted_sale_price=0)
    assert listing_price(item) == (0, "manual")
    assert assess_listing(item, now=NOW)["status"] == "loss_risk"
    assert listing_price(listing(predicted_sale_price=None, current_price=0)) == (0, "currentPrice")


def test_stale_observation_does_not_claim_urgency_or_stall():
    item = listing(
        last_checked_at=NOW - timedelta(hours=24), ends_at=NOW + timedelta(hours=1), bidding=0
    )
    assert assess_listing(item, now=NOW, baseline_bids=0)["status"] == "stale"
    assert assess_listing(listing(), now=NOW, baseline_bids=2)["status"] == "bid_stalled"
    assert assess_listing(listing(), now=NOW, baseline_bids=3)["status"] == "ok"
    assert assess_listing(listing(), now=NOW, baseline_bids=None)["status"] == "ok"


def test_urgency_precedes_loss_and_insufficient_costs():
    item = listing(ends_at=NOW + timedelta(hours=1), bidding=0, acquisition_cost=20000)
    assert assess_listing(item, now=NOW)["status"] == "ending_without_bids"
    item.ends_at = NOW + timedelta(days=3)
    item.missing_cost_fields = ["shippingCostEstimate"]
    assert assess_listing(item, now=NOW)["status"] == "cost_incomplete"


def test_completed_sale_has_no_missing_result_action():
    result = assess_listing(listing(status="sold"), now=NOW, sale_record_exists=True)
    assert result["status"] == "sold"
    assert result["nextAction"] == "販売結果を確認"
