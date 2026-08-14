"""市場価格の時系列集計と短期予測。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from Main.domain.product_condition import enrich_market_items, summarize_condition_market
from Main.services.market_statistics import analyze_market_prices


def parse_auction_date(value: object, reference: datetime) -> datetime | None:
    """Yahooの日付表記とISO 8601を、比較可能な日時へ変換する。"""
    text = str(value or "").strip()
    if not text or text == "N/A":
        return None
    try:
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        parsed = datetime.strptime(f"{reference.year}/{text}", "%Y/%m/%d %H:%M")
        return parsed.replace(year=reference.year - 1) if parsed > reference else parsed
    except (TypeError, ValueError):
        return None


def analyze_stored_market(items: list[dict[str, Any]], reference: datetime) -> dict[str, Any]:
    """保存済み相場データからサマリー・日次推移・状態別統計を作る。"""
    normalized = [
        {
            "name": item.get("Name", ""),
            "price": item.get("EndPrice"),
            "date": parse_auction_date(item.get("SearchDay"), reference),
        }
        for item in items
    ]
    enriched = enrich_market_items(normalized)
    return {
        "summary": analyze_market_prices(enriched),
        "timeSeries": _daily_series(enriched),
        "conditionMarket": summarize_condition_market(enriched),
    }


def predict_market_prices(
    items: list[dict[str, Any]], reference: datetime, lookback_days: int = 90
) -> dict[str, Any] | None:
    """直近相場を日次集計し、堅牢な線形トレンドで30日後を予測する。"""
    rows = []
    cutoff = reference - timedelta(days=lookback_days)
    for item in items:
        date = parse_auction_date(item.get("time"), reference)
        price = _positive_number(item.get("price"))
        if date is not None and price is not None and cutoff <= date <= reference:
            rows.append({"originalDate": item.get("time"), "date": date, "price": price})
    if not rows:
        return None

    frame = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    q1 = float(frame["price"].quantile(0.25))
    q3 = float(frame["price"].quantile(0.75))
    iqr = q3 - q1
    lower, upper = max(0.0, q1 - 1.5 * iqr), q3 + 1.5 * iqr
    frame["isOutlier"] = (frame["price"] < lower) | (frame["price"] > upper)
    clean = frame.loc[~frame["isOutlier"]].copy()
    if clean.empty:
        clean = frame.copy()
        frame["isOutlier"] = False

    clean["day"] = clean["date"].dt.normalize()
    daily = clean.groupby("day")["price"].agg(
        median="median",
        q1=lambda values: values.quantile(0.25),
        q3=lambda values: values.quantile(0.75),
        count="count",
    )
    daily["rollingMedian"] = daily["median"].rolling("14D", min_periods=1).median()

    x = (daily.index - daily.index.min()).days.to_numpy(dtype=float)
    y = daily["median"].to_numpy(dtype=float)
    if len(daily) >= 3 and np.ptp(x) > 0:
        slope, intercept = np.polyfit(x, y, 1)
        fitted = intercept + slope * x
        predicted = intercept + slope * (float(x[-1]) + 30.0)
        residual_scale = float(np.sqrt(np.mean((y - fitted) ** 2)))
        method = "日次中央値の線形トレンド"
    else:
        predicted = float(np.median(y))
        residual_scale = float(np.std(y))
        slope = 0.0
        method = "日次中央値"
    predicted = max(0.0, predicted)
    margin = max(residual_scale * 1.96, predicted * 0.05)
    interval = [int(round(max(0.0, predicted - margin))), int(round(predicted + margin))]
    rolling_by_day = daily["rollingMedian"].to_dict()

    trends = [
        {
            "date": row.originalDate,
            "isoDate": row.date.isoformat(),
            "price": int(round(row.price)),
            "moving_avg": int(round(rolling_by_day.get(row.date.normalize())))
            if not row.isOutlier
            else None,
            "isOutlier": bool(row.isOutlier),
        }
        for row in frame.itertuples(index=False)
    ]
    daily_trends = [
        {
            "date": index.date().isoformat(),
            "median": int(round(row["median"])),
            "q1": int(round(row["q1"])),
            "q3": int(round(row["q3"])),
            "count": int(row["count"]),
            "rollingMedian": int(round(row["rollingMedian"])),
        }
        for index, row in daily.iterrows()
    ]
    trend_percent = slope * 30 / float(np.median(y)) * 100 if np.median(y) else 0.0
    warning = "" if len(clean) >= 10 else "データが少なく、予測の不確実性が高い可能性があります。"
    return {
        "moving_average": int(round(daily["rollingMedian"].iloc[-1])),
        "predicted_price": int(round(predicted)),
        "confidence_interval": interval,
        "prediction_interval": interval,
        "price_trends": trends,
        "daily_trends": daily_trends,
        "quality": {
            "sampleCount": int(len(frame)),
            "usedCount": int(len(clean)),
            "outlierCount": int(frame["isOutlier"].sum()),
            "lookbackDays": lookback_days,
            "method": method,
            "trendPercent30Days": round(trend_percent, 1),
            "warning": warning,
        },
    }


def _daily_series(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        item
        for item in items
        if item.get("date") is not None and _positive_number(item.get("price"))
    ]
    if not rows:
        return []
    frame = pd.DataFrame(rows)
    frame["day"] = pd.to_datetime(frame["date"]).dt.normalize()
    daily = frame.groupby("day")["price"].agg(
        median="median",
        q1=lambda values: values.quantile(0.25),
        q3=lambda values: values.quantile(0.75),
        count="count",
    )
    return [
        {
            "date": index.date().isoformat(),
            "median": int(round(row["median"])),
            "q1": int(round(row["q1"])),
            "q3": int(round(row["q3"])),
            "count": int(row["count"]),
        }
        for index, row in daily.iterrows()
    ]


def _positive_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None
