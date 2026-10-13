"""Manually refresh active saved searches and evaluate persisted alert targets."""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from Main.infrastructure.marketplaces.yahoo import YahooMarketplaceProvider
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.models.sellerlisting import SellerListing
from Main.models.watchitem import WatchItem
from Main.services.alert_rules import (
    evaluate_saved_search_alert_rules,
    evaluate_seller_alert_rules,
    evaluate_watch_alert_rules,
)
from Main.services.job_lock import (
    JOB_ALREADY_RUNNING_EXIT_CODE,
    JobAlreadyRunning,
    alert_job_lock,
)
from Main.services.market_search import (
    TargetSearchFailure,
    execute_target_search,
    record_target_search_failure,
)
from Main.services.notifications import notify_saved_search_run
from Main.services.ownership import RequestOwner
from Main.services.saved_searches import criteria_from_saved_search, is_saved_search_due
from Main.services.search_persistence import DjangoSearchRepository
from Main.services.watchlist import refresh_watched_item

DEFAULT_MAX_RUNTIME_SECONDS = 30 * 60
POSITIVE_OPTIONS = ("user_id", "saved_search_id", "max_runtime_seconds")


class TimeBudgetExhausted(Exception):
    pass


class Command(BaseCommand):
    help = (
        "Refresh active saved searches and evaluate enabled alert rules. Runs one at a time, "
        "stops at a time budget, and exits non-zero when a saved search fails."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--user-id", type=int)
        parser.add_argument("--saved-search-id", type=int)
        parser.add_argument(
            "--evaluate-only",
            action="store_true",
            help="Do not call Yahoo; evaluate the latest persisted target state only.",
        )
        parser.add_argument(
            "--max-runtime-seconds",
            type=int,
            help=f"Stop before the next unit after this many seconds "
            f"(default {DEFAULT_MAX_RUNTIME_SECONDS}).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        for name in POSITIVE_OPTIONS:
            value = options.get(name)
            if value is not None and value <= 0:
                raise CommandError(f"--{name.replace('_', '-')} must be positive")
        budget = options.get("max_runtime_seconds") or DEFAULT_MAX_RUNTIME_SECONDS
        try:
            with alert_job_lock() as check_lock:
                self._run(options, budget, check_lock)
        except JobAlreadyRunning:
            raise CommandError(
                "Alert job is already running; skipped this run",
                returncode=JOB_ALREADY_RUNNING_EXIT_CODE,
            ) from None

    def _run(self, options: dict[str, Any], budget: int, check_lock: Callable[[], None]) -> None:
        started = monotonic()

        def before_unit() -> None:
            check_lock()
            if monotonic() - started > budget:
                raise TimeBudgetExhausted

        searches = SavedSearch.objects.filter(is_active=True, user__is_active=True).select_related(
            "user"
        )
        if options["user_id"]:
            searches = searches.filter(user_id=options["user_id"])
        if options["saved_search_id"]:
            searches = searches.filter(pk=options["saved_search_id"])
            if not searches.exists():
                raise CommandError("対象の有効な保存検索が見つかりません")

        counts = {"refreshed": 0, "failed": 0, "notifications": 0, "not_due": 0}
        now = timezone.now()
        try:
            for saved_search in searches.iterator():
                before_unit()
                if options["evaluate_only"]:
                    counts["notifications"] += self._evaluate_latest(saved_search)
                elif options["saved_search_id"] or is_saved_search_due(saved_search, now):
                    # An explicitly named search runs now; others wait for their interval.
                    self._refresh(saved_search, counts)
                else:
                    counts["not_due"] += 1
            # A run scoped to one saved search does not touch unrelated watch or seller targets.
            if not options["saved_search_id"]:
                self._evaluate_targets(options, counts, before_unit)
        except TimeBudgetExhausted:
            self._summary(counts)
            raise CommandError(
                f"time budget exhausted after {budget}s; remaining targets were not processed"
            ) from None

        self._summary(counts)
        if counts["failed"]:
            raise CommandError(f"{counts['failed']} failed searches")

    def _summary(self, counts: dict[str, int]) -> None:
        self.stdout.write(
            self.style.SUCCESS(
                f"saved_searches_refreshed={counts['refreshed']} failed={counts['failed']} "
                f"notifications_created={counts['notifications']} not_due={counts['not_due']}"
            )
        )

    @staticmethod
    def _evaluate_latest(saved_search: SavedSearch) -> int:
        # A newer failed run means the persisted state is stale, so it suppresses evaluation.
        latest = SearchRun.objects.filter(
            saved_search=saved_search,
            user=saved_search.user,
            search_type=SearchRun.CURRENT,
        ).first()
        if latest is None or not latest.succeeded:
            return 0
        return evaluate_saved_search_alert_rules(latest)

    def _refresh(self, saved_search: SavedSearch, counts: dict[str, int]) -> None:
        owner = RequestOwner(user=saved_search.user, session_key="")
        repository = DjangoSearchRepository()
        try:
            criteria = criteria_from_saved_search(saved_search)
            result = execute_target_search(
                criteria=criteria,
                owner=owner,
                provider=YahooMarketplaceProvider(),
                repository=repository,
                refresh_watch=refresh_watched_item,
                trigger="scheduled",
                saved_search=saved_search,
            )
            current_run = next(
                (
                    run
                    for run in reversed(result.runs)
                    if run.search_type == "current" and run.succeeded
                ),
                None,
            )
            if current_run is not None:
                notify_saved_search_run(current_run)
                counts["notifications"] += evaluate_saved_search_alert_rules(current_run)
                counts["refreshed"] += 1
            else:
                counts["failed"] += 1
        except TargetSearchFailure as failure:
            runs = record_target_search_failure(
                failure,
                criteria=criteria,
                owner=owner,
                repository=repository,
                trigger="scheduled",
                saved_search=saved_search,
            )
            notify_saved_search_run(runs[-1])
            counts["failed"] += 1
        except Exception as error:
            counts["failed"] += 1
            self.stderr.write(f"saved search {saved_search.pk}: {error.__class__.__name__}")
        SavedSearch.objects.filter(pk=saved_search.pk).update(last_run_at=timezone.now())

    @staticmethod
    def _evaluate_targets(
        options: dict[str, Any], counts: dict[str, int], before_unit: Callable[[], None]
    ) -> None:
        watches = WatchItem.objects.filter(user__isnull=False, lifecycle_status="active")
        sellers = SellerListing.objects.filter(user__isnull=False).exclude(
            status__in=("sold", "cancelled")
        )
        if options["user_id"]:
            watches = watches.filter(user_id=options["user_id"])
            sellers = sellers.filter(user_id=options["user_id"])
        for item in watches.iterator():
            before_unit()
            latest = item.price_snapshots.first()
            counts["notifications"] += evaluate_watch_alert_rules(
                item,
                remaining_seconds=latest.remaining_seconds if latest else None,
            )
        for seller in sellers.iterator():
            before_unit()
            counts["notifications"] += evaluate_seller_alert_rules(seller)
