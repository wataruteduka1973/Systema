"""pandasを使った市場価格の統計集計。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd


def analyze_market_prices(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """商品群から価格変動を表す基本統計とヒストグラムを生成する。"""
    prices = pd.Series(
        [_item_price(item) for item in items],
        dtype="float64",
    )
    prices = prices[(prices.notna()) & (prices > 0)]
    if prices.empty:
        return _empty_statistics()

    q1 = float(prices.quantile(0.25))
    median = float(prices.median())
    q3 = float(prices.quantile(0.75))
    iqr = q3 - q1
    lower_fence = max(0.0, q1 - 1.5 * iqr)
    upper_fence = q3 + 1.5 * iqr
    mean = float(prices.mean())
    standard_deviation = float(prices.std(ddof=0))
    coefficient = standard_deviation / mean * 100 if mean else 0.0

    return {
        "count": int(prices.count()),
        "minimum": _rounded(prices.min()),
        "maximum": _rounded(prices.max()),
        "mean": _rounded(mean),
        "median": _rounded(median),
        "q1": _rounded(q1),
        "q3": _rounded(q3),
        "iqr": _rounded(iqr),
        "priceRange": _rounded(prices.max() - prices.min()),
        "standardDeviation": _rounded(standard_deviation),
        "coefficientOfVariation": round(coefficient, 1),
        "lowerFence": _rounded(lower_fence),
        "upperFence": _rounded(upper_fence),
        "outlierCount": int(((prices < lower_fence) | (prices > upper_fence)).sum()),
        "histogram": _histogram(prices),
    }


def enrich_items_with_market_comparison(
    items: Iterable[Mapping[str, Any]], market_median: object
) -> list[dict[str, Any]]:
    """各商品へ中央値との差額・差率・価格位置を付加する。"""
    median = _positive_float(market_median)
    enriched = []
    for item in items:
        result = dict(item)
        price = _item_price(item)
        if price is None or median is None:
            result["marketComparison"] = _empty_comparison()
        else:
            difference = price - median
            difference_rate = difference / median * 100
            if difference_rate <= -15:
                position = "below"
                label = "相場より安い"
            elif difference_rate >= 15:
                position = "above"
                label = "相場より高い"
            else:
                position = "near"
                label = "相場圏内"
            result["marketComparison"] = {
                "difference": _rounded(difference),
                "differenceRate": round(difference_rate, 1),
                "position": position,
                "label": label,
            }
        enriched.append(result)
    return enriched


def _item_price(item: Mapping[str, Any]) -> float | None:
    current_price = _positive_float(item.get("currentPrice"))
    return current_price if current_price is not None else _positive_float(item.get("price"))


def _positive_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, str)):
        try:
            number = float(value)
            return number if number > 0 else None
        except ValueError:
            return None
    return None


def _rounded(value: Any) -> int:
    return int(round(float(value)))


def _histogram(prices: pd.Series, bin_count: int = 8) -> list[dict[str, int]]:
    if prices.nunique() == 1:
        value = _rounded(prices.iloc[0])
        return [{"lower": value, "upper": value, "count": int(prices.count())}]

    categories = pd.cut(prices, bins=min(bin_count, int(prices.nunique())), duplicates="drop")
    counts = categories.value_counts(sort=False)
    return [
        {
            "lower": _rounded(interval.left),
            "upper": _rounded(interval.right),
            "count": int(count),
        }
        for interval, count in counts.items()
    ]


def _empty_statistics() -> dict[str, Any]:
    return {
        "count": 0,
        "minimum": None,
        "maximum": None,
        "mean": None,
        "median": None,
        "q1": None,
        "q3": None,
        "iqr": None,
        "priceRange": None,
        "standardDeviation": None,
        "coefficientOfVariation": None,
        "lowerFence": None,
        "upperFence": None,
        "outlierCount": 0,
        "histogram": [],
    }


def _empty_comparison() -> dict[str, Any]:
    return {
        "difference": None,
        "differenceRate": None,
        "position": "unknown",
        "label": "比較不可",
    }
