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
