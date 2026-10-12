"""Browser workflow for owner-scoped target search, result persistence and watch registration.

Yahoo is never contacted: the HTTP fetch boundary returns saved HTML fixtures, so the
real Yahoo parser, search use case and persistence run unchanged.
"""

from pathlib import Path
from urllib.parse import urlparse

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import expect, sync_playwright

from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.models.watchitem import WatchItem
from Main.views import utils

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"
CHEAP_ITEM_URL = "https://auctions.yahoo.co.jp/jp/auction/b200000001"


class _FixtureResponse:
    def __init__(self, text: str) -> None:
        self.text = text


def _fixture_fetch(url, headers, max_retries=3, timeout=15):
    """Serve the first result page from fixtures and an empty second page."""
    if "b=1&" not in url:
        return _FixtureResponse("<html></html>")
    name = "target_search_closed.html" if "closedsearch" in url else "target_search_current.html"
    return _FixtureResponse((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _login(page, base_url: str, username: str) -> None:
    page.goto(f"{base_url}/accounts/login/")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', "password")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def test_target_search_persists_owned_runs_and_watch_survives_reload(
    db_for_e2e, live_server, monkeypatch
):
    monkeypatch.setattr(utils, "_request_with_retry", _fixture_fetch)
    user_model = get_user_model()
    owner = user_model.objects.create_user("target-owner", password="password")
    user_model.objects.create_user("target-other", password="password")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.set_default_timeout(15_000)
        console_errors: list[str] = []
        external_hosts: set[str] = set()
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        page.on("request", lambda request: external_hosts.add(urlparse(request.url).hostname))
        try:
            _login(page, live_server.url, "target-owner")
            page.goto(f"{live_server.url}/taskle/Deep_Analysis_now")
            page.fill("#search", "ゲーム機")
            page.click("#button-search")

            results = page.locator("#targetResults")
            expect(results).to_contain_text("中古 ゲーム機 本体 お買い得")
            cheap_card = results.locator(".target-result-card", has_text="お買い得")
            expect(cheap_card).to_contain_text("かなり買い時")
            expect(cheap_card).to_contain_text("¥12,000")

            cheap_card.get_by_role("button", name="ウォッチリストへ追加").click()
            watchlist = page.locator("#watchlistTable")
            expect(watchlist).to_be_visible()
            expect(watchlist).to_contain_text("中古 ゲーム機 本体 お買い得")

            page.reload()
            expect(page.locator("#watchlistTable")).to_contain_text("中古 ゲーム機 本体 お買い得")
            assert not console_errors
            assert "yahoo.co.jp" not in " ".join(host or "" for host in external_hosts)
        finally:
            context.close()

        other_context = browser.new_context(viewport={"width": 1280, "height": 900})
        other_page = other_context.new_page()
        other_page.set_default_timeout(15_000)
        try:
            _login(other_page, live_server.url, "target-other")
            other_page.goto(f"{live_server.url}/taskle/Deep_Analysis_now")
            expect(other_page.locator("#watchlistEmpty")).to_be_visible()
            expect(other_page.locator("#watchlistTable")).to_be_hidden()
        finally:
            other_context.close()
            browser.close()

    saved = SavedSearch.objects.get(user=owner)
    runs = SearchRun.objects.filter(user=owner).order_by("created_at")
    assert [run.search_type for run in runs] == [SearchRun.CLOSED, SearchRun.CURRENT]
    assert all(run.succeeded and run.trigger == "saved" for run in runs)
    assert all(run.saved_search_id == saved.pk for run in runs)
    assert [run.item_count for run in runs] == [6, 2]
    assert not SearchRun.objects.exclude(user=owner).exists()
    watch = WatchItem.objects.get()
    assert watch.user == owner
    assert watch.url == CHEAP_ITEM_URL
    assert watch.current_price == 12000
