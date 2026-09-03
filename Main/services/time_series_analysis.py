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


def analyze_snapshot_history(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """検索実行時刻ごとの価格中央値とIQRを履歴グラフ用に集計する。"""
    rows = [
        {"snapshot": item.get("SearchDay"), "price": _positive_number(item.get("EndPrice"))}
        for item in items
    ]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return []
    frame["snapshot"] = pd.to_datetime(frame["snapshot"], errors="coerce")
    frame = frame.dropna(subset=["snapshot", "price"])
    if frame.empty:
        return []
    points = []
    for snapshot, group in frame.groupby("snapshot"):
        prices = group["price"].astype("float64")
        q1, q3 = float(prices.quantile(0.25)), float(prices.quantile(0.75))
        iqr = q3 - q1
        inliers = prices[(prices >= max(0.0, q1 - 1.5 * iqr)) & (prices <= q3 + 1.5 * iqr)]
        if inliers.empty:
            inliers = prices
        points.append(
            {
                "date": snapshot.isoformat(),
                "median": int(round(inliers.median())),
                "q1": int(round(inliers.quantile(0.25))),
                "q3": int(round(inliers.quantile(0.75))),
                "count": int(inliers.count()),
            }
        )
    return points


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
            "moving_avg": (
                int(round(rolling_by_day.get(row.date.normalize()))) if not row.isOutlier else None
            ),
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
        "backtest": backtest_market_prediction(items, reference),
    }


def backtest_market_prediction(
    items: list[dict[str, Any]],
    reference: datetime,
    lookback_days: int = 90,
    horizon_days: int = 30,
    max_windows: int = 8,
) -> dict[str, Any]:
    """過去時点だけで学習し、将来の日次中央値に対する予測誤差を検証する。"""
    rows = []
    for item in items:
        date = parse_auction_date(item.get("time"), reference)
        price = _positive_number(item.get("price"))
        if date is not None and price is not None and date <= reference:
            rows.append({"date": date, "price": price})
    if not rows:
        return _empty_backtest(horizon_days)
    frame = pd.DataFrame(rows)
    frame["day"] = frame["date"].dt.normalize()
    daily = frame.groupby("day")["price"].median().sort_index()
    if len(daily) < 6:
        return _empty_backtest(horizon_days)
    eligible = daily.index[
        (daily.index >= daily.index.min() + timedelta(days=min(14, lookback_days)))
        & (daily.index <= daily.index.max() - timedelta(days=horizon_days))
    ]
    if len(eligible) == 0:
        return _empty_backtest(horizon_days)
    selected = eligible[
        np.linspace(0, len(eligible) - 1, min(max_windows, len(eligible)), dtype=int)
    ]
    points = []
    for cutoff in selected.unique():
        train = daily[
            (daily.index >= cutoff - timedelta(days=lookback_days)) & (daily.index <= cutoff)
        ]
        target = cutoff + timedelta(days=horizon_days)
        actual_window = daily[
            (daily.index >= target - timedelta(days=3))
            & (daily.index <= target + timedelta(days=3))
        ]
        if len(train) < 3 or actual_window.empty:
            continue
        q1, q3 = float(train.quantile(0.25)), float(train.quantile(0.75))
        iqr = q3 - q1
        filtered = train[(train >= max(0.0, q1 - 1.5 * iqr)) & (train <= q3 + 1.5 * iqr)]
        if len(filtered) >= 3:
            train = filtered
        x = (train.index - train.index.min()).days.to_numpy(dtype=float)
        y = train.to_numpy(dtype=float)
        if np.ptp(x) > 0:
            slope, intercept = np.polyfit(x, y, 1)
            fitted = intercept + slope * x
            predicted = max(0.0, float(intercept + slope * (float(x[-1]) + horizon_days)))
            residual_scale = float(np.sqrt(np.mean((y - fitted) ** 2)))
        else:
            predicted, residual_scale = float(np.median(y)), float(np.std(y))
        margin = max(residual_scale * 1.96, predicted * 0.05)
        actual = (
            float(daily.loc[target]) if target in daily.index else float(actual_window.median())
        )
        latest = float(train.iloc[-1])
        points.append(
            {
                "cutoffDate": cutoff.date().isoformat(),
                "targetDate": target.date().isoformat(),
                "predictedPrice": int(round(predicted)),
                "actualPrice": int(round(actual)),
                "absoluteError": int(round(abs(predicted - actual))),
                "percentageError": round(abs(predicted - actual) / actual * 100, 1),
                "withinInterval": max(0.0, predicted - margin) <= actual <= predicted + margin,
                "directionCorrect": (predicted - latest) * (actual - latest) >= 0,
            }
        )
    if not points:
        return _empty_backtest(horizon_days)
    errors = np.array(
        [point["predictedPrice"] - point["actualPrice"] for point in points], dtype=float
    )
    return {
        "available": True,
        "horizonDays": horizon_days,
        "windowCount": len(points),
        "mae": int(round(float(np.mean(np.abs(errors))))),
        "rmse": int(round(float(np.sqrt(np.mean(errors**2))))),
        "mape": round(float(np.mean([point["percentageError"] for point in points])), 1),
        "intervalCoverage": round(
            sum(point["withinInterval"] for point in points) / len(points) * 100, 1
        ),
        "directionAccuracy": round(
            sum(point["directionCorrect"] for point in points) / len(points) * 100, 1
        ),
        "points": points,
        "warning": "" if len(points) >= 3 else "検証可能な期間が少ないため、精度指標は参考値です。",
    }


def _empty_backtest(horizon_days: int) -> dict[str, Any]:
    return {
        "available": False,
        "horizonDays": horizon_days,
        "windowCount": 0,
        "points": [],
        "warning": "30日先まで実績がある期間が不足しているため、バックテストを実行できません。",
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
