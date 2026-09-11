"""Manually refresh active saved searches and evaluate persisted alert targets."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory
from django.utils import timezone

from Main.models.savedsearch import SavedSearch
from Main.models.sellerlisting import SellerListing
from Main.models.watchitem import WatchItem
from Main.services.alert_rules import (
    evaluate_saved_search_alert_rules,
    evaluate_seller_alert_rules,
    evaluate_watch_alert_rules,
)
from Main.services.notifications import notify_saved_search_run
from Main.services.saved_searches import criteria_from_saved_search
from Main.views.utils import complex_market_data_logic


class Command(BaseCommand):
    help = "Refresh active saved searches and evaluate enabled Phase 6 alert rules."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--user-id", type=int)
        parser.add_argument("--saved-search-id", type=int)
        parser.add_argument(
            "--evaluate-only",
            action="store_true",
            help="Do not call Yahoo; evaluate the latest persisted target state only.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        searches = SavedSearch.objects.filter(is_active=True).select_related("user")
        if options["user_id"]:
            searches = searches.filter(user_id=options["user_id"])
        if options["saved_search_id"]:
            searches = searches.filter(pk=options["saved_search_id"])
            if not searches.exists():
                raise CommandError("対象の有効な保存検索が見つかりません")

        refreshed = failed = notifications = 0
        if not options["evaluate_only"]:
            factory = RequestFactory()
            for saved_search in searches.iterator():
                request = factory.get("/taskle/complex_market_data")
                request.user = saved_search.user
                request.saved_search = saved_search
                request.search_trigger = "scheduled"
                try:
                    response = complex_market_data_logic(
                        request, criteria_from_saved_search(saved_search)
                    )
                    runs = getattr(request, "recorded_search_runs", [])
                    if runs:
                        notify_saved_search_run(runs[-1])
                    current_run = next(
                        (
                            run
                            for run in reversed(runs)
                            if run.search_type == "current" and run.succeeded
                        ),
                        None,
                    )
                    if response.status_code < 400 and current_run is not None:
                        notifications += evaluate_saved_search_alert_rules(current_run)
                        refreshed += 1
                    else:
                        failed += 1
                except Exception as error:
                    failed += 1
                    self.stderr.write(f"saved search {saved_search.pk}: {error.__class__.__name__}")
                SavedSearch.objects.filter(pk=saved_search.pk).update(last_run_at=timezone.now())

        watches = WatchItem.objects.filter(user__isnull=False, lifecycle_status="active")
        sellers = SellerListing.objects.filter(user__isnull=False).exclude(
            status__in=("sold", "cancelled")
        )
        if options["user_id"]:
            watches = watches.filter(user_id=options["user_id"])
            sellers = sellers.filter(user_id=options["user_id"])
        for item in watches.iterator():
            latest = item.price_snapshots.first()
            notifications += evaluate_watch_alert_rules(
                item,
                remaining_seconds=latest.remaining_seconds if latest else None,
            )
        for item in sellers.iterator():
            notifications += evaluate_seller_alert_rules(item)

        self.stdout.write(
            self.style.SUCCESS(
                f"saved_searches_refreshed={refreshed} failed={failed} "
                f"notifications_created={notifications}"
            )
        )
