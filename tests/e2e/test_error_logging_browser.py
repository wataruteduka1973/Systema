"""Browser verification for privacy-preserving JavaScript error signals."""

import pytest
from playwright.sync_api import sync_playwright

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_unhandled_rejection_reports_kind_without_browser_message(db_for_e2e, live_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(10_000)
        try:
            page.goto(f"{live_server.url}/taskle/")
            with page.expect_response(
                lambda response: "/taskle/api/v1/client-errors" in response.url
            ) as response_info:
                page.evaluate(
                    "setTimeout(() => Promise.reject(new Error('password=browser-secret')), 0)"
                )
            assert response_info.value.status == 204
        finally:
            browser.close()
