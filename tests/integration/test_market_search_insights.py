"""Current listings in market search are judged against the owner's saved closed market."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from Main.views import api

pytestmark = pytest.mark.django_db

KEYWORD = "ミラーレス"


def _closed(prices):
    return lambda keyword: [
        {
            "name": f"{keyword} {index}",
            "price": price,
            "startPrice": 1,
            "bidding": 2,
            "time": "",
            "url": f"https://auctions.yahoo.co.jp/jp/auction/c{index}",
        }
        for index, price in enumerate(prices)
    ]


def _current(keyword):
    return [
        {
            "name": "安い出品",
            "currentPrice": 7000,
            "bidding": 1,
            "remainingTime": "1日",
            "url": "https://auctions.yahoo.co.jp/jp/auction/n1",
        },
        {
            "name": "相場の出品",
            "currentPrice": 10000,
            "bidding": 3,
            "remainingTime": "2日",
            "url": "https://auctions.yahoo.co.jp/jp/auction/n2",
        },
    ]


@pytest.fixture
def owner(client):
    user = get_user_model().objects.create_user("insight-owner")
    client.force_login(user)
    return user


def _search_current(client):
    response = client.get(reverse("RealtimeSearch"), {"keyword": KEYWORD})
    assert response.status_code == 200
    return response.json()


def test_current_search_without_saved_closed_market_has_no_comparison(client, owner, monkeypatch):
    monkeypatch.setattr(api, "scrape_current_listings", _current)

    body = _search_current(client)

    assert body["closedMarket"] is None
    assert [item["closedMarketComparison"] for item in body["data"]] == [None, None]


def test_current_listings_compare_with_the_latest_saved_closed_median(client, owner, monkeypatch):
    monkeypatch.setattr(api, "scrape_current_listings", _current)
    monkeypatch.setattr(api, "scrape_data", _closed([1000, 1000, 1000]))
    assert client.get(reverse("perform_search"), {"keyword": KEYWORD}).status_code == 200
    monkeypatch.setattr(api, "scrape_data", _closed([9000, 10000, 11000]))
    assert client.get(reverse("perform_search"), {"keyword": KEYWORD}).status_code == 200

    body = _search_current(client)

    assert body["closedMarket"]["median"] == 10000
    assert body["closedMarket"]["count"] == 3
    cheap, fair = body["data"]
    assert cheap["closedMarketComparison"]["position"] == "below"
    assert cheap["closedMarketComparison"]["differenceRate"] == -30.0
    assert fair["closedMarketComparison"]["position"] == "near"
    # The existing comparison against the current listings themselves is unchanged.
    assert "marketComparison" in cheap


def test_closed_runs_without_items_and_other_owners_are_ignored(client, owner, monkeypatch):
    other = get_user_model().objects.create_user("insight-other")
    client.force_login(other)
    monkeypatch.setattr(api, "scrape_data", _closed([9000, 10000, 11000]))
    assert client.get(reverse("perform_search"), {"keyword": KEYWORD}).status_code == 200

    client.force_login(owner)
    monkeypatch.setattr(api, "scrape_data", _closed([]))
    client.get(reverse("perform_search"), {"keyword": KEYWORD})
    monkeypatch.setattr(api, "scrape_current_listings", _current)

    assert _search_current(client)["closedMarket"] is None
