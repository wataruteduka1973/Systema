"""Browser workflow for the owner-scoped confirmed-sale analysis page."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

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


def _sale_this_and_last_month(owner):
    """One sale on the 1st of this month and one on the 1st of last month (Asia/Tokyo noon)."""
    now = timezone.localtime()
    this_month = now.replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    last_month = (this_month - timedelta(days=1)).replace(day=1)
    inventory = InventoryItem.objects.create(user=owner, name="時計", category="時計")
    for index, (sold_at, price) in enumerate(((this_month, 5000), (last_month, 3000))):
        listing = SellerListing.objects.create(
            user=owner,
            inventory_item=inventory,
            external_listing_id=f"a12345679{index}",
            url=f"https://auctions.yahoo.co.jp/jp/auction/a12345679{index}",
            name=f"時計{index}",
            acquisition_cost=1000,
            purchase_shipping_cost=200,
            status="sold",
        )
        save_sale_record(
            owner,
            listing.pk,
            {
                "salePrice": price,
                "actualFee": 300,
                "actualShippingCost": 400,
                "actualPackagingCost": 100,
                "actualOtherCost": 0,
                "soldAt": sold_at.isoformat(),
            },
        )
    return this_month, last_month


@pytest.mark.parametrize("viewport", [(1280, 900), (390, 844)], ids=["desktop", "phone"])
def test_period_filter_monthly_trend_and_expense_breakdown(db_for_e2e, live_server, viewport):
    owner = get_user_model().objects.create_user("outcome-period-browser", password="password")
    this_month, last_month = _sale_this_and_last_month(owner)
    width, height = viewport
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
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
            page.fill('input[name="username"]', "outcome-period-browser")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')
            page.goto(f"{live_server.url}/taskle/seller-outcomes")

            summary = page.locator("#outcomeSummary")
            expect(summary).to_contain_text("2 件")
            expect(page.locator("#outcomePeriodLabel")).to_have_text(
                "全期間の実績を表示しています。"
            )
            expect(page.locator("#monthlyChart")).to_be_visible()
            assert page.evaluate("Boolean(Chart.getChart('monthlyChart'))")
            page.get_by_text("月別の数値を表で見る").click()
            rows = page.locator("#monthlyTable tr")
            expect(rows).to_have_count(2)
            expect(rows.first).to_contain_text(last_month.strftime("%Y/%m"))

            breakdown = page.locator("#expenseBreakdown")
            # Two sales: purchase 1200, fee 300, shipping 400, packaging 100 each.
            expect(breakdown.locator('[data-expense="purchase"]')).to_contain_text("2,400 円")
            expect(breakdown.locator('[data-expense="fee"]')).to_contain_text("600 円")
            expect(breakdown.locator('[data-expense="shipping"]')).to_contain_text("800 円")
            expect(breakdown.locator('[data-expense="packaging"]')).to_contain_text("200 円")
            expect(summary).to_contain_text("4,000 円")  # total expenses

            page.select_option("#outcomePeriod", "last-month")
            expect(summary).to_contain_text("1 件")
            expect(summary).to_contain_text("3,000 円")
            expect(page.locator("#outcomePeriodLabel")).to_contain_text(
                last_month.strftime("%Y/%m/01")
            )
            assert f"from={last_month:%Y-%m-01}" in page.url

            page.reload()
            expect(page.locator("#outcomePeriod")).to_have_value("custom")
            expect(summary).to_contain_text("1 件")

            page.fill("#outcomeFrom", this_month.strftime("%Y-%m-02"))
            page.fill("#outcomeTo", this_month.strftime("%Y-%m-01"))
            page.get_by_role("button", name="表示").click()
            expect(page.locator("#outcomeMessage")).to_contain_text("開始日は終了日以前")

            page.select_option("#outcomePeriod", "all")
            expect(page.locator("#outcomeMessage")).to_be_hidden()
            assert page.evaluate("document.documentElement.scrollWidth") <= width
            assert [text for text in console_errors if "400" not in text] == []
        finally:
            browser.close()
