"""Top-page entry points into market search: recent keywords and keywords whose market moved.

Both read the owner's saved search runs only; nothing here contacts Yahoo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db.models import QuerySet

from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.services.market_statistics import analyze_market_prices

# How many recent runs are scanned; enough for a page of keywords without loading full history.
RUN_SCAN_LIMIT = 300
MOVE_THRESHOLD_PERCENT = 5.0


@dataclass(frozen=True)
class RecentKeyword:
    keyword: str
    searched_at: datetime
    # "history" opens the saved closed data (no Yahoo request); "current" searches current listings.
    mode: str


@dataclass(frozen=True)
class MarketMove:
    keyword: str
    latest_median: int
    previous_median: int
    change_percent: float
    latest_at: datetime
    previous_at: datetime

    @property
    def direction(self) -> str:
        return "up" if self.change_percent > 0 else "down"


@dataclass(frozen=True)
class MarketActivity:
    recent: list[RecentKeyword]
    moves: list[MarketMove]
    comparable_count: int


def _saved_runs(user: Any, search_types: tuple[str, ...]) -> QuerySet[SearchRun]:
    return SearchRun.objects.filter(
        user=user, succeeded=True, search_type__in=search_types, item_count__gt=0
    ).order_by("-created_at", "-pk")[:RUN_SCAN_LIMIT]


def recent_keywords(user: Any, limit: int = 6) -> list[RecentKeyword]:
    runs = list(
        _saved_runs(user, (SearchRun.CLOSED, SearchRun.CURRENT)).values(
            "keyword", "search_type", "created_at"
        )
    )
    with_closed = {run["keyword"] for run in runs if run["search_type"] == SearchRun.CLOSED}
    result: list[RecentKeyword] = []
    seen: set[str] = set()
    for run in runs:
        if run["keyword"] in seen:
            continue
        seen.add(run["keyword"])
        mode = "history" if run["keyword"] in with_closed else "current"
        result.append(RecentKeyword(run["keyword"], run["created_at"], mode))
        if len(result) == limit:
            break
    return result


def _median(run_id: int) -> float | None:
    prices = scraping.objects.filter(search_run_id=run_id).values_list("EndPrice", flat=True)
    return analyze_market_prices({"price": price} for price in prices)["median"]


def market_moves(user: Any, limit: int = 4, candidates: int = 20) -> tuple[list[MarketMove], int]:
    """Compare each keyword's two newest saved closed runs; return moves of 5% or more.

    Also returns how many keywords had two runs to compare, so the page can explain an empty list.
    """
    latest_two: dict[str, list[dict[str, Any]]] = {}
    for run in _saved_runs(user, (SearchRun.CLOSED,)).values("pk", "keyword", "created_at"):
        runs = latest_two.setdefault(run["keyword"], [])
        if len(runs) < 2:
            runs.append(run)
    comparable = [runs for runs in latest_two.values() if len(runs) == 2][:candidates]
    moves = []
    for latest, previous in comparable:
        latest_median, previous_median = _median(latest["pk"]), _median(previous["pk"])
        if not latest_median or not previous_median:
            continue
        change = round((latest_median - previous_median) / previous_median * 100, 1)
        if abs(change) >= MOVE_THRESHOLD_PERCENT:
            moves.append(
                MarketMove(
                    latest["keyword"],
                    round(latest_median),
                    round(previous_median),
                    change,
                    latest["created_at"],
                    previous["created_at"],
                )
            )
    moves.sort(key=lambda move: abs(move.change_percent), reverse=True)
    return moves[:limit], len(comparable)


def market_activity_for(user: Any) -> MarketActivity:
    moves, comparable_count = market_moves(user)
    return MarketActivity(recent_keywords(user), moves, comparable_count)
