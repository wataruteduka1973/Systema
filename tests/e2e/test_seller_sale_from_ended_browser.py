"""Ended listings: record a sale directly when there were bids, or mark relist/cancel without."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from Main.models.inventoryitem import InventoryItem
from Main.models.sellerlisting import SaleRecord, SellerListing

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _ended(user, suffix, name, *, bidding, inventory=None):
    return SellerListing.objects.create(
        user=user,
        inventory_item=inventory,
        external_listing_id=f"c12345678{suffix}",
        url=f"https://auctions.yahoo.co.jp/jp/auction/c12345678{suffix}",
        name=name,
        status="ended",
        acquisition_cost=3000,
        purchase_shipping_cost=300,
        shipping_cost_estimate=700,
        packaging_cost_estimate=100,
        other_cost_estimate=0,
        fee_rate=Decimal("0.10"),
        current_price=9000,
        bidding=bidding,
        ends_at=timezone.now() - timedelta(hours=3),
        last_checked_at=timezone.now(),
    )


def test_sale_is_recorded_from_an_ended_listing_and_counted(db_for_e2e, live_server):
    owner = get_user_model().objects.create_user("ended-browser", password="password")
    inventory = InventoryItem.objects.create(
        user=owner, name="カメラ", category="カメラ", status="listed"
    )
    sold = _ended(owner, 1, "入札ありで終了したカメラ", bidding=4, inventory=inventory)
    unsold = _ended(owner, 2, "入札なしで終了したレンズ", bidding=0)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(10_000)
        console_errors = []
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        try:
            page.goto(f"{live_server.url}/accounts/login/")
            page.fill('input[name="username"]', "ended-browser")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')
            page.goto(f"{live_server.url}/taskle/seller-management")

            expect(page.locator("#sellerSummary")).to_contain_text("販売結果待ち")
            card = page.locator("article, .card").filter(has_text="入札ありで終了したカメラ").first
            expect(card).to_contain_text("落札の可能性あり")
            card.get_by_role("button", name="販売結果を入力").click()
            form = page.locator(f"#seller-{sold.pk}-sale form")
            expect(form.locator('[name="salePrice"]')).to_have_value("9000")
            expect(form.locator('[name="actualFee"]')).to_have_value("900")
            expect(form.locator('[name="actualShippingCost"]')).to_have_value("700")
            form.locator('[name="actualShippingCost"]').fill("650")
            form.get_by_role("button", name="販売結果を確定").click()
            expect(page.locator("body")).to_contain_text("販売結果を保存しました")
            card = page.locator("article, .card").filter(has_text="入札ありで終了したカメラ").first
            expect(card.get_by_role("button", name="販売結果を更新")).to_be_visible()
            expect(card.locator("summary", has_text="販売結果を更新")).to_be_visible()

            other = page.locator("article, .card").filter(has_text="入札なしで終了したレンズ").first
            expect(other).to_contain_text("再出品・見送りを記録")
            other.get_by_role("button", name="見送りにする").click()
            expect(page.locator("body")).to_contain_text("「見送り」として記録しました")

            page.goto(f"{live_server.url}/taskle/seller-outcomes")
            expect(page.locator("#outcomeSummary")).to_contain_text("1 件")
            expect(page.locator("#outcomeSummary")).to_contain_text("9,000 円")
            assert console_errors == []
        finally:
            browser.close()

    record = SaleRecord.objects.get(seller_listing=sold)
    # 9000 - (3000 + 300) - (900 + 650 + 100 + 0)
    assert record.confirmed_profit == 4050
    assert record.category == "カメラ"
    sold.refresh_from_db()
    unsold.refresh_from_db()
    inventory.refresh_from_db()
    assert (sold.status, unsold.status, inventory.status) == ("sold", "cancelled", "sold")


def test_registering_a_url_fetches_the_listing_title(db_for_e2e, live_server, monkeypatch):
    from Main.scraping.seller_listing import ListingObservation

    monkeypatch.setattr(
        "Main.services.seller_listings.fetch_listing",
        lambda url: ListingObservation(
            "公開ページの商品名 ミラーレスカメラ",
            15000,
            2,
            timezone.now() + timedelta(days=2),
            "active",
        ),
    )
    get_user_model().objects.create_user("register-browser", password="password")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(10_000)
        try:
            page.goto(f"{live_server.url}/accounts/login/")
            page.fill('input[name="username"]', "register-browser")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')
            page.goto(f"{live_server.url}/taskle/seller-management")
            page.locator("summary", has_text="出品URLを登録").click()
            page.fill('input[name="url"]', "https://auctions.yahoo.co.jp/jp/auction/d123456789")
            page.get_by_role("button", name="出品を登録").click()
            expect(page.locator("#sellerMessage")).to_contain_text(
                "商品名「公開ページの商品名 ミラーレスカメラ」"
            )
            expect(page.locator("#sellerList")).to_contain_text(
                "公開ページの商品名 ミラーレスカメラ"
            )
            expect(page.locator("#sellerList")).to_contain_text("15,000円")
        finally:
            browser.close()
    assert SellerListing.objects.get().name == "公開ページの商品名 ミラーレスカメラ"
