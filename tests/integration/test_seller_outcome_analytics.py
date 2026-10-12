from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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
        "period": {"from": None, "to": None},
        "expenseBreakdown": [
            {"key": "acquisition", "label": "仕入れ値", "amount": 0},
            {"key": "purchaseShipping", "label": "仕入れ送料", "amount": 0},
            {"key": "fee", "label": "販売手数料", "amount": 0},
            {"key": "shipping", "label": "発送送料", "amount": 0},
            {"key": "packaging", "label": "梱包費", "amount": 0},
            {"key": "other", "label": "その他費用", "amount": 0},
        ],
        "monthly": [],
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


JST = ZoneInfo("Asia/Tokyo")


def sale_at(when, sale_price, *, fee=100, shipping=100, packaging=50, other=0):
    return {
        "salePrice": sale_price,
        "actualFee": fee,
        "actualShippingCost": shipping,
        "actualPackagingCost": packaging,
        "actualOtherCost": other,
        "soldAt": when.isoformat(),
    }


def _seed_period_sales(user):
    """Sales on JST calendar edges: 7/31 23:30, 8/1 00:10, 8/15 and 10/2 (September has none)."""
    inventory = InventoryItem.objects.create(user=user, name="品", category="カメラ")
    times = (
        datetime(2026, 7, 31, 23, 30, tzinfo=JST),
        datetime(2026, 8, 1, 0, 10, tzinfo=JST),
        datetime(2026, 8, 15, 12, 0, tzinfo=JST),
        datetime(2026, 10, 2, 9, 0, tzinfo=JST),
    )
    for index, when in enumerate(times):
        item = listing(user, inventory, 10 + index)
        item.purchase_shipping_cost = 200
        item.save(update_fields=("purchase_shipping_cost",))
        save_sale_record(user, item.pk, sale_at(when, 3000 + index * 1000))


def test_period_filter_uses_inclusive_japan_calendar_days(client):
    user = get_user_model().objects.create_user("outcome-period")
    _seed_period_sales(user)
    client.force_login(user)

    data = client.get(
        reverse("seller_outcomes"), {"from": "2026-08-01", "to": "2026-08-31"}
    ).json()["data"]

    assert data["period"] == {"from": "2026-08-01", "to": "2026-08-31"}
    assert data["summary"]["saleCount"] == 2  # 8/1 00:10 and 8/15, not 7/31 23:30 JST
    assert data["summary"]["totalSales"] == 4000 + 5000
    assert [item["salePrice"] for item in data["lowProfitSales"]] == [4000, 5000]
    assert data["categories"][0]["saleCount"] == 2


def test_expense_breakdown_adds_up_to_total_expenses(client):
    user = get_user_model().objects.create_user("outcome-breakdown")
    _seed_period_sales(user)
    client.force_login(user)

    data = client.get(reverse("seller_outcomes")).json()["data"]

    amounts = {item["key"]: item["amount"] for item in data["expenseBreakdown"]}
    # Each sale: acquisition 1000 + purchase shipping 200, fee 100, shipping 100, packaging 50.
    assert amounts == {
        "acquisition": 4000,
        "purchaseShipping": 800,
        "fee": 400,
        "shipping": 400,
        "packaging": 200,
        "other": 0,
    }
    assert sum(amounts.values()) == data["summary"]["totalExpenses"]


def test_monthly_trend_fills_months_without_sales(client):
    user = get_user_model().objects.create_user("outcome-monthly")
    _seed_period_sales(user)
    client.force_login(user)

    all_time = client.get(reverse("seller_outcomes")).json()["data"]["monthly"]
    assert [(row["month"], row["saleCount"], row["totalSales"]) for row in all_time] == [
        ("2026-07", 1, 3000),
        ("2026-08", 2, 9000),
        ("2026-09", 0, 0),
        ("2026-10", 1, 6000),
    ]
    assert all_time[1]["totalExpenses"] == 2 * 1450
    assert all_time[1]["totalProfit"] == 9000 - 2 * 1450

    ranged = client.get(reverse("seller_outcomes"), {"from": "2026-06-10", "to": "2026-08-20"})
    assert [row["month"] for row in ranged.json()["data"]["monthly"]] == [
        "2026-06",
        "2026-07",
        "2026-08",
    ]


@pytest.mark.parametrize(
    "params",
    [{"from": "2026-13-01"}, {"to": "yesterday"}, {"from": "2026-09-02", "to": "2026-09-01"}],
)
def test_invalid_periods_are_rejected(client, params):
    client.force_login(get_user_model().objects.create_user("outcome-invalid"))

    response = client.get(reverse("seller_outcomes"), params)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_sales_stay_in_outcomes_after_the_listing_is_deleted(client):
    user = get_user_model().objects.create_user("outcome-keep")
    inventory = InventoryItem.objects.create(user=user, name="品", category="カメラ")
    item = listing(user, inventory, 30)
    record = save_sale_record(user, item.pk, payload(5000, 1))
    client.force_login(user)

    response = client.delete(reverse("seller_listing_item", args=[item.pk]))

    assert response.status_code == 204
    record.refresh_from_db()
    assert record.seller_listing_id is None
    assert (record.user_id, record.item_name, record.category) == (user.pk, "販売品30", "カメラ")
    data = client.get(reverse("seller_outcomes")).json()["data"]
    assert data["summary"]["saleCount"] == 1
    assert data["summary"]["totalSales"] == 5000
    assert data["lowProfitSales"][0]["name"] == "販売品30"
    assert data["lowProfitSales"][0]["listingId"] is None
