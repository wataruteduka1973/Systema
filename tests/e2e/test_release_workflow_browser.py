"""Release chains through real session/CSRF APIs, followed by browser rendering.

Only Yahoo retrieval is replaced with deterministic observations. No production I/O.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from Main.models.notification import Notification
from Main.models.watchitem import WatchItem
from Main.scraping.seller_listing import ListingObservation
from Main.views import utils

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_release_purchase_to_sale_chain(db_for_e2e, live_server, client, monkeypatch):
    owner = get_user_model().objects.create_user("release-owner")
    client.force_login(owner)
    price = {"value": 2000}
    auction_url = "https://auctions.yahoo.co.jp/jp/auction/a1234567890"
    monkeypatch.setattr(
        utils, "scrape_data", lambda keyword: [{"name": "中古カメラ", "price": 4000}]
    )
    monkeypatch.setattr(
        utils,
        "scrape_current_listings",
        lambda keyword: [
            {
                "name": "中古カメラ",
                "currentPrice": price["value"],
                "bidding": 1,
                "remainingTime": "30分",
                "url": auction_url,
            }
        ],
    )
    monkeypatch.setattr(
        "Main.services.seller_listings.fetch_listing",
        lambda url: ListingObservation(
            "公開カメラ", 3000, 2, timezone.now() + timedelta(days=1), "active"
        ),
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
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
        unexpected = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda message: errors.append(message.text) if message.type == "error" else None,
        )

        def route_request(route):
            if urlsplit(route.request.url).hostname in {
                "localhost",
                "127.0.0.1",
                "cdn.jsdelivr.net",
                "fonts.googleapis.com",
                "fonts.gstatic.com",
            }:
                route.continue_()
            else:
                unexpected.append(route.request.url)
                route.abort()

        page.route("**/*", route_request)
        try:
            page.goto(live_server.url + reverse("profile"))
            csrf = next(
                cookie["value"] for cookie in context.cookies() if cookie["name"] == "csrftoken"
            )

            def request(name, *, args=(), method="POST", data=None):
                response = context.request.fetch(
                    live_server.url + reverse(name, args=args),
                    method=method,
                    data=data if data is not None else {},
                    headers={"X-CSRFToken": csrf},
                )
                assert response.ok, f"{name}: HTTP {response.status}"
                return response.json()

            saved = request("saved_searches", data={"name": "公開前検証", "keyword": "カメラ"})[
                "item"
            ]
            request("run_saved_search", args=(saved["id"],))
            watch = request(
                "watchlist", data={"name": "中古カメラ", "url": auction_url, "currentPrice": 2000}
            )["item"]
            price["value"] = 1500
            request("run_saved_search", args=(saved["id"],))

            def check_watch_and_notification():
                from django.db import connections

                try:
                    assert WatchItem.objects.get(pk=watch["id"]).current_price == 1500
                    assert (
                        Notification.objects.filter(
                            user_id=owner.pk, event_type="watch_price_drop"
                        ).count()
                        == 1
                    )
                finally:
                    connections.close_all()

            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(check_watch_and_notification).result()
            request("run_saved_search", args=(saved["id"],))
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(check_watch_and_notification).result()
            page.goto(live_server.url + reverse("notifications_page"))
            page.get_by_text("中古カメラ", exact=False).first.wait_for()

            inventory = request(
                "convert_watch_item_to_inventory",
                args=(watch["id"],),
                data={"acquisitionCost": 1000},
            )["item"]
            listing = request(
                "seller_listings", data={"url": auction_url, "inventoryItemId": inventory["id"]}
            )["data"]
            request("seller_listing_refresh", args=(listing["id"],))
            request(
                "seller_listing_item",
                args=(listing["id"],),
                method="PATCH",
                data={"status": "sold"},
            )
            sale = request(
                "seller_listing_sale",
                args=(listing["id"],),
                method="PUT",
                data={
                    "salePrice": 3000,
                    "actualFee": 300,
                    "actualShippingCost": 200,
                    "actualPackagingCost": 100,
                    "actualOtherCost": 0,
                    "soldAt": (timezone.now() - timedelta(minutes=1)).isoformat(),
                },
            )["data"]
            assert sale["confirmedProfit"] == 1400
            page.goto(live_server.url + "/taskle/seller-outcomes")
            page.get_by_text("公開カメラ", exact=False).first.wait_for()
            assert not errors
            assert not unexpected
        finally:
            context.close()
            browser.close()
