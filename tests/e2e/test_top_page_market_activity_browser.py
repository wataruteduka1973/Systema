"""Top-page 市場の動き links open market search results directly.

Saved data is created in the database; current listings are faked. Nothing external is contacted.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.views import api

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _closed_run(user, keyword, prices, days_ago):
    run = SearchRun.objects.create(user=user, keyword=keyword, item_count=len(prices))
    SearchRun.objects.filter(pk=run.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
    for index, price in enumerate(prices):
        scraping.objects.create(
            search_run=run,
            SearchWord=keyword,
            SearchDay="2026-10-01",
            Bidding="2",
            EndPrice=price,
            StartPrice=1,
            Name=f"{keyword} 中古 {index}",
            URL=f"https://auctions.yahoo.co.jp/jp/auction/h{run.pk}{index:08d}",
        )


def _current(keyword):
    return [
        {
            "name": f"{keyword} 出品",
            "currentPrice": 9000,
            "bidding": 1,
            "remainingTime": "1日",
            "url": "https://auctions.yahoo.co.jp/jp/auction/n000000001",
        }
    ]


def test_top_page_activity_opens_market_search(db_for_e2e, live_server, monkeypatch):
    monkeypatch.setattr(api, "scrape_current_listings", _current)
    user = get_user_model().objects.create_user("activity-browser", password="password")
    _closed_run(user, "カメラ", [9000, 10000, 11000], days_ago=5)
    _closed_run(user, "カメラ", [11000, 12000, 13000], days_ago=1)
    run = SearchRun.objects.create(
        user=user, keyword="レンズ", search_type=SearchRun.CURRENT, item_count=1
    )
    SearchRun.objects.filter(pk=run.pk).update(created_at=timezone.now())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(15_000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(f"{live_server.url}/accounts/login/")
            page.fill('input[name="username"]', "activity-browser")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')
            page.goto(f"{live_server.url}/taskle/")

            moves = page.locator("#marketMoves")
            expect(moves).to_contain_text("▲ +20.0%")
            expect(page.locator("#recentKeywords li")).to_have_count(2)

            # A saved keyword opens its saved data without a new search.
            moves.get_by_role("link", name="カメラ").click()
            page.wait_for_url("**/taskle/market-search?mode=history")
            expect(page.locator("#historyKeyword")).to_have_value("カメラ")
            expect(page.locator("#insightTiles")).to_contain_text("12,000円")
            expect(page.locator("#resultTable tbody tr")).to_have_count(3)

            # A keyword with only current runs searches current listings once.
            page.goto(f"{live_server.url}/taskle/")
            page.locator("#recentKeywords").get_by_role("link", name="レンズ").click()
            page.wait_for_url("**/taskle/market-search?mode=current")
            expect(page.locator("#marketKeyword")).to_have_value("レンズ")
            expect(page.locator("#resultTable tbody tr")).to_have_count(1)
            assert errors == []
        finally:
            browser.close()
