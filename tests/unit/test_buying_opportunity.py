import pytest

from Main.domain.buying_opportunity import evaluate_buying_opportunity


@pytest.mark.unit
@pytest.mark.parametrize(
    ("price", "median", "expected"),
    [
        (6000, 10000, "strong_buy"),
        (8000, 10000, "buy"),
        (9500, 10000, "consider"),
        (12000, 10000, "wait"),
    ],
)
def test_evaluate_buying_opportunity_price_thresholds(price, median, expected):
    result = evaluate_buying_opportunity(price, median)
    assert result["status"] == expected


@pytest.mark.unit
def test_junk_is_always_caution():
    result = evaluate_buying_opportunity(100, 10000, condition="junk")
    assert result["status"] == "caution"
    assert result["score"] == 0


@pytest.mark.unit
def test_ending_soon_adds_score_and_reason():
    result = evaluate_buying_opportunity(8000, 10000, remaining_seconds=1800)
    assert result["score"] == 80
    assert result["endingSoon"] is True
    assert "1時間以内" in result["reason"]


@pytest.mark.unit
def test_missing_market_data_is_insufficient():
    assert evaluate_buying_opportunity(1000, 0)["status"] == "insufficient"
