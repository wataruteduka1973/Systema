"""Readable notifications (filters, formatted candidates) and grouped alert rules with toggles."""

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import expect, sync_playwright

from Main.models.alertrule import AlertRule
from Main.models.savedsearch import SavedSearch
from Main.models.watchitem import WatchItem
from Main.services.notifications import create_notification

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _candidate(index):
    return {
        "name": f"ミラーレス 本体 中古 {index}",
        "url": f"https://auctions.yahoo.co.jp/jp/auction/c{index:09d}",
        "currentPrice": 38000,
        "marketMedian": 50000,
        "differenceRate": -24.0,
        "imageUrl": "https://auctions.c.yimg.jp/images/x.jpg",
        "observedAt": "2026-10-13T09:00:00+09:00",
    }


def test_notifications_and_alert_rules_are_readable(db_for_e2e, live_server):
    user = get_user_model().objects.create_user("readable", password="password")
    camera = SavedSearch.objects.create(user=user, name="ミラーレス", keyword="ミラーレス")
    watch = WatchItem.objects.create(
        user=user, name="時計 本体", url="https://auctions.yahoo.co.jp/jp/auction/w000000001"
    )
    AlertRule.objects.create(
        user=user, saved_search=camera, rule_type="price_below", threshold_value=25000
    )
    AlertRule.objects.create(
        user=user, saved_search=camera, rule_type="median_discount", threshold_value=20
    )
    paused = AlertRule.objects.create(
        user=user, watch_item=watch, rule_type="ending_soon", threshold_value=60
    )
    create_notification(
        user=user,
        event_type="saved_search_succeeded",
        title="今日の保存検索の更新（10/13）",
        message="保存検索1件を計3回更新しました。最新は「ミラーレス」の40件です。",
        dedupe_key="daily",
        source_type="search_run",
        source_id=None,
        payload={
            "searches": {
                "1": {
                    "name": "ミラーレス",
                    "itemCount": 40,
                    "lastRunAt": "2026-10-13T09:00:00+09:00",
                }
            }
        },
    )
    create_notification(
        user=user,
        event_type="alert_median_discount",
        title="ミラーレス：相場との差が指定率以上",
        message="保存検索「ミラーレス」で5件が「相場との差が指定率以上」に一致しました。",
        dedupe_key="alert",
        source_type="alert_rule",
        source_id=None,
        payload={"candidateCount": 5, "candidates": [_candidate(i) for i in range(5)]},
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(10_000)
        page.route(
            "https://*.yimg.jp/**",
            lambda route: route.fulfill(
                status=200,
                content_type="image/svg+xml",
                body="<svg xmlns='http://www.w3.org/2000/svg'/>",
            ),
        )
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(f"{live_server.url}/accounts/login/")
            page.fill('input[name="username"]', "readable")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')

            page.goto(f"{live_server.url}/taskle/notifications")
            cards = page.locator("#notificationList article")
            expect(cards).to_have_count(2)
            alert = cards.filter(has_text="ミラーレス：相場との差が指定率以上")
            expect(alert.locator(".notification-candidate")).to_have_count(3)
            first = alert.locator(".notification-candidate").first
            expect(first).to_contain_text("現在価格 38,000円 / 相場中央値 50,000円")
            expect(first.locator(".compare-chip")).to_have_text("相場比 -24%")
            expect(first.locator("img")).to_have_attribute(
                "src", "https://auctions.c.yimg.jp/images/x.jpg"
            )
            expect(first.locator("a.candidate-name")).to_have_attribute(
                "href", "https://auctions.yahoo.co.jp/jp/auction/c000000000"
            )
            expect(alert).to_contain_text("ほか2件があります")
            expect(cards.filter(has_text="今日の保存検索の更新")).to_contain_text(
                "ミラーレス：40件"
            )

            page.locator('#notificationCategories [data-category="alert"]').click()
            expect(cards).to_have_count(1)
            expect(cards.first).to_contain_text("ミラーレス：相場との差が指定率以上")
            page.locator('#notificationCategories [data-category="update"]').click()
            expect(cards).to_have_count(1)
            expect(cards.first).to_contain_text("今日の保存検索の更新")

            page.goto(f"{live_server.url}/taskle/alerts")
            groups = page.locator("#alertRuleList .alert-target-group")
            expect(groups).to_have_count(2)
            expect(groups.first).to_contain_text("保存検索ミラーレス2件")
            expect(groups.first).to_contain_text("しきい値：25,000円")
            expect(groups.first).to_contain_text("しきい値：20%")
            expect(groups.nth(1)).to_contain_text("ウォッチ商品時計 本体1件")
            expect(groups.nth(1)).to_contain_text("まだ通知していません")

            page.locator(f"#alertToggle{paused.pk}").uncheck()
            expect(page.locator(f'[data-rule-id="{paused.pk}"]')).to_contain_text("停止中")

            # New rules start from a suggested threshold per condition; prices are left to the user.
            page.select_option("#alertTargetType", "savedSearch")
            page.select_option("#alertRuleType", "median_discount")
            expect(page.locator("#alertThreshold")).to_have_value("20")
            page.select_option("#alertRuleType", "price_below")
            expect(page.locator("#alertThreshold")).to_have_value("")
            assert errors == []
        finally:
            browser.close()

    paused.refresh_from_db()
    assert paused.is_enabled is False
