import pytest

from Main.domain.purchase_budget import calculate_budget, normalize_assumptions


def inputs(**changes):
    return {
        "salePrice": 10000,
        "feeRate": "0.10",
        "purchaseShipping": 700,
        "shippingCost": 800,
        "packagingCost": 200,
        "otherCost": 300,
        "targetProfit": 2000,
        **changes,
    }


@pytest.mark.parametrize(
    "price,profit,status",
    [
        (4500, 2500, "within_budget"),
        (5000, 2000, "within_budget"),
        (5500, 1500, "over_budget"),
        (9000, -2000, "over_budget"),
    ],
)
def test_budget_price_boundaries(price, profit, status):
    result = calculate_budget(inputs(), price)
    assert result["purchaseLimit"] == 5000
    assert result["estimatedProfit"] == profit
    assert result["status"] == status


def test_unknown_zero_rounding_and_impossible_budget():
    assert calculate_budget(inputs(shippingCost=None), 5000)["estimatedProfit"] is None
    assert calculate_budget(inputs(shippingCost=0), 5000)["purchaseLimit"] == 5800
    result = calculate_budget(inputs(salePrice=10005), 5000)
    assert result["feeEstimate"] == 1001
    assert result["purchaseLimit"] == 5004
    assert calculate_budget(inputs(targetProfit=10000), 0)["status"] == "no_budget"
    assert (
        calculate_budget(
            inputs(
                feeRate="1",
                purchaseShipping=0,
                shippingCost=0,
                packagingCost=0,
                otherCost=0,
                targetProfit=0,
            ),
            0,
        )["purchaseLimit"]
        == 0
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"salePrice": True},
        {"shippingCost": -1},
        {"salePrice": "1.5"},
        {"feeRate": "NaN"},
        {"feeRate": "0.100001"},
        {"otherCost": 1000000000001},
        {"user": 1},
    ],
)
def test_reject_invalid_assumptions(payload):
    with pytest.raises(ValueError):
        normalize_assumptions(payload)


def test_null_and_zero_remain_distinct():
    assert normalize_assumptions({"shippingCost": "", "otherCost": "0"}) == {
        "shippingCost": None,
        "otherCost": 0,
    }
