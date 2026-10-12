"""Top-page recommendation cards: images, fallback, and adding to the watchlist."""

import base64

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import expect, sync_playwright

from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.models.watchitem import WatchItem

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

# 1x1 PNG served for listing images so the browser never contacts Yahoo.
PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _item(auction_id, name, *, image):
    return {
        "name": name,
        "url": f"https://auctions.yahoo.co.jp/jp/auction/{auction_id}",
        "imageUrl": image,
        "price": 12000,
        "remainingSeconds": 7200,
        "remainingTime": "2時間",
        "marketMedian": 22500,
        "condition": "used",
        "conditionLabel": "中古・動作品",
        "bidding": 2,
        "buyDecision": {"status": "strong_buy", "label": "かなり買い時", "score": 90},
        "marketComparison": {"differenceRate": -46.7},
    }


def test_recommendation_cards_show_images_and_add_to_watchlist(db_for_e2e, live_server):
    user = get_user_model().objects.create_user("top-reco", password="password")
    saved = SavedSearch.objects.create(user=user, name="ゲーム機", keyword="ゲーム機")
    SearchRun.objects.create(
        user=user,
        saved_search=saved,
        keyword="ゲーム機",
        search_type=SearchRun.CURRENT,
        item_count=3,
        succeeded=True,
        trigger="saved",
        result_snapshot={
            "medianPrice": 22500,
            "recommend_items": [
                _item("a10000001", "画像ありの商品", image="https://auctions.c.yimg.jp/ok.jpg"),
                _item("a10000002", "画像なしの商品", image=""),
                _item("a10000003", "画像切れの商品", image="https://auctions.c.yimg.jp/broken.jpg"),
            ],
        },
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
        page = context.new_page()
        page.set_default_timeout(10_000)
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
            page.fill('input[name="username"]', "top-reco")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')
            page.goto(f"{live_server.url}/taskle/")

            cards = page.locator(".recommendation-card")
            expect(cards).to_have_count(3)
            with_image = cards.filter(has_text="画像ありの商品")
            expect(with_image.locator("img")).to_have_js_property("naturalWidth", 1)
            expect(cards.filter(has_text="画像なしの商品").locator("img")).to_have_count(0)
            expect(cards.filter(has_text="画像切れの商品").locator("img")).to_have_count(0)
            for text in ("かなり買い時 (90)", "中古・動作品", "相場比 -46.7%", "2件", "¥22,500"):
                expect(cards.first).to_contain_text(text)

            button = with_image.locator(".recommendation-watch")
            expect(button).to_have_text("ウォッチリストへ追加")
            button.click()
            expect(page.locator("#systemaFeedback [role=status]")).to_contain_text(
                "「画像ありの商品」をウォッチリストに追加しました"
            )
            expect(button).to_have_text("ウォッチ中")
            expect(button).to_be_disabled()

            width = page.evaluate("document.documentElement.scrollWidth")
            assert width <= 390
            assert [text for text in console_errors if "Failed to load resource" not in text] == []
        finally:
            context.close()
            browser.close()

    watch = WatchItem.objects.get()
    assert watch.user == user
    assert watch.url == "https://auctions.yahoo.co.jp/jp/auction/a10000001"
    assert watch.current_price == 12000
    assert watch.search_keyword == "ゲーム機"
