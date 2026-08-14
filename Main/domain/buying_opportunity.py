"""相場価格と商品状態から買い時を判定する。"""

from __future__ import annotations

from typing import Any


def evaluate_buying_opportunity(
    current_price: object,
    market_median: object,
    condition: str = "unknown",
    remaining_seconds: object = None,
) -> dict[str, Any]:
    """価格比率を中心に、説明可能な買い時判定を返す。"""
    price = _positive_number(current_price)
    median_price = _positive_number(market_median)

    if condition == "junk":
        return _decision("caution", "要注意", 0, "ジャンク・故障品として出品されています")
    if price is None or median_price is None:
        return _decision(
            "insufficient", "判定材料不足", 0, "有効な現在価格または相場中央値がありません"
        )

    ratio = price / median_price
    discount_rate = round((1 - ratio) * 100, 1)
    if ratio <= 0.70:
        status, label, base_score = "strong_buy", "かなり買い時", 90
    elif ratio <= 0.85:
        status, label, base_score = "buy", "買い時", 75
    elif ratio <= 1.00:
        status, label, base_score = "consider", "検討候補", 60
    else:
        status, label, base_score = "wait", "様子見", max(10, round(50 / ratio))

    seconds = _positive_number(remaining_seconds)
    ending_soon = seconds is not None and seconds <= 3600
    score = min(100, base_score + (5 if ending_soon and ratio <= 1 else 0))
    comparison = (
        f"相場中央値より{abs(discount_rate):.1f}%安い"
        if discount_rate >= 0
        else f"相場中央値より{abs(discount_rate):.1f}%高い"
    )
    reason = f"{comparison}価格です"
    if ending_soon:
        reason += "。終了まで1時間以内です"

    return _decision(status, label, score, reason, ratio, discount_rate, ending_soon)


def _positive_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return float(value)


def _decision(
    status: str,
    label: str,
    score: int,
    reason: str,
    price_ratio: float | None = None,
    discount_rate: float | None = None,
    ending_soon: bool = False,
) -> dict[str, Any]:
    return {
        "status": status,
        "label": label,
        "score": score,
        "reason": reason,
        "priceRatio": round(price_ratio, 3) if price_ratio is not None else None,
        "discountRate": discount_rate,
        "endingSoon": ending_soon,
    }
