"""Top-page market activity: recent keywords and keywords whose saved closed market moved."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.services.market_activity import market_moves, recent_keywords

pytestmark = pytest.mark.django_db


def _run(user, keyword, prices, *, search_type=SearchRun.CLOSED, days_ago=0, succeeded=True):
    run = SearchRun.objects.create(
        user=user,
        keyword=keyword,
        search_type=search_type,
        item_count=len(prices),
        succeeded=succeeded,
    )
    SearchRun.objects.filter(pk=run.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
    scraping.objects.bulk_create(
        scraping(
            search_run=run,
            SearchWord=keyword,
            SearchDay="2026-10-01",
            Bidding="1",
            EndPrice=price,
            StartPrice=1,
            Name=f"{keyword} {index}",
            URL=f"https://auctions.yahoo.co.jp/jp/auction/x{run.pk}{index}",
        )
        for index, price in enumerate(prices)
    )
    return run


@pytest.fixture
def user():
    return get_user_model().objects.create_user("activity-owner", password="password")


def test_recent_keywords_are_distinct_newest_first_and_pick_a_free_mode(user):
    _run(user, "カメラ", [1000], days_ago=3)
    _run(user, "レンズ", [2000], search_type=SearchRun.CURRENT, days_ago=2)
    _run(user, "カメラ", [1100], search_type=SearchRun.CURRENT, days_ago=1)
    _run(user, "三脚", [], days_ago=0)  # no items: not an entry point
    _run(user, "時計", [500], days_ago=0, succeeded=False)
    _run(get_user_model().objects.create_user("someone-else"), "他人", [1], days_ago=0)

    entries = recent_keywords(user)

    # カメラ has saved closed data, so it opens without a Yahoo request; レンズ only has current runs.
    assert [(entry.keyword, entry.mode) for entry in entries] == [
        ("カメラ", "history"),
        ("レンズ", "current"),
    ]


def test_market_moves_compare_the_two_newest_closed_runs(user):
    _run(user, "上昇", [1, 1, 1], days_ago=20)  # a third, older run is not compared
    _run(user, "上昇", [9000, 10000, 11000], days_ago=10)
    _run(user, "上昇", [11000, 12000, 13000], days_ago=1)
    _run(user, "下落", [20000], days_ago=5)
    _run(user, "下落", [15000], days_ago=2)
    _run(user, "横ばい", [10000], days_ago=5)
    _run(user, "横ばい", [10300], days_ago=2)
    _run(user, "一回だけ", [5000], days_ago=1)

    moves, comparable = market_moves(user)

    assert comparable == 3
    assert [(move.keyword, move.change_percent, move.direction) for move in moves] == [
        ("下落", -25.0, "down"),
        ("上昇", 20.0, "up"),
    ]
    assert (moves[0].previous_median, moves[0].latest_median) == (20000, 15000)


def test_top_page_links_recent_keywords_and_moves_into_market_search(client, user):
    _run(user, "カメラ", [10000], days_ago=5)
    _run(user, "カメラ", [12000], days_ago=1)
    client.force_login(user)

    html = client.get(reverse("index")).content.decode()

    assert 'id="marketActivityHeading"' in html
    link = f"{reverse('market_search')}?mode=history&amp;keyword=%E3%82%AB%E3%83%A1%E3%83%A9"
    assert html.count(link) == 2
    assert "▲ +20.0%" in html
    assert "10,000円 → 12,000円" in html


def test_top_page_market_activity_is_for_signed_in_users_with_a_hint_when_empty(client, user):
    assert "marketActivityHeading" not in client.get(reverse("index")).content.decode()

    client.force_login(user)
    html = client.get(reverse("index")).content.decode()

    assert "marketActivityHeading" in html
    assert "市場検索を開く" in html
