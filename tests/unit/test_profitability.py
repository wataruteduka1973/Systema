from decimal import Decimal

import pytest

from Main.domain.profitability import calculate_profitability, decimal_rate

pytestmark = pytest.mark.unit


def test_profitability_calculates_fee_profit_margin_and_break_even():
    result = calculate_profitability(
        sale_price=22000,
        acquisition_cost=12000,
        shipping_cost=1000,
        packaging_cost=200,
        other_cost=0,
        fee_rate=Decimal("0.10"),
    )

    assert result == {
        "salePrice": 22000,
        "feeEstimate": 2200,
        "totalCost": 15400,
        "estimatedProfit": 6600,
        "profitMarginPercent": 30.0,
        "breakEvenPrice": 14667,
    }


def test_profitability_allows_negative_estimated_profit():
    result = calculate_profitability(
        sale_price=5000,
        acquisition_cost=6000,
        fee_rate=Decimal("0.10"),
    )

    assert result["estimatedProfit"] == -1500
    assert result["profitMarginPercent"] == -30.0


@pytest.mark.parametrize("value", ["-0.1", "1.1", "NaN", "invalid"])
def test_decimal_rate_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        decimal_rate(value)


def test_profitability_handles_full_fee_rate_without_division_by_zero():
    result = calculate_profitability(
        sale_price=1000,
        acquisition_cost=100,
        fee_rate=Decimal("1"),
    )

    assert result["estimatedProfit"] == -100
    assert result["breakEvenPrice"] is None
