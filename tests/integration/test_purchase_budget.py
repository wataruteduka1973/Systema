import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from Main.models.purchasebudget import PurchaseDecision
from Main.models.searchrun import SearchRun
from Main.models.watchitem import WatchItem
from Main.scraping.seller_listing import ListingObservation
from Main.services.inventory import convert_watch_to_inventory, simulate_inventory_profit
from Main.services.purchase_budget import save_cost_settings, save_decision
from Main.services.seller_listings import create_listing, serialize_listing, update_listing, refresh_listing

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    return get_user_model().objects.create_user("budget-owner")


@pytest.fixture
def watch(owner):
    return WatchItem.objects.create(
        user=owner,
        name="camera",
        url="https://auctions.yahoo.co.jp/jp/auction/a123456789",
        current_price=4500,
    )


def assumptions(**changes):
    return {
        "salePrice": 10000,
        "feeRate": "0.10",
        "purchaseShipping": 700,
        "shippingCost": 800,
        "packagingCost": 200,
        "otherCost": 300,
        "targetProfit": 2000,
        **changes,
    }


def payload(**changes):
    return {"assumptions": assumptions(**changes), "evidenceNote": "中古の同型を参考に手入力"}


def test_auth_owner_csrf_and_method_boundaries(client, owner, watch):
    url = reverse("purchase_budget", args=[watch.pk])
    settings_url = reverse("purchase_cost_settings")
    assert client.get(url).status_code == 401
    assert client.get(settings_url).status_code == 401
    client.force_login(owner)
    assert client.get(settings_url).json()["data"]["shippingCost"] is None
    assert client.delete(settings_url).status_code == 405
    assert client.post(url, data="[]", content_type="application/json").status_code == 400
    other = get_user_model().objects.create_user("budget-other")
    client.force_login(other)
    assert client.get(url).status_code == 404
    assert (
        client.post(url, data=json.dumps(payload()), content_type="application/json").status_code
        == 404
    )
    csrf = Client(enforce_csrf_checks=True)
    csrf.force_login(owner)
    assert csrf.put(settings_url, data="{}", content_type="application/json").status_code == 403
    assert csrf.post(url, data="{}", content_type="application/json").status_code == 403


def test_defaults_overrides_idempotency_and_frozen_transfer(owner, watch):
    defaults = assumptions()
    defaults.pop("salePrice")
    save_cost_settings(owner, defaults)
    data = {"assumptions": {"salePrice": 10000, "shippingCost": 1000}, "evidenceNote": "手入力"}
    first = save_decision(owner, watch.pk, data)
    assert first["result"]["purchaseLimit"] == 4800
    assert save_decision(owner, watch.pk, data) == first
    assert PurchaseDecision.objects.count() == 1
    save_cost_settings(owner, {"shippingCost": 9999})
    assert save_decision(owner, watch.pk, data) == first
    stock, created = convert_watch_to_inventory(owner, watch.pk, {"acquisitionCost": 4700})
    assert created and stock.purchase_decision == first
    again, created = convert_watch_to_inventory(owner, watch.pk, {"acquisitionCost": 100})
    assert not created and again.pk == stock.pk and again.acquisition_cost == 4700
    with pytest.raises(ValueError, match="在庫化"):
        save_decision(owner, watch.pk, payload())
    listing = create_listing(
        owner,
        {"inventoryItemId": stock.pk, "url": "https://auctions.yahoo.co.jp/jp/auction/b123456789"},
    )
    assert listing.purchase_decision == first
    assert listing.purchase_shipping_cost == 700
    assert listing.shipping_cost_estimate == 1000
    assert serialize_listing(listing)["profit"]["estimatedProfit"] == 2100
    assert simulate_inventory_profit(stock, {})["estimatedProfit"] == 2100
    update_listing(owner, listing.pk, {"shippingCostEstimate": 0})
    stock.acquisition_cost = 1
    stock.save()
    listing.refresh_from_db()
    assert listing.acquisition_cost == 4700 and listing.purchase_decision == first


def test_unknown_cost_survives_inventory_listing_and_explicit_zero_resolves(owner, watch):
    decision = save_decision(owner, watch.pk, payload(shippingCost=None))
    assert decision["result"]["status"] == "insufficient"
    stock, _ = convert_watch_to_inventory(owner, watch.pk, {})
    assert simulate_inventory_profit(stock, {})["estimatedProfit"] is None
    listing = create_listing(
        owner,
        {"inventoryItemId": stock.pk, "url": "https://auctions.yahoo.co.jp/jp/auction/b123456789"},
    )
    assert serialize_listing(listing)["profit"] is None
    assert listing.missing_cost_fields == ["shippingCostEstimate"]
    listing = update_listing(owner, listing.pk, {"note": "changed"})
    assert serialize_listing(listing)["profit"] is None
    listing = update_listing(owner, listing.pk, {"shippingCostEstimate": 0})
    assert serialize_listing(listing)["profit"]["estimatedProfit"] == 3300
    assert listing.purchase_decision["assumptions"]["shippingCost"] is None


def test_evidence_is_owner_scoped_and_copied_before_retention(client, owner, watch):
    run = SearchRun.objects.create(user=owner, keyword="camera", search_type="closed", item_count=2)
    for price in (10000, 10001):
        run.items.create(
            Name="camera",
            URL="https://auctions.yahoo.co.jp/jp/auction/a123456789",
            EndPrice=price,
            StartPrice=0,
            SearchWord="camera",
            SearchDay="2026-09-05",
            Bidding="1",
        )
    request = {"assumptions": assumptions(), "evidenceRunId": run.pk}
    result = save_decision(owner, watch.pk, request)
    assert result["assumptions"]["salePrice"] == 10001
    assert result["evidence"]["count"] == 2
    assert result["evidence"]["salePeriod"] is None
    other = get_user_model().objects.create_user("evidence-other")
    other_watch = WatchItem.objects.create(
        user=other, name="other", url="https://auctions.yahoo.co.jp/jp/auction/a987654321"
    )
    client.force_login(other)
    assert (
        client.post(
            reverse("purchase_budget", args=[other_watch.pk]),
            data=json.dumps(request),
            content_type="application/json",
        ).status_code
        == 404
    )
    assert client.get(reverse("purchase_cost_settings")).json()["evidenceRuns"] == []
    run.delete()
    assert PurchaseDecision.objects.get(watch_item=watch).snapshot == result


def test_api_settings_and_null_override(client, owner, watch):
    client.force_login(owner)
    settings_url = reverse("purchase_cost_settings")
    values = assumptions()
    values.pop("salePrice")
    assert (
        client.put(
            settings_url, data=json.dumps(values), content_type="application/json"
        ).status_code
        == 200
    )
    result = client.post(
        reverse("purchase_budget", args=[watch.pk]),
        data=json.dumps(
            {"assumptions": {"salePrice": 10000, "shippingCost": None}, "evidenceNote": "手入力"}
        ),
        content_type="application/json",
    )
    assert result.status_code == 200
    assert result.json()["data"]["result"]["missing"] == ["shippingCost"]


def test_unknown_observation_stays_null_after_later_cost_edit(owner, watch, monkeypatch):
    save_decision(owner, watch.pk, payload(shippingCost=None))
    stock, _ = convert_watch_to_inventory(owner, watch.pk, {})
    listing = create_listing(owner, {"inventoryItemId": stock.pk, "url": "https://auctions.yahoo.co.jp/jp/auction/b123456789"})
    monkeypatch.setattr("Main.services.seller_listings.fetch_listing", lambda url: ListingObservation("camera", 10000, 1, timezone.now() + timedelta(days=1), "active"))
    refreshed = refresh_listing(owner, listing.pk)
    snapshot = refreshed.snapshots.get()
    assert snapshot.estimated_profit is None and snapshot.estimated_fee is None
    assert snapshot.calculation_inputs["missing_cost_fields"] == ["shippingCostEstimate"]
    update_listing(owner, listing.pk, {"shippingCostEstimate": 0})
    snapshot.refresh_from_db()
    assert snapshot.estimated_profit is None


def test_changed_decision_appends_and_reapply_defaults_preserves_sale(owner, watch):
    first = save_decision(owner, watch.pk, payload())
    save_cost_settings(owner, {"shippingCost": 0})
    changed = save_decision(owner, watch.pk, {"useDefaults": True})
    assert changed["assumptions"]["salePrice"] == 10000
    assert changed["assumptions"]["shippingCost"] == 0
    assert changed["assumptions"]["purchaseShipping"] is None
    assert PurchaseDecision.objects.count() == 2
    assert PurchaseDecision.objects.order_by("pk").first().snapshot == first
