"""Top-page layout: 3 x 4 recommendation grid and aligned feature-card buttons."""

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import expect, sync_playwright

from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _item(index):
    return {
        "name": f"おすすめ商品 {index}",
        "url": f"https://auctions.yahoo.co.jp/jp/auction/l{index:09d}",
        "imageUrl": "",
        "price": 12000,
        "remainingSeconds": 7200,
        "remainingTime": "2時間",
        "marketMedian": 22500,
        "condition": "used",
        "conditionLabel": "中古・動作品",
        "bidding": 2,
        "buyDecision": {"status": "strong_buy", "label": "かなり買い時", "score": 90 - index},
        "marketComparison": {"differenceRate": -46.7},
    }


def test_twelve_recommendations_in_rows_of_four_and_feature_buttons_align(db_for_e2e, live_server):
    user = get_user_model().objects.create_user("top-layout", password="password")
    saved = SavedSearch.objects.create(user=user, name="ゲーム機", keyword="ゲーム機")
    SearchRun.objects.create(
        user=user,
        saved_search=saved,
        keyword="ゲーム機",
        search_type=SearchRun.CURRENT,
        item_count=14,
        succeeded=True,
        trigger="saved",
        result_snapshot={"medianPrice": 22500, "recommend_items": [_item(i) for i in range(14)]},
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(10_000)
        try:
            page.goto(f"{live_server.url}/accounts/login/")
            page.fill('input[name="username"]', "top-layout")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')
            page.goto(f"{live_server.url}/taskle/")

            cards = page.locator(".recommendation-card")
            expect(cards).to_have_count(12)
            tops = [round(cards.nth(i).bounding_box()["y"]) for i in range(12)]
            assert len(set(tops)) == 3
            assert [tops[i * 4 : i * 4 + 4].count(tops[i * 4]) for i in range(3)] == [4, 4, 4]

            buttons = page.locator(".feature-card .btn-feature")
            expect(buttons).to_have_count(4)
            button_tops = {round(buttons.nth(i).bounding_box()["y"]) for i in range(4)}
            assert len(button_tops) == 1
            decoration = buttons.first.evaluate("e => getComputedStyle(e).textDecorationLine")
            assert decoration == "none"
        finally:
            browser.close()
