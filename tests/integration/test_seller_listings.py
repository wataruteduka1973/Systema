from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from Main.models.inventoryitem import InventoryItem
from Main.models.sellerlisting import SellerListingSnapshot
from Main.scraping.seller_listing import ListingObservation, ListingParseError
from Main.services.exceptions import ExternalServiceError
from Main.services.seller_listings import create_listing, update_listing

pytestmark = pytest.mark.django_db
URL = "https://auctions.yahoo.co.jp/jp/auction/x1234567890"


@pytest.fixture
def owner(client):
    cache.clear()
    user = get_user_model().objects.create_user("seller-owner")
    client.force_login(user)
    return user


@pytest.fixture
def listing(owner):
    return create_listing(owner, {"url": URL, "acquisitionCost": 8000, "note": "ユーザーのメモ"})


@pytest.fixture
def fetch(monkeypatch):
    mock = Mock(
        return_value=ListingObservation(
            "公開商品名", 12000, 3, timezone.now() + timedelta(days=1), "active"
        )
    )
    monkeypatch.setattr("Main.services.seller_listings.fetch_listing", mock)
    return mock


def test_create_copy_inventory_crud_pagination_and_no_network(client, owner, fetch):
    inventory = InventoryItem.objects.create(user=owner, name="カメラ", acquisition_cost=8000)
    response = client.post(
        reverse("seller_listings"),
        {"url": URL + "?tracking=1", "inventoryItemId": inventory.pk},
        content_type="application/json",
    )
    assert response.status_code == 201
    item = response.json()["data"]
    assert item["acquisitionCost"] == 8000
    assert item["url"] == URL
    assert item["profit"] is None and item["currentPrice"] is None
    fetch.assert_not_called()
    detail = reverse("seller_listing_item", args=[item["id"]])
    changed = client.patch(
        detail,
        {
            "predictedSalePrice": 12000,
            "feeRate": "0.10",
            "shippingCostEstimate": 500,
            "status": "relist",
        },
        content_type="application/json",
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["profit"]["estimatedProfit"] == 2300
    inventory.acquisition_cost = 9999
    inventory.save()
    assert client.get(detail).json()["data"]["acquisitionCost"] == 8000
    data = client.get(reverse("seller_listings"), {"status": "relist", "pageSize": 1}).json()
    assert data["meta"] == {"page": 1, "pageSize": 1, "total": 1}
    assert client.get(reverse("seller_listings"), {"pageSize": 101}).status_code == 400
    assert client.get(reverse("seller_listings"), {"status": "invalid"}).status_code == 400
    assert (
        client.post(
            reverse("seller_listings"), {"url": URL}, content_type="application/json"
        ).status_code
        == 409
    )
    inventory.delete()
    assert client.get(detail).json()["data"]["inventoryItemId"] is None
    assert client.delete(detail).status_code == 204


def test_cross_user_all_endpoints_and_inventory_reference(client, owner, listing, fetch):
    other = get_user_model().objects.create_user("seller-other")
    inventory = InventoryItem.objects.create(user=owner, name="非公開")
    client.force_login(other)
    detail = reverse("seller_listing_item", args=[listing.pk])
    assert client.get(detail).status_code == 404
    assert client.patch(detail, {}, content_type="application/json").status_code == 404
    assert client.delete(detail).status_code == 404
    assert (
        client.post(
            reverse("seller_listing_refresh", args=[listing.pk]),
            {},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.get(reverse("seller_listing_snapshots", args=[listing.pk])).status_code == 404
    assert client.get(reverse("seller_listings")).json()["data"] == []
    assert (
        client.post(
            reverse("seller_listings"),
            {"url": URL, "inventoryItemId": inventory.pk},
            content_type="application/json",
        ).status_code
        == 404
    )
    fetch.assert_not_called()
    client.logout()
    for url in [
        reverse("seller_listings"),
        detail,
        reverse("seller_listing_snapshots", args=[listing.pk]),
    ]:
        assert client.get(url).status_code == 401
    assert client.post(reverse("seller_listing_refresh", args=[listing.pk])).status_code == 401


def test_csrf_on_all_mutations(owner, listing):
    client = Client(enforce_csrf_checks=True)
    client.force_login(owner)
    assert (
        client.post(reverse("seller_listings"), {}, content_type="application/json").status_code
        == 403
    )
    detail = reverse("seller_listing_item", args=[listing.pk])
    assert client.patch(detail, {}, content_type="application/json").status_code == 403
    assert client.delete(detail).status_code == 403
    assert client.post(reverse("seller_listing_refresh", args=[listing.pk])).status_code == 403


def test_refresh_atomic_history_and_manual_fields_preserved(client, owner, listing, fetch):
    update_listing(owner, listing.pk, {"status": "relist", "feeRate": "0.10", "targetProfit": 3000})
    url = reverse("seller_listing_refresh", args=[listing.pk])
    first = client.post(url, {}, content_type="application/json")
    assert first.status_code == 200
    assert first.json()["data"]["status"] == "relist"
    assert first.json()["data"]["note"] == "ユーザーのメモ"
    snapshot = SellerListingSnapshot.objects.get(seller_listing=listing)
    assert snapshot.estimated_profit == 2800
    assert snapshot.calculation_inputs["acquisition_cost"] == 8000
    update_listing(owner, listing.pk, {"acquisitionCost": 15000})
    assert client.post(url, {}, content_type="application/json").status_code == 200
    history = client.get(reverse("seller_listing_snapshots", args=[listing.pk])).json()
    assert history["meta"]["total"] == 2
    assert history["data"][0]["estimatedProfit"] == -4200
    snapshot.refresh_from_db()
    assert snapshot.estimated_profit == 2800
    assert client.delete(reverse("seller_listing_item", args=[listing.pk])).status_code == 204
    assert not SellerListingSnapshot.objects.exists()


@pytest.mark.parametrize(
    "error,code",
    [
        (ExternalServiceError("secret response"), "external_service_unavailable"),
        (ListingParseError("解析失敗"), "listing_parse_failed"),
    ],
)
def test_failed_refresh_never_changes_data(client, listing, fetch, error, code):
    fetch.side_effect = error
    before = listing.updated_at
    response = client.post(
        reverse("seller_listing_refresh", args=[listing.pk]), {}, content_type="application/json"
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == code
    assert b"secret response" not in response.content
    listing.refresh_from_db()
    assert listing.updated_at == before and listing.last_checked_at is None
    assert not listing.snapshots.exists()


def test_refresh_rate_limit_separate_from_search(client, listing, fetch, settings):
    settings.SELLER_REFRESH_RATE_LIMIT = 1
    url = reverse("seller_listing_refresh", args=[listing.pk])
    assert client.post(url, {}, content_type="application/json").status_code == 200
    response = client.post(url, {}, content_type="application/json")
    assert response.status_code == 429 and response["Retry-After"] == "60"
    assert fetch.call_count == 1


def test_concurrent_edit_or_delete_discards_observation(client, owner, listing, fetch):
    observation = fetch.return_value

    def edit_during_fetch(url):
        update_listing(owner, listing.pk, {"note": "別操作で更新"})
        return observation

    fetch.side_effect = edit_during_fetch
    assert (
        client.post(
            reverse("seller_listing_refresh", args=[listing.pk]),
            {},
            content_type="application/json",
        ).status_code
        == 409
    )
    assert not listing.snapshots.exists()

    def delete_during_fetch(url):
        listing.delete()
        return observation

    fetch.side_effect = delete_during_fetch
    assert (
        client.post(
            reverse("seller_listing_refresh", args=[listing.pk]),
            {},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert not SellerListingSnapshot.objects.exists()


@pytest.mark.parametrize(
    "payload",
    [
        {"feeRate": "NaN"},
        {"feeRate": "0.123456"},
        {"feeRate": "1.1"},
        {"acquisitionCost": -1},
        {"shippingCostEstimate": True},
        {"targetProfit": 10**30},
        {"url": "https://evil.test/"},
        {"cookie": "secret"},
        {"estimatedProfit": 100},
        {"status": []},
        {"name": ""},
        {"predictedSalePrice": -1},
    ],
)
def test_invalid_update_is_rejected(client, listing, payload):
    response = client.patch(
        reverse("seller_listing_item", args=[listing.pk]), payload, content_type="application/json"
    )
    assert response.status_code == 400


def test_snapshot_failure_rolls_back_observation(owner, listing, fetch, monkeypatch):
    from Main.services.seller_listings import refresh_listing

    monkeypatch.setattr(
        SellerListingSnapshot.objects, "create", Mock(side_effect=RuntimeError("DB failure"))
    )
    with pytest.raises(RuntimeError):
        refresh_listing(owner, listing.pk)
    listing.refresh_from_db()
    assert listing.last_checked_at is None


def test_closed_observation_is_not_confirmed_sale(client, listing, fetch):
    fetch.return_value = ListingObservation(
        "終了", 13000, 4, timezone.now() - timedelta(days=1), "ended"
    )
    response = client.post(
        reverse("seller_listing_refresh", args=[listing.pk]), {}, content_type="application/json"
    )
    assert response.json()["data"]["status"] == "ended"
    assert response.json()["data"]["remainingSeconds"] == 0


@pytest.mark.parametrize("inventory_id", [10**100, True, "１２３", -1, "1.0"])
def test_invalid_inventory_id_is_client_error(client, owner, inventory_id):
    response = client.post(
        reverse("seller_listings"),
        {"url": URL, "inventoryItemId": inventory_id},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_credential_payload_rejected_without_external_request(client, listing, fetch):
    response = client.post(
        reverse("seller_listing_refresh", args=[listing.pk]),
        {"cookie": "private"},
        content_type="application/json",
    )
    assert response.status_code == 400
    fetch.assert_not_called()


def test_seller_page_has_registration_and_script(client, owner):
    response = client.get(reverse("seller_management"))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'id="sellerCreateForm"' in content
    assert "JS/SellerListings.js" in content
