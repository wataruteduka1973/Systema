"""Failures show an in-page message instead of a browser dialog, and the page keeps its state."""

import json

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import expect, sync_playwright

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _json(route, status, payload):
    route.fulfill(status=status, content_type="application/json", body=json.dumps(payload))


def _open(playwright, live_server, username):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.set_default_timeout(10_000)
    dialogs: list[str] = []

    def dismiss(dialog):
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", dismiss)
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', "password")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    return browser, page, dialogs


def test_failed_history_update_shows_server_error_not_success(db_for_e2e, live_server):
    get_user_model().objects.create_user("feedback-history", password="password")
    with sync_playwright() as playwright:
        browser, page, dialogs = _open(playwright, live_server, "feedback-history")
        try:
            page.route(
                "**/taskle/get_search_words*", lambda r: _json(r, 200, {"searchWords": ["camera"]})
            )
            page.route(
                "**/taskle/update_market_data*",
                lambda r: _json(r, 500, {"error": "保存に失敗しました"}),
            )
            page.goto(f"{live_server.url}/taskle/yahuoku_history")
            page.select_option("#searchWordDropdown", "camera")
            page.click("#updateMarketData")

            message = page.locator("#systemaFeedback [role=alert]")
            expect(message).to_contain_text("更新に失敗しました: 保存に失敗しました")
            expect(page.locator("#systemaFeedback")).not_to_contain_text("更新しました。")
            expect(page.locator("#updateMarketData")).to_be_enabled()
            assert dialogs == []

            message.get_by_role("button", name="閉じる").click()
            expect(message).to_have_count(0)
        finally:
            browser.close()


def test_target_search_server_error_keeps_the_page_and_input(db_for_e2e, live_server):
    get_user_model().objects.create_user("feedback-target", password="password")
    with sync_playwright() as playwright:
        browser, page, dialogs = _open(playwright, live_server, "feedback-target")
        try:
            page.route(
                "**/taskle/api/v1/saved-searches/*/run",
                lambda r: _json(r, 500, {"error": "検索処理中にエラーが発生しました"}),
            )
            page.goto(f"{live_server.url}/taskle/Deep_Analysis_now")
            page.fill("#search", "ゲーム機")
            page.click("#button-search")

            expect(page.locator("#systemaFeedback [role=alert]")).to_contain_text(
                "検索に失敗しました: 検索処理中にエラーが発生しました"
            )
            # The page is not replaced by the error document.
            expect(page.locator("#search")).to_have_value("ゲーム機")
            expect(page.locator("nav.navbar-custom")).to_be_visible()
            expect(page.locator("#button-search")).to_be_enabled()
            assert dialogs == []
        finally:
            browser.close()
