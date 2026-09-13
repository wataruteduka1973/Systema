import json
from io import StringIO
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory

from Main.domain.market_listing import MarketListingObservation
from Main.management.commands import run_alerts
from Main.models.notification import Notification
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.services.exceptions import ExternalServiceError
from Main.services.saved_searches import criteria_from_saved_search
from Main.services.search_persistence import DjangoSearchRepository
from Main.views import utils

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


def test_web_and_cli_persist_identical_results_and_owner(monkeypatch):
    saved = _saved_search("parity")
    provider = SuccessfulProvider()
    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", SuccessfulProvider)
    monkeypatch.setattr(
        utils,
        "scrape_data",
        lambda keyword: [item.as_closed_item() for item in provider.search_closed(keyword)],
    )
    monkeypatch.setattr(
        utils,
        "scrape_current_listings",
        lambda keyword: [
            item.as_current_item(item.time) for item in provider.search_current(keyword)
        ],
    )
    request = RequestFactory().get("/taskle/complex_market_data")
    request.user = saved.user
    request.saved_search = saved
    request.search_trigger = "saved"
    response = utils.complex_market_data_logic(request, criteria_from_saved_search(saved))
    assert response.status_code == 200
    call_command("run_alerts", saved_search_id=saved.pk, stdout=StringIO())
    web = SearchRun.objects.get(saved_search=saved, search_type="current", trigger="saved")
    cli = SearchRun.objects.get(saved_search=saved, search_type="current", trigger="scheduled")
    assert web.result_snapshot == cli.result_snapshot == json.loads(response.content)
    fields = ("Name", "EndPrice", "StartPrice", "Bidding", "URL")
    assert list(web.items.values_list(*fields)) == list(cli.items.values_list(*fields))
    assert web.criteria_snapshot == cli.criteria_snapshot
    assert web.user_id == cli.user_id == saved.user_id
    assert web.session_key == cli.session_key == ""
    run_alerts.notify_saved_search_run(cli)
    assert (
        Notification.objects.filter(source_id=cli.pk, event_type="saved_search_succeeded").count()
        == 1
    )


def test_command_rejects_other_users_search_before_fetch(monkeypatch):
    owned = _saved_search("scope-owner")
    other = _saved_search("scope-other")
    fetch = Mock(side_effect=AssertionError("unexpected fetch"))
    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", fetch)
    with pytest.raises(CommandError):
        call_command("run_alerts", user_id=owned.user_id, saved_search_id=other.pk)
    fetch.assert_not_called()
    assert not SearchRun.objects.exists()


def test_invalid_saved_criteria_does_not_abort_later_searches(monkeypatch):
    invalid = _saved_search("invalid-criteria")
    invalid.keyword = ""
    invalid.name = "aaa"
    invalid.save()
    valid = _saved_search("valid-criteria")
    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", SuccessfulProvider)
    output, errors = StringIO(), StringIO()
    call_command("run_alerts", stdout=output, stderr=errors)
    assert "failed=1" in output.getvalue()
    assert SearchRun.objects.filter(saved_search=valid, succeeded=True).count() == 2
    invalid.refresh_from_db()
    assert invalid.last_run_at is not None


def test_snapshot_failure_marks_existing_current_run_failed(monkeypatch):
    saved = _saved_search("snapshot-failure")
    monkeypatch.setattr(run_alerts, "YahooMarketplaceProvider", SuccessfulProvider)

    def fail(*args, **kwargs):
        raise ValueError("private snapshot detail")

    monkeypatch.setattr(DjangoSearchRepository, "save_result_snapshot", fail)
    call_command("run_alerts", stdout=StringIO())
    assert SearchRun.objects.filter(saved_search=saved).count() == 2
    current = SearchRun.objects.get(saved_search=saved, search_type="current")
    assert current.succeeded is False
    assert current.failure_code == "unexpected_error"
    assert Notification.objects.get(user=saved.user).event_type == "saved_search_failed"
