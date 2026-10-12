"""Top-page recommendations picked from the owner's stored saved-search results.

Nothing is fetched from Yahoo here: the cards reuse the latest successful current-listing
snapshot of each active saved search, which already carries the target-analysis buy decision.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone

from Main.domain.listing_image import safe_image_url
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.models.watchitem import WatchItem
from Main.services.watchlist import is_watchable_url

RECOMMENDED_STATUSES = {"strong_buy", "buy"}
DEFAULT_LIMIT = 6


@dataclass(frozen=True)
class SnapshotPair:
    """The latest snapshot of one saved search and the one before it (for "new" detection)."""

    saved_search_name: str
    keyword: str
    observed_at: datetime
    items: Sequence[Mapping[str, Any]]
    median_price: float
    previous_urls: frozenset[str] | None


@dataclass(frozen=True)
class Recommendation:
    name: str
    url: str
    image_url: str
    price: int
    market_median: float
    discount_rate: float | None
    decision_status: str
    decision_label: str
    decision_score: int
    decision_reason: str
    condition: str
    condition_label: str
    bidding: int | None
    remaining_time: str
    ends_at: datetime | None
    is_new: bool
    saved_search_name: str
    observed_at: datetime
    watch_payload: dict[str, Any]

    @property
    def difference_label(self) -> str:
        """Signed market difference as shown on the target-analysis cards ("相場比 -46.7%")."""
        if self.discount_rate is None:
            return ""
        return f"相場比 {self.discount_rate:+.1f}%"

    @property
    def market_position(self) -> str:
        """Same bands as Main/services/market_statistics.py (±15%)."""
        if self.discount_rate is None:
            return "near"
        if self.discount_rate <= -15:
            return "below"
        return "above" if self.discount_rate >= 15 else "near"


def _int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return int(value)


def _recommendation(
    item: Mapping[str, Any], pair: SnapshotPair, now: datetime
) -> Recommendation | None:
    decision = item.get("buyDecision")
    if not isinstance(decision, Mapping) or decision.get("status") not in RECOMMENDED_STATUSES:
        return None
    url = str(item.get("url") or "")
    name = str(item.get("name") or "").strip()
    price = _int(item.get("price"))
    if not name or price is None or price <= 0 or not is_watchable_url(url):
        return None

    remaining = _int(item.get("remainingSeconds"))
    ends_at = pair.observed_at + timedelta(seconds=remaining) if remaining is not None else None
    if ends_at is not None and ends_at <= now:
        return None

    comparison = item.get("marketComparison")
    discount = comparison.get("differenceRate") if isinstance(comparison, Mapping) else None
    is_new = pair.previous_urls is not None and url not in pair.previous_urls
    return Recommendation(
        name=name,
        url=url,
        image_url=safe_image_url(item.get("imageUrl")),
        price=price,
        market_median=float(item.get("marketMedian") or pair.median_price or 0),
        discount_rate=float(discount) if isinstance(discount, (int, float)) else None,
        decision_status=str(decision.get("status")),
        decision_label=str(decision.get("label") or ""),
        decision_score=_int(decision.get("score")) or 0,
        decision_reason=str(decision.get("reason") or ""),
        condition=str(item.get("condition") or "unknown"),
        condition_label=str(item.get("conditionLabel") or ""),
        bidding=_int(item.get("bidding")),
        remaining_time=str(item.get("remainingTime") or ""),
        ends_at=ends_at,
        is_new=is_new,
        saved_search_name=pair.saved_search_name,
        observed_at=pair.observed_at,
        watch_payload={
            "name": name,
            "url": url,
            "currentPrice": price,
            "marketMedian": item.get("marketMedian") or pair.median_price,
            "bidding": _int(item.get("bidding")) or 0,
            "condition": str(item.get("condition") or "unknown"),
            "conditionLabel": str(item.get("conditionLabel") or ""),
            "remainingTime": str(item.get("remainingTime") or ""),
            "remainingSeconds": remaining,
            "searchKeyword": pair.keyword,
        },
    )


def select_recommendations(
    pairs: Iterable[SnapshotPair],
    watched_urls: set[str],
    *,
    now: datetime,
    limit: int = DEFAULT_LIMIT,
) -> list[Recommendation]:
    """Buy candidates not yet watched or ended, new ones first, then by buy score."""
    best: dict[str, Recommendation] = {}
    for pair in pairs:
        for item in pair.items:
            if not isinstance(item, Mapping):
                continue
            candidate = _recommendation(item, pair, now)
            if candidate is None or candidate.url in watched_urls:
                continue
            current = best.get(candidate.url)
            if current is None or candidate.decision_score > current.decision_score:
                best[candidate.url] = candidate
    ordered = sorted(
        best.values(),
        key=lambda item: (
            not item.is_new,
            -item.decision_score,
            item.ends_at or datetime.max.replace(tzinfo=now.tzinfo),
        ),
    )
    return ordered[:limit]


def _snapshot_items(run: SearchRun) -> list[Mapping[str, Any]]:
    snapshot = run.result_snapshot if isinstance(run.result_snapshot, dict) else {}
    items = snapshot.get("recommend_items", [])
    return [item for item in items if isinstance(item, Mapping)] if isinstance(items, list) else []


def snapshot_pairs_for(user: Any) -> list[SnapshotPair]:
    """Latest and previous successful current-listing snapshot of each active saved search."""
    pairs: list[SnapshotPair] = []
    for saved in SavedSearch.objects.filter(user=user, is_active=True):
        runs = list(
            SearchRun.objects.filter(
                user=user,
                saved_search=saved,
                search_type=SearchRun.CURRENT,
                succeeded=True,
            )
            .exclude(result_snapshot={})
            .order_by("-created_at", "-pk")[:2]
        )
        if not runs:
            continue
        latest = runs[0]
        previous_urls = (
            frozenset(str(item.get("url")) for item in _snapshot_items(runs[1]) if item.get("url"))
            if len(runs) > 1
            else None
        )
        snapshot = latest.result_snapshot if isinstance(latest.result_snapshot, dict) else {}
        pairs.append(
            SnapshotPair(
                saved_search_name=saved.name,
                keyword=saved.keyword,
                observed_at=latest.created_at,
                items=_snapshot_items(latest),
                median_price=float(snapshot.get("medianPrice") or 0),
                previous_urls=previous_urls,
            )
        )
    return pairs


@dataclass(frozen=True)
class RecommendationSection:
    has_saved_searches: bool
    items: list[Recommendation]
    last_observed_at: datetime | None


def recommendations_for(user: Any, *, limit: int = DEFAULT_LIMIT) -> RecommendationSection:
    """Recommendation cards for a signed-in user's top page."""
    pairs = snapshot_pairs_for(user)
    watched_urls = set(WatchItem.objects.filter(user=user).values_list("url", flat=True))
    return RecommendationSection(
        has_saved_searches=SavedSearch.objects.filter(user=user, is_active=True).exists(),
        items=select_recommendations(pairs, watched_urls, now=timezone.now(), limit=limit),
        last_observed_at=max((pair.observed_at for pair in pairs), default=None),
    )
