"""Browser evidence for the migrated search and watch workflow.

Yahoo retrieval is replaced with deterministic observations. The test does not
access production data, saved credentials, or external auction pages.
"""

from urllib.parse import urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from playwright.sync_api import sync_playwright

from Main.views import api, utils

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_search_watch_and_notification_browser_flow(db_for_e2e, live_server, client, monkeypatch):
    owner = get_user_model().objects.create_user("a0-browser-owner")
    client.force_login(owner)
    auction_url = "https://auctions.yahoo.co.jp/jp/auction/a1234567890"
    current_price = {"value": 2000}

    def current_items(keyword):
        return [
            {
                "name": "A0 中古カメラ",
                "currentPrice": current_price["value"],
                "startPrice": 1000,
                "bidding": 1,
                "remainingTime": "30分",
                "url": auction_url,
            }
        ]

    def closed_items(keyword):
        return [{"name": "A0 中古カメラ", "price": 4000}]

    monkeypatch.setattr(api, "scrape_current_listings", current_items)
    monkeypatch.setattr(utils, "scrape_current_listings", current_items)
    monkeypatch.setattr(utils, "scrape_data", closed_items)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})
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
        errors = []
        unexpected_requests = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda message: errors.append(message.text) if message.type == "error" else None,
        )

        def route_request(route):
            hostname = urlsplit(route.request.url).hostname
            if hostname in {"localhost", "127.0.0.1"}:
                route.continue_()
            elif hostname in {"cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com"}:
                content_type = (
                    "application/javascript"
                    if route.request.resource_type == "script"
                    else "text/css"
                )
                route.fulfill(status=200, body="", content_type=content_type)
            else:
                unexpected_requests.append(route.request.url)
                route.abort()

        page.route("**/*", route_request)
        try:
            page.goto(live_server.url + reverse("profile"))
            csrf = next(
                cookie["value"] for cookie in context.cookies() if cookie["name"] == "csrftoken"
            )

            page.goto(live_server.url + reverse("market_search") + "?mode=current")
            page.locator("#marketKeyword").fill("A0 カメラ")
            page.locator("#marketSearchButton").click()
            page.get_by_text("A0 中古カメラ", exact=True).wait_for()
            assert page.locator("#priceHeading").inner_text() == "現在価格"
            assert "1件を表示" in page.locator("#resultSummary").inner_text()

            def request(name, *, args=(), data=None):
                response = context.request.post(
                    live_server.url + reverse(name, args=args),
                    data=data if data is not None else {},
                    headers={"X-CSRFToken": csrf},
                )
                assert response.ok, f"{name}: HTTP {response.status}"
                return response.json()

            request(
                "watchlist",
                data={"name": "A0 中古カメラ", "url": auction_url, "currentPrice": 2000},
            )
            saved = request(
                "saved_searches", data={"name": "A0 ブラウザ条件", "keyword": "カメラ"}
            )["item"]
            current_price["value"] = 1500
            request("run_saved_search", args=(saved["id"],))
            request("run_saved_search", args=(saved["id"],))

            page.goto(live_server.url + reverse("notifications_page"))
            page.get_by_text("ウォッチ商品の価格が下がりました", exact=True).wait_for()
            assert page.get_by_text("ウォッチ商品の価格が下がりました", exact=True).count() == 1
            assert not errors
            assert not unexpected_requests
        finally:
            context.close()
            browser.close()
