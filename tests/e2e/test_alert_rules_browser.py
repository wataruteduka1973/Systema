"""Browser workflow for owner-scoped Phase 6 alert-rule CRUD."""

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import sync_playwright

from Main.models.savedsearch import SavedSearch

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_alert_rule_create_edit_delete_at_mobile_width(db_for_e2e, live_server):
    user = get_user_model().objects.create_user("alert-browser", password="password")
    saved = SavedSearch.objects.create(user=user, name="カメラ候補", keyword="camera")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        page.set_default_timeout(10_000)
        console_errors = []
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        try:
            page.goto(f"{live_server.url}/accounts/login/")
            page.fill('input[name="username"]', "alert-browser")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')
            page.goto(f"{live_server.url}/taskle/alerts")
            page.select_option("#alertTargetType", "savedSearch")
            page.select_option("#alertTargetId", str(saved.pk))
            page.select_option("#alertRuleType", "price_below")
            page.fill("#alertThreshold", "4000")
            page.click("#alertSubmit")
            page.locator("#alertRuleList article").wait_for()
            assert "価格が指定額以下" in page.locator("#alertRuleList").inner_text()
            assert "カメラ候補" in page.locator("#alertRuleList").inner_text()

            page.get_by_role("button", name="編集").click()
            page.fill("#alertThreshold", "3500")
            page.get_by_role("button", name="変更を保存").click()
            page.get_by_text("アラート条件を更新しました。").wait_for()
            assert "3500" in page.locator("#alertRuleList").inner_text()

            page.get_by_role("button", name="削除").click()
            page.get_by_text("アラート条件はまだありません。").wait_for()
            dimensions = page.evaluate(
                "() => ({scroll: document.documentElement.scrollWidth, width: innerWidth})"
            )
            assert dimensions["scroll"] <= dimensions["width"]
            assert not console_errors
        finally:
            context.close()
            browser.close()
