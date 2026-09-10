from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from Main.models.inventoryitem import InventoryItem
from Main.models.sellerlisting import SaleRecord, SellerListing
from Main.services.seller_listings import save_sale_record

pytestmark = pytest.mark.django_db


def listing(user, inventory, suffix):
    return SellerListing.objects.create(
        user=user,
        inventory_item=inventory,
        external_listing_id=f"a1234567{suffix}",
        url=f"https://auctions.yahoo.co.jp/jp/auction/a1234567{suffix}",
        name=f"販売品{suffix}",
        acquisition_cost=1000,
        status="sold",
    )


def payload(sale_price, days):
    return {
        "salePrice": sale_price,
        "actualFee": 100,
        "actualShippingCost": 100,
        "actualPackagingCost": 0,
        "actualOtherCost": 0,
        "soldAt": (timezone.now() - timedelta(days=days)).isoformat(),
    }


def test_sale_outcomes_aggregate_only_the_owners_confirmed_sales(client):
    owner = get_user_model().objects.create_user("outcome-owner")
    other = get_user_model().objects.create_user("outcome-other")
    camera = InventoryItem.objects.create(user=owner, name="カメラ", category="カメラ")
    game = InventoryItem.objects.create(user=owner, name="ゲーム", category="ゲーム")
    other_inventory = InventoryItem.objects.create(user=other, name="他人", category="他人")
    save_sale_record(owner, listing(owner, camera, 1).pk, payload(2000, 2))
    save_sale_record(owner, listing(owner, game, 2).pk, payload(800, 1))
    save_sale_record(other, listing(other, other_inventory, 3).pk, payload(10000, 1))
    client.force_login(owner)

    response = client.get(reverse("seller_outcomes"))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"] == {
        "saleCount": 2,
        "totalSales": 2800,
        "totalExpenses": 2400,
        "totalProfit": 400,
        "profitableCount": 1,
        "lossCount": 1,
    }
    assert [(item["category"], item["totalProfit"]) for item in data["categories"]] == [
        ("カメラ", 800),
        ("ゲーム", -400),
    ]
    assert [item["confirmedProfit"] for item in data["lowProfitSales"]] == [-400, 800]


def test_sale_outcomes_are_empty_for_no_confirmed_sales_and_require_login(client):
    url = reverse("seller_outcomes")
    assert client.get(url).status_code == 401
    user = get_user_model().objects.create_user("outcome-empty")
    client.force_login(user)
    data = client.get(url).json()["data"]
    assert data == {
        "summary": {
            "saleCount": 0,
            "totalSales": 0,
            "totalExpenses": 0,
            "totalProfit": 0,
            "profitableCount": 0,
            "lossCount": 0,
        },
        "categories": [],
        "lowProfitSales": [],
    }


def test_sale_record_copies_category_at_confirmation_even_if_inventory_changes():
    user = get_user_model().objects.create_user("outcome-category")
    inventory = InventoryItem.objects.create(user=user, name="品", category="初期カテゴリ")
    record = save_sale_record(user, listing(user, inventory, 4).pk, payload(2000, 1))
    inventory.category = "変更後"
    inventory.save(update_fields=("category",))
    save_sale_record(user, record.seller_listing_id, payload(2200, 0))
    record.refresh_from_db()
    assert record.category == "初期カテゴリ"
    assert SaleRecord.objects.get(pk=record.pk).category == "初期カテゴリ"
