"""Browser workflow for the owner-scoped confirmed-sale analysis page."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from playwright.sync_api import sync_playwright

from Main.models.inventoryitem import InventoryItem
from Main.models.sellerlisting import SellerListing
from Main.services.seller_listings import save_sale_record

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_confirmed_sale_analysis_page_shows_only_the_owners_results(db_for_e2e, live_server):
    owner = get_user_model().objects.create_user("outcome-browser", password="password")
    other = get_user_model().objects.create_user("outcome-browser-other", password="password")
    inventory = InventoryItem.objects.create(user=owner, name="カメラ", category="カメラ")
    listing = SellerListing.objects.create(
        user=owner,
        inventory_item=inventory,
        external_listing_id="a123456781",
        url="https://auctions.yahoo.co.jp/jp/auction/a123456781",
        name="カメラ本体",
        acquisition_cost=1000,
        status="sold",
    )
    other_listing = SellerListing.objects.create(
        user=other,
        external_listing_id="a123456782",
        url="https://auctions.yahoo.co.jp/jp/auction/a123456782",
        name="他人の商品",
        acquisition_cost=1000,
        status="sold",
    )
    payload = {
        "salePrice": 2000,
        "actualFee": 100,
        "actualShippingCost": 100,
        "actualPackagingCost": 0,
        "actualOtherCost": 0,
        "soldAt": (timezone.now() - timedelta(days=1)).isoformat(),
    }
    save_sale_record(owner, listing.pk, payload)
    save_sale_record(other, other_listing.pk, payload)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
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
            page.fill('input[name="username"]', "outcome-browser")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')
            page.goto(f"{live_server.url}/taskle/seller-outcomes")
            page.get_by_text("カメラ本体").wait_for()
            assert "販売件数" in page.locator("#outcomeSummary").inner_text()
            assert "カメラ" in page.locator("#outcomeCategories").inner_text()
            assert "他人の商品" not in page.locator("body").inner_text()
            dimensions = page.evaluate(
                "() => ({scroll: document.documentElement.scrollWidth, width: innerWidth})"
            )
            assert dimensions["scroll"] <= dimensions["width"]
            assert not console_errors
        finally:
            context.close()
            browser.close()
