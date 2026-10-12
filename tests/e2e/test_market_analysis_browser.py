"""The merged market analysis page: predict from a new keyword or a saved one, and save new ones.

Yahoo retrieval is replaced with deterministic closed auctions; nothing external is contacted.
"""

from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import expect, sync_playwright

from Main.views import utils

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

KEYWORD = "テスト機"


def _closed_items(keyword):
    today = datetime.now().replace(hour=21, minute=0, second=0, microsecond=0)
    return [
        {
            "name": f"{keyword} 本体 中古 {index}",
            "price": 10000 + index * 40,
            "startPrice": 1000,
            "bidding": 5,
            "url": f"https://auctions.yahoo.co.jp/jp/auction/x{index:09d}",
            "time": (today - timedelta(days=80 - index)).isoformat(),
        }
        for index in range(80)
    ]


def test_market_analysis_predicts_from_new_and_saved_keywords(db_for_e2e, live_server, monkeypatch):
    monkeypatch.setattr(utils, "scrape_data", _closed_items)
    get_user_model().objects.create_user("market-analysis", password="password")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(15_000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(f"{live_server.url}/accounts/login/")
            page.fill('input[name="username"]', "market-analysis")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')

            # The old prediction page opens the new-keyword tab of the merged page.
            page.goto(f"{live_server.url}/taskle/Yahuoku_prediction")
            expect(page).to_have_url(f"{live_server.url}/taskle/Deep_Analysis?source=new")
            expect(page.locator("#sourceNewTab")).to_have_attribute("aria-selected", "true")
            expect(page.locator("#sourceNew")).to_be_visible()
            expect(page.locator("#sourceHistory")).to_be_hidden()
            expect(page.locator("#predictionSection")).to_be_hidden()

            page.fill("#search", KEYWORD)
            page.click("#button-search")
            expect(page.locator("#predictionSection")).to_be_visible()
            expect(page.locator("#predictionKeyword")).to_have_text(f"：{KEYWORD}")
            expect(page.locator("#predictionTable tbody tr")).to_have_count(4)
            expect(page.locator("#backtestStatus")).to_contain_text("期間を検証")
            expect(page.locator("#storedAnalysis")).to_be_hidden()

            # Saving moves the keyword into the history tab and shows its stored summary.
            page.click("#saveKeyword")
            expect(page.locator("#sourceHistoryTab")).to_have_attribute("aria-selected", "true")
            expect(page.locator("#searchWordDropdown")).to_have_value(KEYWORD)
            expect(page.locator("#storedAnalysis")).to_be_visible()
            expect(page.locator("#marketSummaryCards")).to_contain_text("80件")
            expect(page.locator("#saveKeyword")).to_be_hidden()
            expect(page).to_have_url(f"{live_server.url}/taskle/Deep_Analysis")

            # Switching tabs clears the results; a saved keyword predicts from the history tab.
            page.click("#sourceNewTab")
            expect(page.locator("#predictionSection")).to_be_hidden()
            page.click("#sourceHistoryTab")
            expect(page.locator("#storedAnalysis")).to_be_hidden()
            page.select_option("#searchWordDropdown", KEYWORD)
            page.click("#predictSavedKeyword")
            expect(page.locator("#predictionSection")).to_be_visible()
            expect(page.locator("#saveKeyword")).to_be_hidden()

            # A keyword typed again that is already saved offers no second save.
            page.click("#sourceNewTab")
            page.fill("#search", KEYWORD)
            page.press("#search", "Enter")
            expect(page.locator("#predictionSection")).to_be_visible()
            expect(page.locator("#saveKeyword")).to_be_hidden()
            assert errors == []
        finally:
            browser.close()
