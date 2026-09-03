import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from Main.models.inventoryitem import InventoryItem
from Main.models.watchitem import WatchItem

pytestmark = pytest.mark.django_db


def test_inventory_page_and_api_require_login(client):
    assert client.get(reverse("seller_management")).status_code == 302
    assert client.get(reverse("inventory_items")).status_code == 401
    assert (
        client.post(
            reverse("inventory_items"), data="{}", content_type="application/json"
        ).status_code
        == 401
    )


def test_inventory_mutations_require_csrf():
    user = get_user_model().objects.create_user("inventory-csrf", password="password")
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)

    response = csrf_client.post(
        reverse("inventory_items"),
        data='{"name": "CSRFなしの商品", "acquisitionCost": 1000}',
        content_type="application/json",
    )

    assert response.status_code == 403


def test_manual_inventory_crud_filter_and_owner_isolation(client):
    owner = get_user_model().objects.create_user("inventory-owner", password="password")
    other = get_user_model().objects.create_user("inventory-other", password="password")
    client.force_login(owner)
    created_response = client.post(
        reverse("inventory_items"),
        json.dumps(
            {
                "name": "中古カメラ",
                "condition": "used",
                "category": "カメラ",
                "acquisitionCost": 12000,
                "status": "acquired",
                "note": "動作確認済み",
            }
        ),
        content_type="application/json",
    )
    item_id = created_response.json()["item"]["id"]

    assert created_response.status_code == 201
    assert (
        client.get(reverse("inventory_items"), {"status": "acquired"}).json()["items"][0]["name"]
        == "中古カメラ"
    )

    detail_url = reverse("inventory_item", args=(item_id,))
    updated = client.patch(
        detail_url,
        json.dumps({"status": "preparing", "acquisitionCost": 12500}),
        content_type="application/json",
    )
    assert updated.status_code == 200
    assert updated.json()["item"]["status"] == "preparing"

    client.force_login(other)
    assert client.get(detail_url).status_code == 404
    assert client.patch(detail_url, data="{}", content_type="application/json").status_code == 404
    assert client.delete(detail_url).status_code == 404

    client.force_login(owner)
    assert client.delete(detail_url).status_code == 200
    assert not InventoryItem.objects.filter(pk=item_id).exists()


def test_watch_conversion_is_owner_limited_atomic_and_idempotent(client):
    owner = get_user_model().objects.create_user("conversion-owner", password="password")
    other = get_user_model().objects.create_user("conversion-other", password="password")
    watch = WatchItem.objects.create(
        user=owner,
        name="購入候補",
        url="https://auctions.yahoo.co.jp/jp/auction/inventory-source",
        current_price=8000,
        added_price=9000,
        condition="used",
        category="カメラ",
        note="仕入候補",
    )
    url = reverse("convert_watch_item_to_inventory", args=(watch.pk,))
    client.force_login(other)
    assert (
        client.post(
            url, data='{"acquisitionCost": 7500}', content_type="application/json"
        ).status_code
        == 404
    )

    client.force_login(owner)
    first = client.post(url, data='{"acquisitionCost": 7500}', content_type="application/json")
    second = client.post(url, data='{"acquisitionCost": 7000}', content_type="application/json")

    assert first.status_code == 201
    assert first.json()["created"] is True
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert InventoryItem.objects.filter(user=owner, source_watch_item=watch).count() == 1
    inventory = InventoryItem.objects.get(source_watch_item=watch)
    assert inventory.acquisition_cost == 7500
    assert inventory.status == "acquired"
    watch.refresh_from_db()
    assert watch.lifecycle_status == "purchased"


def test_inventory_profit_simulation_uses_server_side_acquisition_cost(client):
    user = get_user_model().objects.create_user("profit-owner", password="password")
    item = InventoryItem.objects.create(
        user=user,
        name="商品",
        acquisition_cost=12000,
        status="acquired",
    )
    client.force_login(user)

    response = client.post(
        reverse("inventory_profit_simulation", args=(item.pk,)),
        json.dumps(
            {
                "salePrice": 22000,
                "acquisitionCost": 1,
                "shippingCost": 1000,
                "packagingCost": 200,
                "feeRate": "0.10",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["data"]["totalCost"] == 15400
    assert response.json()["data"]["estimatedProfit"] == 6600


def test_inventory_page_contains_management_surfaces(client):
    user = get_user_model().objects.create_user("inventory-page", password="password")
    client.force_login(user)

    content = client.get(reverse("seller_management")).content.decode("utf-8")

    assert "購入候補から在庫へ" in content
    assert "在庫を手動登録" in content
    assert "見込み利益を計算" not in content  # Cards are rendered from API data.
    assert "InventoryManagement.js" in content
    assert "出品・在庫管理" in client.get(reverse("index")).content.decode("utf-8")
