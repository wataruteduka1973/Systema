from datetime import datetime, timedelta

from Main.services.time_series_analysis import (
    analyze_snapshot_history,
    analyze_stored_market,
    backtest_market_prediction,
    parse_auction_date,
    predict_market_prices,
)


def test_snapshot_history_keeps_each_update_as_a_separate_point():
    history = [
        {"SearchDay": "2026-08-14 10:00:00", "EndPrice": 1000},
        {"SearchDay": "2026-08-14 10:00:00", "EndPrice": 2000},
        {"SearchDay": "2026-08-15 10:00:00", "EndPrice": 3000},
        {"SearchDay": "2026-08-15 10:00:00", "EndPrice": 5000},
    ]

    points = analyze_snapshot_history(history)

    assert len(points) == 2
    assert points[0]["median"] == 1500
    assert points[1]["median"] == 4000


def test_snapshot_history_excludes_extreme_price_from_chart_range():
    history = [
        {"SearchDay": "2026-08-15 10:00:00", "EndPrice": price}
        for price in [1000, 1200, 1400, 1600, 1_000_000_000]
    ]

    point = analyze_snapshot_history(history)[0]

    assert point["count"] == 4
    assert point["median"] == 1300
    assert point["q3"] < 1_000_000_000


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


def test_backtest_uses_only_data_available_at_each_cutoff():
    reference = datetime(2026, 8, 15, 12, 0)
    items = [{"time": (reference - timedelta(days=120 - day)).isoformat(), "price": 1000 + day * 10} for day in range(121)]
    result = backtest_market_prediction(items, reference)
    assert result["available"] is True
    assert result["windowCount"] >= 3
    assert result["mae"] <= 1
    assert result["directionAccuracy"] == 100.0
    assert all(point["targetDate"] > point["cutoffDate"] for point in result["points"])


def test_backtest_reports_when_history_is_too_short():
    reference = datetime(2026, 8, 15, 12, 0)
    items = [{"time": (reference - timedelta(days=day)).isoformat(), "price": 1000} for day in range(10)]
    result = backtest_market_prediction(items, reference)
    assert result["available"] is False
    assert result["windowCount"] == 0
