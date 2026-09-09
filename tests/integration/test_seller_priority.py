from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from Main.models.sellerlisting import SellerListing, SellerListingSnapshot
from Main.services.seller_listings import listing_page

pytestmark = pytest.mark.django_db


def make_listing(user, number, **changes):
    data = dict(
        user=user,
        external_listing_id=str(number),
        url=f"https://auctions.yahoo.co.jp/jp/auction/a{number:09d}",
        name=f"商品{number}",
        status="active",
        predicted_sale_price=10000,
        fee_rate=Decimal("0.1"),
        acquisition_cost=1000,
        bidding=1,
        last_checked_at=timezone.now(),
        ends_at=timezone.now() + timedelta(days=3),
    )
    data.update(changes)
    return SellerListing.objects.create(**data)


def test_priority_before_pagination_filter_count_owner_and_default(
    client, django_assert_num_queries
):
    owner = get_user_model().objects.create_user("priority-owner")
    other = get_user_model().objects.create_user("priority-other")
    now = timezone.now()
    urgent = make_listing(owner, 1, ends_at=now + timedelta(hours=2), bidding=0)
    loss = make_listing(owner, 2, acquisition_cost=20000)
    for number in range(3, 26):
        make_listing(owner, number)
    make_listing(other, 100, acquisition_cost=30000)
    with (
        patch("Main.services.seller_listings.timezone.now", return_value=now),
        django_assert_num_queries(2),
    ):
        data = listing_page(owner, status="", action="", sort="priority", page=1, size=1)
    assert data["data"][0]["id"] == urgent.pk
    assert data["meta"] == {"page": 1, "pageSize": 1, "total": 25}
    assert data["summary"]["total"] == 25
    assert data["summary"]["urgent"] == 1
    assert data["summary"]["actionCounts"]["loss_risk"] == 1
    client.force_login(owner)
    url = reverse("seller_listings")
    second = client.get(url, {"sort": "priority", "page": 2, "pageSize": 1}).json()
    assert second["data"][0]["id"] == loss.pk
    filtered = client.get(url, {"action": "loss_risk", "status": "active"}).json()
    assert filtered["meta"]["total"] == 1 and filtered["data"][0]["id"] == loss.pk
    assert client.get(url, {"action": "loss_risk", "status": "sold"}).json()["meta"]["total"] == 0
    assert client.get(url).json()["data"][0]["name"] == "商品25"
    assert client.get(url, {"page": 100}).json()["data"] == []
    for query in (
        {"sort": "bogus"},
        {"action": "bogus"},
        {"status": "bogus"},
        {"page": 0},
        {"pageSize": 101},
    ):
        assert client.get(url, query).status_code == 400
    client.logout()
    assert client.get(url, {"sort": "priority"}).status_code == 401


def test_stall_requires_time_spaced_observation_and_uses_same_detail_rule(client):
    owner = get_user_model().objects.create_user("stall-owner")
    item = make_listing(owner, 1)

    def snapshot(hours, bids):
        SellerListingSnapshot.objects.create(
            seller_listing=item,
            current_price=10000,
            bidding=bids,
            remaining_seconds=100000,
            market_median=0,
            predicted_sale_price=10000,
            estimated_fee=1000,
            estimated_profit=8000,
            calculation_inputs={},
            observed_status="active",
            observed_at=item.last_checked_at - timedelta(hours=hours),
        )

    snapshot(1, 1)
    client.force_login(owner)
    url = reverse("seller_listings")
    assert client.get(url, {"action": "bid_stalled"}).json()["meta"]["total"] == 0
    snapshot(24, 1)
    result = client.get(url, {"action": "bid_stalled"}).json()
    assert result["meta"]["total"] == 1
    detail = client.get(reverse("seller_listing_item", args=[item.pk])).json()
    assert detail["data"]["actionStatus"] == result["data"][0]["actionStatus"]
    item.last_checked_at -= timedelta(days=1)
    item.save()
    assert client.get(url, {"action": "bid_stalled"}).json()["meta"]["total"] == 0


def test_tied_priorities_have_stable_page_order():
    owner = get_user_model().objects.create_user("tie-owner")
    first = make_listing(owner, 1)
    second = make_listing(owner, 2)
    now = timezone.now()
    SellerListing.objects.filter(user=owner).update(ends_at=None, updated_at=now)

    def page(number):
        return listing_page(owner, status="", action="", sort="priority", page=number, size=1)

    assert page(1)["data"][0]["id"] == second.pk
    assert page(2)["data"][0]["id"] == first.pk
