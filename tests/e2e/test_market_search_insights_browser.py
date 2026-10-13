"""Market search shows a market summary, 相場比 chips and per-listing next actions.

Yahoo retrieval is replaced with deterministic data; nothing external is contacted.
"""

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import expect, sync_playwright

from Main.models.watchitem import WatchItem
from Main.views import api

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

PRICES = [8000, 9000, 9500, 10000, 10000, 10500, 11000, 12000, 30000]


def _closed(keyword):
    return [
        {
            "name": f"{keyword} 中古 {index}",
            "price": price,
            "startPrice": 1000,
            "bidding": 10 if price == 10000 else 2,
            "time": "",
            "url": f"https://auctions.yahoo.co.jp/jp/auction/c{index:09d}",
        }
        for index, price in enumerate(PRICES)
    ]


def _current(keyword):
    return [
        {
            "name": f"{keyword} 安い出品",
            "currentPrice": 7000,
            "bidding": 1,
            "remainingTime": "1日",
            "url": "https://auctions.yahoo.co.jp/jp/auction/n000000001",
        },
        {
            "name": f"{keyword} 相場の出品",
            "currentPrice": 10000,
            "bidding": 3,
            "remainingTime": "2日",
            "url": "https://auctions.yahoo.co.jp/jp/auction/n000000002",
        },
    ]


def test_market_search_summary_comparison_and_actions(db_for_e2e, live_server, monkeypatch):
    monkeypatch.setattr(api, "scrape_data", _closed)
    monkeypatch.setattr(api, "scrape_current_listings", _current)
    user = get_user_model().objects.create_user("market-insights", password="password")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(15_000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(f"{live_server.url}/accounts/login/")
            page.fill('input[name="username"]', "market-insights")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')

            # Current listings before any closed data: no comparison, with a way to fetch it.
            page.goto(f"{live_server.url}/taskle/market-search?mode=current")
            page.fill("#marketKeyword", "カメラ")
            page.click("#marketSearchButton")
            insights = page.locator("#marketInsights")
            expect(insights).to_be_visible()
            expect(page.locator("#closedMarketNote")).to_contain_text("保存済みの落札相場がない")
            expect(
                page.locator("#resultTable tbody tr").first.locator(".compare-chip")
            ).to_have_count(0)
            page.click("#fetchClosedMarket")
            expect(page.locator("#closedMarketNote")).to_contain_text("中央値10,000円")
            expect(insights).to_contain_text("相場より安い出品")
            expect(page.locator("#insightTiles")).to_contain_text("1件")
            expect(
                page.locator("#resultTable tbody tr").first.locator(".compare-chip")
            ).to_have_text("-30%")

            # Closed market summary with distribution, then back to current listings.
            page.locator("#insightActions button", has_text="落札相場を見る").click()
            expect(page.locator("#insightTiles")).to_contain_text("9件")
            expect(page.locator("#insightTiles")).to_contain_text("10,000円")
            expect(page.locator("#priceDistribution .distribution-bin").first).to_be_visible()
            expect(page.locator("#distributionLabels")).to_contain_text("入札集中")
            expect(page.locator("#distributionNote")).to_contain_text("外れ値1件")
            expect(page.locator("#insightActions a")).to_have_attribute(
                "href", "/taskle/Deep_Analysis?source=new&keyword=%E3%82%AB%E3%83%A1%E3%83%A9"
            )
            expect(page.locator("#actionHeading")).to_be_hidden()
            expect(page.locator("#closedMarketNote")).to_be_hidden()
            # Bins span the kept prices only (8,000-12,000), so there is no empty edge bin.
            expect(page.locator("#distributionLabels > span").last).not_to_contain_text("1.3万")

            page.locator("#insightActions button", has_text="出品中の商品を探す").click()
            expect(page.locator("#actionHeading")).to_be_visible()
            first = page.locator("#resultTable tbody tr").first
            first.locator("button", has_text="ウォッチ").click()
            expect(first.locator("button", has_text="ウォッチ中")).to_be_disabled()

            # 仕入れ予算 registers the listing and opens its budget in target analysis.
            page.locator("#resultTable tbody tr").nth(1).locator(
                "button", has_text="仕入れ予算"
            ).click()
            page.wait_for_url("**/taskle/Deep_Analysis_now?budget=*")
            budget_url = page.url
            expect(page.locator("#purchaseBudgetEditor")).to_contain_text("相場の出品")
            assert errors == []
        finally:
            browser.close()

    # The ORM is checked outside Playwright's event loop.
    watched = {item.current_price: item for item in WatchItem.objects.filter(user=user)}
    assert sorted(watched) == [7000, 10000]
    assert {item.market_median for item in watched.values()} == {10000}
    assert budget_url.endswith(f"budget={watched[10000].pk}")
