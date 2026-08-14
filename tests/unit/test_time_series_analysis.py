from datetime import datetime, timedelta

from Main.services.time_series_analysis import (
    analyze_stored_market,
    parse_auction_date,
    predict_market_prices,
)


def test_parse_auction_date_wraps_future_month_to_previous_year():
    reference = datetime(2026, 1, 10, 12, 0)

    parsed = parse_auction_date("12/31 23:59", reference)

    assert parsed == datetime(2025, 12, 31, 23, 59)


def test_analyze_stored_market_builds_summary_series_and_conditions():
    items = [
        {"Name": "新品 カメラ", "EndPrice": 10000, "SearchDay": "2026-08-10T10:00:00"},
        {"Name": "中古 動作品 カメラ", "EndPrice": 8000, "SearchDay": "2026-08-10T12:00:00"},
        {"Name": "ジャンク カメラ", "EndPrice": 2000, "SearchDay": "2026-08-11T10:00:00"},
    ]

    analysis = analyze_stored_market(items, datetime(2026, 8, 15))

    assert analysis["summary"]["count"] == 3
    assert len(analysis["timeSeries"]) == 2
    conditions = {row["condition"]: row for row in analysis["conditionMarket"]["conditions"]}
    assert conditions["new"]["count"] == 1
    assert conditions["junk"]["medianPrice"] == 2000


def test_prediction_keeps_dates_aligned_and_marks_iqr_outlier():
    reference = datetime(2026, 8, 15, 12, 0)
    prices = [1000, 1050, 1100, 1150, 1200, 1250, 1300, 10000]
    items = [
        {
            "time": (reference - timedelta(days=7 - index)).isoformat(),
            "price": price,
        }
        for index, price in enumerate(prices)
    ]

    result = predict_market_prices(items, reference)

    assert result is not None
    assert result["quality"]["outlierCount"] == 1
    assert result["quality"]["usedCount"] == 7
    assert len(result["price_trends"]) == len(items)
    assert len(result["daily_trends"]) == 7
    outlier = next(item for item in result["price_trends"] if item["isOutlier"])
    assert outlier["price"] == 10000
    assert result["prediction_interval"][0] <= result["predicted_price"]
    assert result["prediction_interval"][1] >= result["predicted_price"]
