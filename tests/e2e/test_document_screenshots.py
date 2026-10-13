"""Regenerate the screenshots used by the Sphinx documentation (GitHub Pages).

Not a regular test: it runs only when DOC_SCREENSHOT_DIR is set, e.g.

    DOC_SCREENSHOT_DIR=document/_static/screens DB_ENGINE=sqlite \
        python -m pytest -m e2e tests/e2e/test_document_screenshots.py

It reuses the guide screenshot fixtures: Yahoo is never contacted, the fetch boundary serves
generated sample listings, and listing images are generated SVGs.
"""

import os
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import expect, sync_playwright

from Main.views import utils
from tests.e2e.test_guide_screenshots import KEYWORD, _fake_fetch, _search, _serve_image

OUTPUT = os.environ.get("DOC_SCREENSHOT_DIR")
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(not OUTPUT, reason="set DOC_SCREENSHOT_DIR to regenerate document images"),
]

VIEWPORT = {"width": 1280, "height": 900}
SCALE = 1.25
MAX_HEIGHT = 900


def _shoot(page, name: str, selector: str, height: int | None = None) -> None:
    """Capture from the top of `selector`: the element (up to MAX_HEIGHT), or `height` CSS px."""
    target = page.locator(selector).first
    target.scroll_into_view_if_needed()
    page.evaluate("document.getElementById('systemaFeedback')?.replaceChildren()")
    page.wait_for_timeout(600)
    box = target.bounding_box()
    top = box["y"] + page.evaluate("window.scrollY")
    page.screenshot(
        path=str(Path(OUTPUT) / f"{name}.jpg"),
        type="jpeg",
        quality=80,
        clip={
            "x": 0,
            "y": top - 12,
            "width": VIEWPORT["width"],
            "height": height or min(MAX_HEIGHT, box["height"] + 24),
        },
        full_page=True,
    )


def test_regenerate_document_screenshots(db_for_e2e, live_server, monkeypatch):
    monkeypatch.setattr(utils, "_request_with_retry", _fake_fetch)
    get_user_model().objects.create_user("guide", password="password")
    base = live_server.url
    Path(OUTPUT).mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=SCALE)
        page.set_default_timeout(20_000)
        page.route("https://*.yimg.jp/**", _serve_image)
        try:
            page.goto(f"{base}/accounts/login/")
            page.fill('input[name="username"]', "guide")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')

            # 市場検索: closed-market summary, then current listings with 相場比 and actions.
            page.goto(f"{base}/taskle/market-search?mode=closed")
            page.fill("#marketKeyword", KEYWORD)
            page.click("#marketSearchButton")
            expect(page.locator("#marketInsights")).to_be_visible()
            _shoot(page, "market_search_summary", "#marketInsights")
            page.locator("#insightActions button", has_text="出品中の商品を探す").click()
            expect(page.locator("#closedMarketNote")).to_contain_text("中央値")
            _shoot(page, "market_search_current", "#resultTable", height=620)

            # 相場分析: prediction for the keyword.
            page.goto(f"{base}/taskle/Deep_Analysis?source=new&keyword={KEYWORD}")
            page.locator("#predictionTable tbody tr").first.wait_for()
            _shoot(page, "market_analysis", "#predictionSection")

            # ターゲット分析: also saves the condition, which feeds the top page and alerts.
            _search(page, f"{base}/taskle/Deep_Analysis_now")
            page.locator("#targetResults .target-result-card").nth(3).wait_for()
            _shoot(page, "target_analysis", "#targetResultsHeader", height=760)

            page.goto(f"{base}/taskle/")
            _shoot(page, "top_market_activity", ".market-activity", height=262)

            # アラート: one rule plus the saved-search refresh status.
            page.goto(f"{base}/taskle/alerts")
            page.locator("#refreshList .refresh-card").first.wait_for()
            page.select_option("#alertTargetType", "savedSearch")
            page.select_option("#alertRuleType", "median_discount")
            page.click("#alertSubmit")
            page.locator("#alertRuleList .alert-target-group").first.wait_for()
            _shoot(page, "alerts", "#refreshHeading", height=640)

            page.goto(f"{base}/taskle/notifications")
            page.locator("#notificationList article").first.wait_for()
            _shoot(page, "notifications", "#notificationCategories", height=360)
        finally:
            browser.close()
