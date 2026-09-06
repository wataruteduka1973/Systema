"""購入前の費用前提と上限。空欄は不明であり、ゼロとは異なる。"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from Main.domain.profitability import calculate_profitability, decimal_rate
from Main.domain.seller_listing import money

COST_KEYS = (
    "feeRate",
    "purchaseShipping",
    "shippingCost",
    "packagingCost",
    "otherCost",
    "targetProfit",
)
INPUT_KEYS = ("salePrice", *COST_KEYS)


def normalize_assumptions(payload: Mapping[str, Any], *, settings: bool = False) -> dict[str, Any]:
    keys = COST_KEYS if settings else INPUT_KEYS
    if set(payload) - set(keys):
        raise ValueError("未対応の費用項目があります")
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None or value == "":
            result[key] = None
        elif key == "feeRate":
            rate = decimal_rate(value)
            if rate != rate.quantize(Decimal("0.00001")):
                raise ValueError("手数料率は小数点以下5桁以内で指定してください")
            result[key] = str(rate)
        else:
            result[key] = money(value)
    return result


def calculate_budget(assumptions: Mapping[str, Any], price: int) -> dict[str, Any]:
    missing = [key for key in INPUT_KEYS if assumptions.get(key) is None]
    if missing:
        return {
            "status": "insufficient",
            "missing": missing,
            "purchaseLimit": None,
            "estimatedProfit": None,
            "feeEstimate": None,
            "targetDifference": None,
        }
    result = calculate_profitability(
        sale_price=assumptions["salePrice"],
        acquisition_cost=price,
        shipping_cost=assumptions["purchaseShipping"] + assumptions["shippingCost"],
        packaging_cost=assumptions["packagingCost"],
        other_cost=assumptions["otherCost"],
        fee_rate=decimal_rate(assumptions["feeRate"]),
    )
    profit = result["estimatedProfit"]
    assert isinstance(profit, int)
    limit = price + profit - assumptions["targetProfit"]
    return {
        **result,
        "purchaseLimit": limit if limit >= 0 else None,
        "status": (
            "no_budget" if limit < 0 else "within_budget" if price <= limit else "over_budget"
        ),
        "missing": [],
        "targetDifference": profit - assumptions["targetProfit"],
    }
