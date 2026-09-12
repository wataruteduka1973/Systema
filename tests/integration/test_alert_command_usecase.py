from io import StringIO
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from Main.domain.market_listing import MarketListingObservation
from Main.management.commands import run_alerts
from Main.models.notification import Notification
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.services.exceptions import ExternalServiceError

pytestmark = pytest.mark.django_db


def _observation(name: str, price: int, time: str) -> MarketListingObservation:
    return MarketListingObservation(
        marketplace="test_market",
        external_id="a123456789",
        name=name,
        price=price,
        start_price=price,
        bidding=1,
        time=time,
        url="https://auctions.yahoo.co.jp/jp/auction/a123456789",
    )


class SuccessfulProvider:
    marketplace = "test_market"

    def search_closed(self, keyword: str) -> list[MarketListingObservation]:
        return [_observation("落札カメラ", 20000, "終了")]

    def search_current(self, keyword: str) -> list[MarketListingObservation]:
        return [_observation("出品中カメラ", 10000, "30分")]


class CurrentFailureProvider(SuccessfulProvider):
    def search_current(self, keyword: str) -> list[MarketListingObservation]:
        raise ExternalServiceError("private upstream detail")


def _saved_search(username: str = "scheduled-owner") -> SavedSearch:
    user = get_user_model().objects.create_user(username)
    return SavedSearch.objects.create(user=user, name="カメラ", keyword="カメラ")


def test_run_alerts_uses_shared_usecase_and_records_scheduled_success(monkeypatch):
    saved_search = _saved_search()
    notify = Mock(wraps=run_alerts.notify_saved_search_run)
    evaluate = Mock(return_value=0)
    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", SuccessfulProvider)
    monkeypatch.setattr(run_alerts, "notify_saved_search_run", notify)
    monkeypatch.setattr(run_alerts, "evaluate_saved_search_alert_rules", evaluate)

    call_command("run_alerts", stdout=StringIO())

    runs = list(SearchRun.objects.filter(saved_search=saved_search).order_by("created_at"))
    assert [run.search_type for run in runs] == [SearchRun.CLOSED, SearchRun.CURRENT]
    assert all(run.succeeded and run.trigger == "scheduled" for run in runs)
    notification = Notification.objects.get(user=saved_search.user)
    assert notification.event_type == "saved_search_succeeded"
    assert notification.source_id == runs[-1].pk
    notify.assert_called_once_with(runs[-1])
    evaluate.assert_called_once_with(runs[-1])


def test_run_alerts_records_and_notifies_current_failure_after_closed_success(monkeypatch):
    saved_search = _saved_search("scheduled-failure")
    evaluate = Mock(return_value=0)
    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", CurrentFailureProvider)
    monkeypatch.setattr(run_alerts, "evaluate_saved_search_alert_rules", evaluate)

    call_command("run_alerts", stdout=StringIO())

    runs = {run.search_type: run for run in SearchRun.objects.filter(saved_search=saved_search)}
    assert runs[SearchRun.CLOSED].succeeded is True
    assert runs[SearchRun.CURRENT].succeeded is False
    assert runs[SearchRun.CURRENT].failure_code == "external_service_unavailable"
    notification = Notification.objects.get(user=saved_search.user)
    assert notification.event_type == "saved_search_failed"
    assert notification.source_id == runs[SearchRun.CURRENT].pk
    assert "private upstream detail" not in notification.message
    evaluate.assert_not_called()


def test_run_alerts_skips_saved_searches_owned_by_inactive_users(monkeypatch):
    saved_search = _saved_search("inactive-owner")
    saved_search.user.is_active = False
    saved_search.user.save(update_fields=("is_active",))

    def unexpected_provider():
        raise AssertionError("inactive user's search was fetched")

    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", unexpected_provider)

    call_command("run_alerts", stdout=StringIO())

    assert not SearchRun.objects.filter(saved_search=saved_search).exists()
    assert not Notification.objects.filter(user=saved_search.user).exists()


def test_run_alerts_source_has_no_http_request_or_view_dependency():
    source = run_alerts.__file__
    assert source is not None
    text = open(source, encoding="utf-8").read()
    assert "RequestFactory" not in text
    assert "Main.views" not in text
