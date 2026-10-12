"""Target-analysis result cards: table facts, images, comparison, watch and phone layout."""

import base64

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import expect, sync_playwright

from Main.models.watchitem import WatchItem

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _item(auction_id, name, *, image, price=12000, rate=-46.7, position="below"):
    return {
        "name": name,
        "url": f"https://auctions.yahoo.co.jp/jp/auction/{auction_id}",
        "imageUrl": image,
        "price": price,
        "remainingSeconds": 7200,
        "remainingTime": "2時間",
        "bidding": 3,
        "marketMedian": 22500,
        "condition": "used",
        "conditionLabel": "中古・動作品",
        "attributes": [],
        "attributeLabels": [],
        "buyDecision": {
            "status": "strong_buy",
            "label": "かなり買い時",
            "score": 90,
            "reason": "相場中央値より大きく安い",
        },
        "marketComparison": {"differenceRate": rate, "position": position, "label": ""},
    }


RESULT = {
    "medianPrice": 22500,
    "marketStatistics": None,
    "recommend_items": [
        _item("c10000001", "画像ありの<b>商品</b>", image="https://auctions.c.yimg.jp/ok.jpg"),
        _item("c10000002", "画像なしの商品", image=""),
        _item("c10000003", "画像切れの商品", image="https://auctions.c.yimg.jp/broken.jpg"),
        _item(
            "c10000004",
            "外部画像の商品",
            image="https://evil.example/x.jpg",
            rate=20.0,
            position="above",
        ),
    ],
}


@pytest.mark.parametrize("viewport", [(1280, 900), (390, 844)], ids=["desktop", "phone"])
def test_result_cards_show_table_facts_and_add_to_watchlist(db_for_e2e, live_server, viewport):
    get_user_model().objects.create_user("target-cards", password="password")
    width, height = viewport
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        page.set_default_timeout(10_000)
        requested_hosts = []
        page.on("request", lambda request: requested_hosts.append(request.url))
        page.route(
            "https://auctions.c.yimg.jp/**",
            lambda route: (
                route.abort()
                if route.request.url.endswith("broken.jpg")
                else route.fulfill(status=200, content_type="image/png", body=PIXEL)
            ),
        )
        console_errors = []
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        try:
            page.goto(f"{live_server.url}/accounts/login/")
            page.fill('input[name="username"]', "target-cards")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')
            page.goto(f"{live_server.url}/taskle/Deep_Analysis_now")
            expect(page.locator("#targetResultsHeader")).to_be_hidden()
            page.evaluate("result => window.renderTargetAnalysisResult(result)", RESULT)

            cards = page.locator("#targetResults .target-result-card")
            expect(cards).to_have_count(4)
            expect(page.locator("#targetResultCount")).to_have_text("4件")
            first = cards.nth(0)
            # Names are text, never markup.
            expect(first.locator(".target-result-name")).to_have_text("画像ありの<b>商品</b>")
            expect(first.locator("img")).to_have_js_property("naturalWidth", 1)
            for text in (
                "かなり買い時 (90)",
                "中古・動作品",
                "¥12,000",
                "相場比 -46.7%",
                "3件",
                "2時間",
                "¥22,500",
                "相場中央値より大きく安い",
            ):
                expect(first).to_contain_text(text)
            expect(first.get_by_role("link", name="商品ページ")).to_have_attribute(
                "href", "https://auctions.yahoo.co.jp/jp/auction/c10000001"
            )
            expect(cards.nth(1).locator("img")).to_have_count(0)
            expect(cards.nth(1)).to_contain_text("画像なし")
            expect(cards.nth(2).locator("img")).to_have_count(0)
            expect(cards.nth(3).locator("img")).to_have_count(0)
            expect(cards.nth(3)).to_contain_text("相場比 +20.0%")

            cards.nth(0).get_by_label("比較").check()
            cards.nth(1).get_by_label("比較").check()
            expect(page.locator("#marketComparisonTray")).to_be_visible()

            cards.nth(0).get_by_role("button", name="ウォッチリストへ追加").click()
            expect(page.locator("#watchlistCards")).to_contain_text("画像ありの<b>商品</b>")
            expect(
                page.locator(".target-result-card")
                .nth(0)
                .get_by_role("button", name="ウォッチ解除")
            ).to_be_visible()

            assert page.evaluate("document.documentElement.scrollWidth") <= width
            assert not any("evil.example" in url for url in requested_hosts)
            assert [text for text in console_errors if "Failed to load resource" not in text] == []
        finally:
            context.close()
            browser.close()

    assert WatchItem.objects.get().url == "https://auctions.yahoo.co.jp/jp/auction/c10000001"


def test_empty_result_shows_message(db_for_e2e, live_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(10_000)
        try:
            page.goto(f"{live_server.url}/taskle/Deep_Analysis_now")
            page.evaluate(
                "() => window.renderTargetAnalysisResult({medianPrice: 1000, recommend_items: []})"
            )
            expect(page.locator("#targetResultsEmpty")).to_be_visible()
            expect(page.locator("#targetResultCount")).to_have_text("0件")
        finally:
            browser.close()
