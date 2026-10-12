"""Watchlist cards: table facts, image fallback, editor, history, budget and removal."""

import base64

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import expect, sync_playwright

from Main.models.watchitem import WatchItem, WatchPriceSnapshot

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _watch(user, auction_id, name, *, image, priority=0, note=""):
    item = WatchItem.objects.create(
        user=user,
        name=name,
        url=f"https://auctions.yahoo.co.jp/jp/auction/{auction_id}",
        primary_image_url=image,
        current_price=8000,
        added_price=10000,
        bidding=4,
        remaining_time="3時間",
        condition="used",
        condition_label="中古・動作品",
        market_median=15000,
        buy_status="strong_buy",
        buy_label="かなり買い時",
        buy_score=88,
        buy_reason="相場中央値より大きく安い",
        priority=priority,
        note=note,
    )
    for price in (10000, 8000):
        WatchPriceSnapshot.objects.create(watch_item=item, price=price, bidding=4)
    return item


@pytest.mark.parametrize("viewport", [(1280, 900), (390, 844)], ids=["desktop", "phone"])
def test_watchlist_cards_show_facts_and_support_every_action(db_for_e2e, live_server, viewport):
    user = get_user_model().objects.create_user("watch-cards", password="password")
    first = _watch(
        user,
        "w10000001",
        "画像ありウォッチ",
        image="https://auctions.c.yimg.jp/ok.jpg",
        priority=2,
        note="週末までに判断",
    )
    _watch(user, "w10000002", "画像なしウォッチ", image="")
    width, height = viewport
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_default_timeout(10_000)
        page.route(
            "https://auctions.c.yimg.jp/**",
            lambda route: route.fulfill(status=200, content_type="image/png", body=PIXEL),
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
            page.fill('input[name="username"]', "watch-cards")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')
            page.goto(f"{live_server.url}/taskle/Deep_Analysis_now")

            cards = page.locator("#watchlistCards .watch-card")
            expect(cards).to_have_count(2)
            card = cards.filter(has_text="画像ありウォッチ")
            expect(card.locator("img")).to_have_js_property("naturalWidth", 1)
            for text in (
                "かなり買い時 (88)",
                "中古・動作品",
                "追跡中",
                "優先度 高",
                "¥8,000",
                "追加時から -¥2,000",
                "¥10,000",
                "¥15,000",
                "4件",
                "2回観測",
                "相場中央値より大きく安い",
                "週末までに判断",
                "最終確認",
            ):
                expect(card).to_contain_text(text)
            expect(cards.filter(has_text="画像なしウォッチ").locator("img")).to_have_count(0)
            expect(cards.filter(has_text="画像なしウォッチ")).to_contain_text("画像なし")
            assert page.evaluate("document.documentElement.scrollWidth") <= width

            card.get_by_role("button", name="履歴").click()
            expect(card.locator(".watch-history")).to_contain_text("価格・入札履歴（2件）")
            card.get_by_role("button", name="履歴").click()
            expect(card.locator(".watch-history")).to_be_hidden()

            card.get_by_role("button", name="購入上限・利益").click()
            expect(page.locator("#purchaseBudgetEditor")).to_contain_text("画像ありウォッチ")

            card.locator("summary", has_text="判断を編集").click()
            card.locator("select").nth(1).select_option("skipped")
            card.get_by_role("button", name="判断を保存").click()
            expect(cards).to_have_count(1)
            page.select_option("#watchStatusFilter", "")
            expect(cards).to_have_count(2)
            expect(cards.filter(has_text="画像ありウォッチ")).to_contain_text("見送り")

            cards.filter(has_text="画像なしウォッチ").get_by_role(
                "button", name="ウォッチ解除"
            ).click()
            expect(cards).to_have_count(1)
            assert console_errors == []
        finally:
            browser.close()

    first.refresh_from_db()
    assert first.lifecycle_status == "skipped"
    assert list(WatchItem.objects.values_list("name", flat=True)) == ["画像ありウォッチ"]
