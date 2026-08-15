import pytest

from Main.services.market_statistics import (
    analyze_market_prices,
    enrich_items_with_market_comparison,
)


@pytest.mark.unit
def test_analyze_market_prices_returns_variability_metrics():
    result = analyze_market_prices([{"price": price} for price in [1000, 2000, 3000, 4000, 10000]])

    assert result["count"] == 5
    assert result["median"] == 3000
    assert result["minimum"] == 1000
    assert result["maximum"] == 10000
    assert result["priceRange"] == 9000
    assert result["iqr"] == 2000
    assert result["outlierCount"] == 1
    assert sum(item["count"] for item in result["histogram"]) == 4
    assert max(item["upper"] for item in result["histogram"]) < 10000


@pytest.mark.unit
def test_analyze_market_prices_prefers_current_price_and_ignores_invalid_values():
    result = analyze_market_prices(
        [
            {"price": 100, "currentPrice": 2000},
            {"price": 1000},
            {"price": 0},
            {"price": "invalid"},
        ]
    )

    assert result["count"] == 2
    assert result["median"] == 1500


@pytest.mark.unit
def test_enrich_items_with_market_comparison_labels_price_position():
    items = enrich_items_with_market_comparison(
        [{"price": 7000}, {"price": 10000}, {"price": 13000}], 10000
    )

    assert [item["marketComparison"]["position"] for item in items] == [
        "below",
        "near",
        "above",
    ]
    assert items[0]["marketComparison"]["differenceRate"] == -30.0


@pytest.mark.unit
def test_empty_market_statistics_has_stable_schema():
    result = analyze_market_prices([])
    assert result["count"] == 0
    assert result["histogram"] == []
