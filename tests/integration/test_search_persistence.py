import json

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.models.searchwordlog import searchwordlog
from Main.views import api


def _closed_items():
    return [
        {
            "name": "中古 商品A",
            "price": 2000,
            "startPrice": 1000,
            "bidding": 3,
            "time": "2026-09-01T10:00:00+09:00",
            "url": "https://auctions.yahoo.co.jp/jp/auction/a123456789",
        },
        {
            "name": "新品 商品B",
            "price": 4000,
            "startPrice": 2000,
            "bidding": 5,
            "time": "2026-09-02T10:00:00+09:00",
            "url": "https://auctions.yahoo.co.jp/jp/auction/b123456789",
        },
    ]


@pytest.mark.django_db
def test_closed_search_contract_persists_owned_success_and_legacy_response(monkeypatch):
    factory = RequestFactory()
    user = get_user_model().objects.create_user(username="contract-owner")
    request = factory.get("/taskle/perform_search?keyword=console")
    request.user = user
    monkeypatch.setattr(api, "scrape_data", lambda keyword: _closed_items())

    response = api.perform_search(request)

    payload = json.loads(response.content)
    assert response.status_code == 200
    assert set(payload) == {"data", "conditionSummary", "marketStatistics"}
    assert [item["name"] for item in payload["data"]] == ["中古 商品A", "新品 商品B"]
    run = SearchRun.objects.get()
    assert run.user == user
    assert run.session_key == ""
    assert run.keyword == "console"
    assert run.search_type == SearchRun.CLOSED
    assert run.item_count == 2
    assert run.succeeded is True
    assert run.failure_code == ""
    assert run.trigger == "manual"
    assert run.criteria_snapshot["keyword"] == "console"
    assert list(run.items.values_list("Name", flat=True)) == ["中古 商品A", "新品 商品B"]
    assert list(searchwordlog.objects.values_list("user", "word")) == [(user.pk, "console")]
    assert request.recorded_search_runs == [run]

    other_user = get_user_model().objects.create_user(username="other-owner")
    other_request = factory.get("/taskle/get_market_data?keyword=console")
    other_request.user = other_user
    other_response = api.get_market_data(other_request)
    assert other_response.status_code == 200
    assert json.loads(other_response.content)["data"] == []
    assert SearchRun.objects.filter(user=user).count() == 1


@pytest.mark.django_db(transaction=True)
def test_closed_search_rolls_back_success_when_item_persistence_fails(monkeypatch):
    factory = RequestFactory()
    user = get_user_model().objects.create_user(username="persistence-owner")
    request = factory.get("/taskle/perform_search?keyword=console")
    request.user = user
    monkeypatch.setattr(api, "scrape_data", lambda keyword: _closed_items())

    def fail_after_first_row(rows, *args, **kwargs):
        first = rows[0]
        scraping.objects.create(
            search_run=first.search_run,
            SearchWord=first.SearchWord,
            SearchDay=first.SearchDay,
            Name=first.Name,
            EndPrice=first.EndPrice,
            StartPrice=first.StartPrice,
            Bidding=first.Bidding,
            URL=first.URL,
        )
        raise RuntimeError("injected persistence failure")

    monkeypatch.setattr(scraping.objects, "bulk_create", fail_after_first_row)

    response = api.perform_search(request)

    assert response.status_code == 500
    assert json.loads(response.content) == {
        "error": "検索処理中にエラーが発生しました",
        "code": "search_failed",
    }
    assert scraping.objects.count() == 0
    run = SearchRun.objects.get()
    assert run.user == user
    assert run.keyword == "console"
    assert run.item_count == 0
    assert run.succeeded is False
    assert run.failure_code == "unexpected_error"
    assert list(searchwordlog.objects.values_list("user", "word")) == [(user.pk, "console")]
    assert request.recorded_search_runs == [run]
