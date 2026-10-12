from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from Main.models.inventoryitem import InventoryItem
from Main.models.sellerlisting import SaleRecord, SellerListing

pytestmark = pytest.mark.django_db


def make_listing(user, inventory=None):
    return SellerListing.objects.create(
        user=user,
        inventory_item=inventory,
        external_listing_id="a123456789",
        url="https://auctions.yahoo.co.jp/jp/auction/a123456789",
        name="販売結果テスト",
        status="sold",
        acquisition_cost=8000,
        purchase_shipping_cost=500,
        predicted_sale_price=12000,
    )


def sale_payload(**changes):
    payload = {
        "salePrice": 10000,
        "actualFee": 1000,
        "actualShippingCost": 700,
        "actualPackagingCost": 100,
        "actualOtherCost": 200,
        "soldAt": (timezone.now() - timedelta(days=1)).isoformat(),
    }
    payload.update(changes)
    return payload


def test_sale_result_is_owner_scoped_recalculated_and_updates_inventory(client):
    owner = get_user_model().objects.create_user("sale-owner")
    inventory = InventoryItem.objects.create(user=owner, name="在庫", status="listed")
    listing = make_listing(owner, inventory)
    client.force_login(owner)
    url = reverse("seller_listing_sale", args=[listing.pk])

    response = client.put(
        url, sale_payload(confirmedProfit=999999), content_type="application/json"
    )
    assert response.status_code == 400
    response = client.put(url, sale_payload(), content_type="application/json")
    assert response.status_code == 200
    assert response.json()["data"]["confirmedProfit"] == -500
    assert SaleRecord.objects.get(seller_listing=listing).confirmed_profit == -500
    inventory.refresh_from_db()
    assert inventory.status == "sold"

    response = client.put(url, sale_payload(salePrice=15000), content_type="application/json")
    assert response.status_code == 200
    assert response.json()["data"]["confirmedProfit"] == 4500
    assert SaleRecord.objects.filter(seller_listing=listing).count() == 1
    detail = client.get(reverse("seller_listing_item", args=[listing.pk])).json()["data"]
    assert detail["saleRecord"]["confirmedProfit"] == 4500
    assert detail["actionStatus"]["status"] == "sold"


def test_sale_result_auth_ownership_csrf_and_validation(client):
    owner = get_user_model().objects.create_user("sale-owner")
    other = get_user_model().objects.create_user("sale-other")
    listing = make_listing(owner)
    url = reverse("seller_listing_sale", args=[listing.pk])
    assert client.put(url, sale_payload(), content_type="application/json").status_code == 401
    client.force_login(other)
    assert client.put(url, sale_payload(), content_type="application/json").status_code == 404
    client.force_login(owner)
    for payload in (
        sale_payload(salePrice=-1),
        sale_payload(actualFee=True),
        sale_payload(soldAt="2026-09-09T10:00:00"),
        {key: value for key, value in sale_payload().items() if key != "actualFee"},
    ):
        assert client.put(url, payload, content_type="application/json").status_code == 400
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(owner)
    assert csrf_client.put(url, sale_payload(), content_type="application/json").status_code == 403


def test_summary_counts_sale_result_for_owner_only(client):
    owner = get_user_model().objects.create_user("summary-owner")
    other = get_user_model().objects.create_user("summary-other")
    missing = make_listing(owner)
    make_listing(other)
    client.force_login(owner)
    result = client.get(reverse("seller_listings"), {"action": "sale_result_missing"}).json()
    assert result["meta"]["total"] == 1
    assert result["data"][0]["id"] == missing.pk
    assert result["summary"]["total"] == 1
    assert result["summary"]["saleResultMissing"] == 1


def _ended_listing(user, suffix, *, bidding, status="ended"):
    return SellerListing.objects.create(
        user=user,
        external_listing_id=f"b12345678{suffix}",
        url=f"https://auctions.yahoo.co.jp/jp/auction/b12345678{suffix}",
        name=f"終了した出品{suffix}",
        status=status,
        acquisition_cost=3000,
        current_price=9000,
        bidding=bidding,
        ends_at=timezone.now() - timedelta(hours=2),
        last_checked_at=timezone.now(),
    )


def test_ended_listing_with_bids_awaits_a_sale_and_can_be_recorded_directly(client):
    owner = get_user_model().objects.create_user("ended-owner")
    with_bids = _ended_listing(owner, 1, bidding=3)
    without_bids = _ended_listing(owner, 2, bidding=0)
    marked_sold = make_listing(owner)
    client.force_login(owner)
    url = reverse("seller_listings")

    result = client.get(url, {"action": "awaiting_sale"}).json()
    assert {item["id"] for item in result["data"]} == {with_bids.pk, marked_sold.pk}
    assert result["summary"]["saleResultMissing"] == 2
    statuses = {
        item["id"]: item["actionStatus"]["status"] for item in client.get(url).json()["data"]
    }
    assert statuses == {
        with_bids.pk: "sale_likely",
        without_bids.pk: "status_check",
        marked_sold.pk: "sale_result_missing",
    }

    # Ended is not sold: recording the sale is what marks it sold and counts it.
    response = client.put(
        reverse("seller_listing_sale", args=[with_bids.pk]),
        sale_payload(salePrice=9000),
        content_type="application/json",
    )
    assert response.status_code == 200
    with_bids.refresh_from_db()
    assert with_bids.status == "sold"
    outcomes = client.get(reverse("seller_outcomes")).json()["data"]["summary"]
    assert outcomes["saleCount"] == 1
    assert outcomes["totalSales"] == 9000


def test_ended_listing_without_bids_can_be_marked_relist(client):
    owner = get_user_model().objects.create_user("relist-owner")
    listing = _ended_listing(owner, 3, bidding=0)
    client.force_login(owner)

    response = client.patch(
        reverse("seller_listing_item", args=[listing.pk]),
        {"status": "relist"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["data"]["actionStatus"]["status"] == "relist"
    assert client.get(reverse("seller_listings"), {"action": "bogus"}).status_code == 400
