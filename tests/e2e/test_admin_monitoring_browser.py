"""Browser verification of staff monitoring, filtering, privacy and responsive layout."""

from pathlib import Path
from urllib.parse import urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from playwright.sync_api import sync_playwright

from Main.models.errorlog import ErrorLog
from Main.models.searchrun import SearchRun

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_staff_monitoring_browser(db_for_e2e, live_server, client):
    staff = get_user_model().objects.create_user("monitor@example.test", is_staff=True)
    client.force_login(staff)
    SearchRun.objects.create(user=staff, keyword="private-keyword", duration_ms=120)
    SearchRun.objects.create(
        session_key="private-session",
        keyword="private-keyword",
        duration_ms=300,
        succeeded=False,
        failure_code="html_parse_error",
    )
    ErrorLog.objects.create(error_code="500", error_message="private-cookie")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        context.add_cookies(
            [
                {
                    "name": "sessionid",
                    "value": client.cookies["sessionid"].value,
                    "url": live_server.url,
                }
            ]
        )
        page = context.new_page()
        failures = []
        unexpected_hosts = []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.on(
            "console",
            lambda message: failures.append(message.text) if message.type == "error" else None,
        )

        def restrict(route):
            host = urlsplit(route.request.url).hostname
            if host in {
                "localhost",
                "127.0.0.1",
                "cdn.jsdelivr.net",
                "fonts.googleapis.com",
                "fonts.gstatic.com",
            }:
                route.continue_()
            else:
                unexpected_hosts.append(host)
                route.abort()

        page.route("**/*", restrict)
        try:
            url = live_server.url + reverse("developer_dashboard")
            page.goto(url)
            page.get_by_role("heading", name="管理者モニタリング", exact=True).wait_for()
            assert "50.0%" in page.locator("#monitoringSummary").inner_text()
            assert "HTML解析失敗" in page.locator("main").inner_text()
            for value in (
                "monitor@example.test",
                "private-keyword",
                "private-session",
                "private-cookie",
            ):
                assert value not in page.locator("body").inner_text()
            output = Path("logs/phase8")
            output.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output / "desktop.png"), full_page=True)
            page.get_by_label("集計期間", exact=True).select_option("1")
            page.get_by_label("エラー種別", exact=True).select_option("browser")
            page.get_by_role("button", name="適用", exact=True).click()
            page.wait_for_url("**/developer/?**")
            assert "エラー記録はありません。" in page.locator("main").inner_text()
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(output / "mobile.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.goto(url + "?days=invalid")
            page.get_by_role("alert").wait_for()
            page.get_by_role("link", name="リセット", exact=True).click()
            page.locator("#monitoringSummary").wait_for()
            # Invalid filter returns HTTP 400 intentionally; Chromium may log it.
            assert all("400" in message for message in failures)
            assert not unexpected_hosts
        finally:
            context.close()
            browser.close()
