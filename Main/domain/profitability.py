"""出品前の見込み利益を外部I/Oなしで計算する。"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any


def calculate_profitability(
    *,
    sale_price: int,
    acquisition_cost: int,
    shipping_cost: int = 0,
    packaging_cost: int = 0,
    other_cost: int = 0,
    fee_rate: Decimal = Decimal("0.10"),
) -> dict[str, int | float | None]:
    values = (sale_price, acquisition_cost, shipping_cost, packaging_cost, other_cost)
    if any(value < 0 for value in values):
        raise ValueError("金額は0以上で指定してください")
    if fee_rate < 0 or fee_rate > 1:
        raise ValueError("手数料率は0から1で指定してください")

    fee = int((Decimal(sale_price) * fee_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    fixed_cost = acquisition_cost + shipping_cost + packaging_cost + other_cost
    total_cost = fixed_cost + fee
    estimated_profit = sale_price - total_cost
    margin = round(estimated_profit / sale_price * 100, 1) if sale_price else None
    break_even = None
    if fee_rate < 1:
        break_even = int(
            (Decimal(fixed_cost) / (Decimal("1") - fee_rate)).quantize(
                Decimal("1"), rounding=ROUND_CEILING
            )
        )
    return {
        "salePrice": sale_price,
        "feeEstimate": fee,
        "totalCost": total_cost,
        "estimatedProfit": estimated_profit,
        "profitMarginPercent": margin,
        "breakEvenPrice": break_even,
    }


def calculate_confirmed_profit(
    *,
    sale_price: int,
    acquisition_cost: int,
    purchase_shipping_cost: int,
    actual_fee: int,
    actual_shipping_cost: int,
    actual_packaging_cost: int,
    actual_other_cost: int,
) -> int:
    """Calculate realized profit from validated, non-negative yen amounts."""
    values = (
        sale_price,
        acquisition_cost,
        purchase_shipping_cost,
        actual_fee,
        actual_shipping_cost,
        actual_packaging_cost,
        actual_other_cost,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise ValueError("amounts must be non-negative integers")
    return sale_price - sum(values[1:])


def decimal_rate(value: Any) -> Decimal:
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("手数料率が正しくありません") from error
    if not rate.is_finite() or rate < 0 or rate > 1:
        raise ValueError("手数料率は0から1で指定してください")
    return rate
