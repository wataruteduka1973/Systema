"""Alert page: saved-search refresh status, interval, on/off and 今すぐ取得.

Yahoo retrieval is replaced with deterministic data; nothing external is contacted.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.views import utils

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _closed(keyword):
    return [
        {
            "name": f"{keyword} 落札",
            "price": 20000,
            "startPrice": 1,
            "bidding": 3,
            "time": "",
            "url": "https://auctions.yahoo.co.jp/jp/auction/c000000001",
        }
    ]


def _current(keyword):
    return [
        {
            "name": f"{keyword} 出品",
            "currentPrice": 15000,
            "bidding": 1,
            "remainingTime": "1日",
            "url": "https://auctions.yahoo.co.jp/jp/auction/n000000001",
        }
    ]


def test_refresh_status_interval_toggle_and_run_now(db_for_e2e, live_server, monkeypatch):
    monkeypatch.setattr(utils, "scrape_data", _closed)
    monkeypatch.setattr(utils, "scrape_current_listings", _current)
    user = get_user_model().objects.create_user("refresh-browser", password="password")
    healthy = SavedSearch.objects.create(user=user, name="カメラ", keyword="カメラ")
    broken = SavedSearch.objects.create(
        user=user, name="時計", keyword="時計", refresh_interval_hours=24
    )
    two_hours_ago = timezone.now() - timedelta(hours=2)
    SavedSearch.objects.filter(pk__in=[healthy.pk, broken.pk]).update(last_run_at=two_hours_ago)
    SearchRun.objects.create(
        user=user, saved_search=healthy, keyword="カメラ", search_type="current", item_count=12
    )
    SearchRun.objects.create(
        user=user,
        saved_search=broken,
        keyword="時計",
        search_type="closed",
        succeeded=False,
        failure_code="external_service_unavailable",
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(15_000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(f"{live_server.url}/accounts/login/")
            page.fill('input[name="username"]', "refresh-browser")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')
            page.goto(f"{live_server.url}/taskle/alerts")

            camera = page.locator(f'[data-saved-search-id="{healthy.pk}"]')
            watch = page.locator(f'[data-saved-search-id="{broken.pk}"]')
            expect(camera).to_contain_text("出品12件")
            # Its hourly refresh is already overdue, so no past time is shown.
            expect(camera).to_contain_text("次回予定：次の自動実行で取得")
            expect(watch).to_contain_text("取得失敗")
            expect(watch).to_contain_text("ヤフオクに接続できませんでした")
            expect(watch.locator("select")).to_have_value("24")

            camera.locator("select").select_option("6")
            expect(page.locator("#refreshMessage")).to_contain_text("取得頻度を変更しました")
            expect(page.locator(f'[data-saved-search-id="{healthy.pk}"] select')).to_have_value("6")

            # 今すぐ取得 runs the saved search once and clears the failure.
            watch.get_by_role("button", name="今すぐ取得").click()
            expect(page.locator("#refreshMessage")).to_contain_text("「時計」を取得しました")
            watch = page.locator(f'[data-saved-search-id="{broken.pk}"]')
            expect(watch).not_to_contain_text("取得失敗")
            expect(watch).to_contain_text("出品1件")

            watch.locator(f"#refreshToggle{broken.pk}").uncheck()
            watch = page.locator(f'[data-saved-search-id="{broken.pk}"]')
            expect(watch).to_contain_text("次回予定：停止中")
            expect(watch.get_by_role("button", name="今すぐ取得")).to_be_disabled()
            assert errors == []
        finally:
            browser.close()

    healthy.refresh_from_db()
    broken.refresh_from_db()
    assert healthy.refresh_interval_hours == 6
    assert broken.is_active is False
