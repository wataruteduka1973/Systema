from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from Main.models.alertrule import AlertRule
from Main.models.notification import Notification
from Main.models.purchasebudget import CostSettings
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.models.sellerlisting import SellerListing, SellerListingSnapshot
from Main.models.watchitem import WatchItem, WatchPriceSnapshot
from Main.services.alert_rules import (
    evaluate_saved_search_alert_rules,
    evaluate_seller_alert_rules,
    evaluate_watch_alert_rules,
)

pytestmark = pytest.mark.integration


def _watch(user, *, name="候補", price=3000, median=5000, bidding=1, score=80):
    return WatchItem.objects.create(
        user=user,
        name=name,
        url="https://auctions.yahoo.co.jp/jp/auction/test-alert",
        current_price=price,
        added_price=price,
        market_median=median,
        bidding=bidding,
        buy_score=score,
    )


def _saved_run(saved_search, items):
    return SearchRun.objects.create(
        user=saved_search.user,
        saved_search=saved_search,
        keyword=saved_search.keyword,
        search_type=SearchRun.CURRENT,
        item_count=len(items),
        succeeded=True,
        trigger="saved",
        result_snapshot={"medianPrice": 5000, "recommend_items": items},
    )


def _candidate(url, *, price=3000, score=80):
    return {
        "name": "中古カメラ",
        "url": url,
        "price": price,
        "bidding": 1,
        "remainingSeconds": 1800,
        "buyDecision": {"score": score, "label": "買い時", "reason": "割安"},
    }


def _listing(user):
    return SellerListing.objects.create(
        user=user,
        external_listing_id="seller-alert",
        url="https://auctions.yahoo.co.jp/jp/auction/seller-alert",
        name="出品商品",
        status="active",
        last_checked_at=timezone.now(),
    )


def _seller_snapshot(listing, *, observed_at, bids, median, profit, remaining=1800):
    return SellerListingSnapshot.objects.create(
        seller_listing=listing,
        current_price=5000,
        bidding=bids,
        remaining_seconds=remaining,
        market_median=median,
        predicted_sale_price=5000,
        estimated_fee=500,
        estimated_profit=profit,
        observed_status="active",
        observed_at=observed_at,
    )


@pytest.mark.django_db
def test_alert_rule_crud_is_owner_scoped_and_page_lists_only_owned_targets(client):
    user = get_user_model().objects.create_user("alerts-owner", password="password")
    other = get_user_model().objects.create_user("alerts-other", password="password")
    watch = _watch(user)
    other_watch = _watch(other, name="他人の非公開商品")
    client.force_login(user)

    created = client.post(
        reverse("alert_rules"),
        {
            "watchItemId": watch.pk,
            "ruleType": "price_below",
            "thresholdValue": "3500",
            "cooldownMinutes": 60,
        },
        content_type="application/json",
    )
    assert created.status_code == 201
    rule_id = created.json()["item"]["id"]
    assert created.json()["item"]["targetLabel"] == "候補"

    denied = client.post(
        reverse("alert_rules"),
        {
            "watchItemId": other_watch.pk,
            "ruleType": "price_below",
            "thresholdValue": 1,
            "cooldownMinutes": 60,
        },
        content_type="application/json",
    )
    assert denied.status_code == 400
    assert client.get(reverse("alert_rule_item", args=[rule_id])).status_code == 200
    changed = client.patch(
        reverse("alert_rule_item", args=[rule_id]),
        {"isEnabled": False, "thresholdValue": 3200},
        content_type="application/json",
    )
    assert changed.status_code == 200 and changed.json()["item"]["isEnabled"] is False
    page = client.get(reverse("alert_rules_page"))
    listed_targets = page.context["alert_targets"]["watchItem"]
    assert listed_targets == [{"id": watch.pk, "label": "候補"}]
    assert client.delete(reverse("alert_rule_item", args=[rule_id])).status_code == 204


@pytest.mark.django_db
def test_alert_api_requires_login_and_rejects_invalid_target_rule(client):
    user = get_user_model().objects.create_user("alerts-validation", password="password")
    watch = _watch(user)
    assert client.get(reverse("alert_rules")).status_code == 401
    client.force_login(user)
    response = client.post(
        reverse("alert_rules"),
        {
            "watchItemId": watch.pk,
            "ruleType": "market_decline",
            "thresholdValue": 10,
            "cooldownMinutes": 60,
        },
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_watch_rules_create_one_notification_during_cooldown():
    user = get_user_model().objects.create_user("alerts-watch", password="password")
    watch = _watch(user)
    AlertRule.objects.create(
        user=user,
        watch_item=watch,
        rule_type="median_discount",
        threshold_value=30,
        cooldown_minutes=60,
    )

    assert evaluate_watch_alert_rules(watch, remaining_seconds=1800) == 1
    assert evaluate_watch_alert_rules(watch, remaining_seconds=1800) == 0
    notification = Notification.objects.get(user=user, event_type="alert_median_discount")
    assert notification.payload["marketMedian"] == 5000
    assert notification.payload["observedAt"]


@pytest.mark.django_db
def test_saved_search_new_listing_skips_first_run_and_budget_includes_evidence():
    user = get_user_model().objects.create_user("alerts-search", password="password")
    saved = SavedSearch.objects.create(user=user, name="カメラ", keyword="camera")
    new_rule = AlertRule.objects.create(
        user=user,
        saved_search=saved,
        rule_type="new_listing",
        threshold_value=0,
        cooldown_minutes=60,
    )
    AlertRule.objects.create(
        user=user,
        saved_search=saved,
        rule_type="within_budget",
        threshold_value=0,
        cooldown_minutes=60,
    )
    CostSettings.objects.create(
        user=user,
        assumptions={
            "feeRate": "0.10",
            "purchaseShipping": 0,
            "shippingCost": 500,
            "packagingCost": 0,
            "otherCost": 0,
            "targetProfit": 500,
        },
    )

    first = _saved_run(saved, [_candidate("https://auctions.yahoo.co.jp/jp/auction/a")])
    assert evaluate_saved_search_alert_rules(first) == 1
    assert not Notification.objects.filter(source_id=new_rule.pk).exists()
    second = _saved_run(
        saved,
        [
            _candidate("https://auctions.yahoo.co.jp/jp/auction/a"),
            _candidate("https://auctions.yahoo.co.jp/jp/auction/b"),
        ],
    )
    assert evaluate_saved_search_alert_rules(second) == 1
    notification = Notification.objects.get(source_id=new_rule.pk)
    assert notification.payload["candidateCount"] == 1
    assert notification.payload["candidates"][0]["url"].endswith("/b")


@pytest.mark.django_db
def test_failed_saved_search_never_creates_alert_notification():
    user = get_user_model().objects.create_user("alerts-failed", password="password")
    saved = SavedSearch.objects.create(user=user, name="失敗条件", keyword="camera")
    AlertRule.objects.create(
        user=user,
        saved_search=saved,
        rule_type="price_below",
        threshold_value=5000,
        cooldown_minutes=60,
    )
    run = _saved_run(saved, [_candidate("https://auctions.yahoo.co.jp/jp/auction/a")])
    run.succeeded = False
    run.save(update_fields=("succeeded",))
    assert evaluate_saved_search_alert_rules(run) == 0
    assert not Notification.objects.exists()


@pytest.mark.django_db
def test_seller_rules_use_persisted_snapshots_for_decline_stall_and_profit():
    user = get_user_model().objects.create_user("alerts-seller", password="password")
    listing = _listing(user)
    for rule_type, threshold in (
        ("bid_stalled", 24),
        ("ending_without_bids", 60),
        ("loss_risk", 500),
        ("market_decline", 10),
    ):
        AlertRule.objects.create(
            user=user,
            seller_listing=listing,
            rule_type=rule_type,
            threshold_value=threshold,
            cooldown_minutes=60,
        )
    now = timezone.now()
    _seller_snapshot(
        listing, observed_at=now - timedelta(hours=25), bids=0, median=6000, profit=-100
    )
    _seller_snapshot(listing, observed_at=now, bids=0, median=5000, profit=-600)

    assert evaluate_seller_alert_rules(listing) == 4
    assert set(Notification.objects.values_list("event_type", flat=True)) == {
        "alert_bid_stalled",
        "alert_ending_without_bids",
        "alert_loss_risk",
        "alert_market_decline",
    }


@pytest.mark.django_db
def test_evaluate_only_command_uses_persisted_state_without_refresh(capsys):
    user = get_user_model().objects.create_user("alerts-command", password="password")
    watch = _watch(user)
    WatchPriceSnapshot.objects.create(
        watch_item=watch,
        price=watch.current_price,
        bidding=watch.bidding,
        remaining_seconds=1800,
    )
    AlertRule.objects.create(
        user=user,
        watch_item=watch,
        rule_type="price_below",
        threshold_value=3000,
        cooldown_minutes=60,
    )

    call_command("run_alerts", "--evaluate-only", "--user-id", str(user.pk))
    assert "notifications_created=1" in capsys.readouterr().out
