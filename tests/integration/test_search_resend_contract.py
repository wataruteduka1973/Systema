"""A0.7 resend and concurrency contract for search runs (ADR 0003, current behavior).

Until X1 introduces acquisition_id, every search execution is a new observation: a
resend creates a new SearchRun with its own rows, while notifications for one run are
deduplicated. Concurrent saves must stay atomic and owner-scoped.
"""

from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import close_old_connections, connection

from Main.domain.market_listing import MarketListingObservation
from Main.management.commands import run_alerts
from Main.models.notification import Notification
from Main.models.savedsearch import SavedSearch
from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.services.notifications import notify_saved_search_run
from Main.services.ownership import RequestOwner
from Main.services.search_persistence import MAX_RETAINED_RUNS, persist_successful_search

CONCURRENT_ROUNDS = 20

postgresql_only = pytest.mark.skipif(
    connection.vendor != "postgresql", reason="PostgreSQL concurrency check"
)

ITEMS = [
    {
        "name": f"中古 ゲーム機 {index}",
        "price": 20000 + index,
        "startPrice": 10000,
        "bidding": index,
        "url": f"https://auctions.yahoo.co.jp/jp/auction/a10000000{index}",
    }
    for index in range(3)
]


class _Provider:
    marketplace = "test_market"

    def search_closed(self, keyword: str) -> list[MarketListingObservation]:
        return [self._observation("落札カメラ", 20000, "終了")]

    def search_current(self, keyword: str) -> list[MarketListingObservation]:
        return [self._observation("出品中カメラ", 10000, "30分")]

    @staticmethod
    def _observation(name: str, price: int, time: str) -> MarketListingObservation:
        return MarketListingObservation(
            marketplace="test_market",
            external_id="a123456789",
            name=name,
            price=price,
            start_price=price,
            bidding=1,
            time=time,
            url="https://auctions.yahoo.co.jp/jp/auction/a123456789",
        )


def _save(user_id: int, keyword: str = "ゲーム機") -> SearchRun:
    owner = RequestOwner(user=get_user_model().objects.get(pk=user_id), session_key="")
    return persist_successful_search(
        owner=owner, keyword=keyword, search_type=SearchRun.CLOSED, items=ITEMS
    )


def _run_concurrently(task, arguments):
    barrier = Barrier(len(arguments))

    def run(argument):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            return task(argument)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=len(arguments)) as executor:
        return list(executor.map(run, arguments))


@pytest.mark.django_db
def test_resending_a_saved_search_creates_new_runs_and_one_notification_per_run(monkeypatch):
    user = get_user_model().objects.create_user("resend-owner")
    saved = SavedSearch.objects.create(user=user, name="カメラ", keyword="カメラ")
    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", _Provider)
    monkeypatch.setattr(run_alerts, "evaluate_saved_search_alert_rules", lambda run: 0)

    call_command("run_alerts", saved_search_id=saved.pk, stdout=StringIO())
    call_command("run_alerts", saved_search_id=saved.pk, stdout=StringIO())

    runs = list(SearchRun.objects.filter(saved_search=saved).order_by("created_at", "pk"))
    assert [run.search_type for run in runs] == ["closed", "current"] * 2
    assert len({run.pk for run in runs}) == 4
    assert all(run.items.count() == 1 for run in runs)
    current_runs = [run for run in runs if run.search_type == SearchRun.CURRENT]
    notifications = Notification.objects.filter(user=user, event_type="saved_search_succeeded")
    assert sorted(notifications.values_list("source_id", flat=True)) == sorted(
        run.pk for run in current_runs
    )

    notify_saved_search_run(current_runs[-1])

    assert notifications.count() == 2


@postgresql_only
@pytest.mark.django_db(transaction=True)
def test_concurrent_identical_saves_keep_separate_complete_runs_on_postgresql():
    # Several rounds: a pruning race that deletes the other transaction's committed run
    # only shows up when one save commits between the other's prune statements.
    for round_number in range(CONCURRENT_ROUNDS):
        user = get_user_model().objects.create_user(f"concurrent-saver-{round_number}")

        runs = _run_concurrently(lambda user_id: _save(user_id).pk, [user.pk, user.pk])

        assert len(set(runs)) == 2
        assert set(
            SearchRun.objects.filter(user=user, succeeded=True).values_list("pk", flat=True)
        ) == set(runs)
        for run_id in runs:
            assert scraping.objects.filter(search_run_id=run_id).count() == len(ITEMS)


@postgresql_only
@pytest.mark.django_db(transaction=True)
def test_concurrent_saves_by_different_owners_do_not_share_runs_on_postgresql():
    users = [get_user_model().objects.create_user(f"owner-{index}") for index in range(2)]

    runs = _run_concurrently(lambda user_id: _save(user_id).pk, [user.pk for user in users])

    for user, run_id in zip(users, runs, strict=True):
        run = SearchRun.objects.get(pk=run_id)
        assert run.user_id == user.pk
        assert run.session_key == ""
        assert SearchRun.objects.filter(user=user).count() == 1
        assert run.items.count() == len(ITEMS)


@postgresql_only
@pytest.mark.django_db(transaction=True)
def test_concurrent_notification_resend_for_one_run_creates_one_notification_on_postgresql():
    user = get_user_model().objects.create_user("notify-resend")
    run = _save(user.pk)
    run.saved_search = SavedSearch.objects.create(user=user, name="ゲーム機", keyword="ゲーム機")
    run.save(update_fields=("saved_search",))

    _run_concurrently(
        lambda run_id: notify_saved_search_run(SearchRun.objects.get(pk=run_id)),
        [run.pk, run.pk],
    )

    assert Notification.objects.filter(user=user, source_id=run.pk).count() == 1


@postgresql_only
@pytest.mark.django_db(transaction=True)
def test_concurrent_saves_at_retention_limit_converge_on_next_save_on_postgresql():
    user = get_user_model().objects.create_user("retention-race")
    for _ in range(MAX_RETAINED_RUNS - 1):
        _save(user.pk)

    _run_concurrently(lambda user_id: _save(user_id), [user.pk, user.pk])

    # Each transaction prunes without seeing the other's uncommitted run, so the limit
    # can be exceeded by the number of concurrent saves until the next save prunes.
    retained = SearchRun.objects.filter(user=user).count()
    assert MAX_RETAINED_RUNS <= retained <= MAX_RETAINED_RUNS + 1
    _save(user.pk)
    assert SearchRun.objects.filter(user=user).count() == MAX_RETAINED_RUNS
    assert scraping.objects.filter(search_run__user=user).count() == MAX_RETAINED_RUNS * len(ITEMS)


@pytest.mark.django_db
def test_sequential_saves_keep_only_the_newest_runs_up_to_the_retention_limit():
    user = get_user_model().objects.create_user("retention-sequential")
    run_ids = [_save(user.pk).pk for _ in range(MAX_RETAINED_RUNS + 2)]

    retained = set(SearchRun.objects.filter(user=user).values_list("pk", flat=True))

    assert retained == set(run_ids[2:])
    assert scraping.objects.filter(search_run__user=user).count() == MAX_RETAINED_RUNS * len(ITEMS)
