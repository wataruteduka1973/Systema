import json

import pytest
from django.core.cache import cache
from django.test import RequestFactory, override_settings

from Main.models.searchrun import SearchRun
from Main.services.exceptions import ExternalServiceError
from Main.views import api, utils

pytestmark = pytest.mark.django_db


def test_search_rejects_overlong_keyword_without_fetch(monkeypatch):
    called = False

    def fetch(keyword):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(api, "scrape_data", fetch)
    with override_settings(EXTERNAL_SEARCH_KEYWORD_MAX_LENGTH=5):
        response = api.perform_search(
            RequestFactory().get("/taskle/perform_search", {"keyword": "123456"})
        )

    assert response.status_code == 400
    assert json.loads(response.content)["code"] == "invalid_keyword"
    assert called is False


def test_search_returns_safe_503_and_records_failure(monkeypatch):
    monkeypatch.setattr(
        api,
        "scrape_data",
        lambda keyword: (_ for _ in ()).throw(ExternalServiceError("private upstream detail")),
    )
    request = RequestFactory().get("/taskle/perform_search", {"keyword": "カメラ"})

    response = api.perform_search(request)
    payload = json.loads(response.content)

    assert response.status_code == 503
    assert payload == {
        "error": "外部サービスからデータを取得できませんでした",
        "code": "external_service_unavailable",
    }
    assert "private upstream detail" not in response.content.decode("utf-8")
    run = SearchRun.objects.get()
    assert run.succeeded is False
    assert run.duration_ms is not None
    assert run.failure_code == "external_service_unavailable"
    assert "private upstream detail" not in run.failure_code


def test_search_rate_limit_uses_429_and_retry_after(monkeypatch):
    cache.clear()
    monkeypatch.setattr(api, "scrape_data", lambda keyword: [])
    monkeypatch.setattr(api, "save_to_database", lambda keyword, items, run=None: None)
    factory = RequestFactory()
    with override_settings(
        EXTERNAL_SEARCH_RATE_LIMIT=1,
        EXTERNAL_SEARCH_RATE_WINDOW_SECONDS=30,
    ):
        first = api.perform_search(factory.get("/taskle/perform_search?keyword=test"))
        second = api.perform_search(factory.get("/taskle/perform_search?keyword=test"))

    assert first.status_code == 200
    assert second.status_code == 429
    assert second["Retry-After"] == "30"


def test_search_applies_and_records_normalized_criteria(monkeypatch):
    monkeypatch.setattr(
        api,
        "scrape_data",
        lambda keyword: [
            {"name": "中古 カメラ", "price": 2000},
            {"name": "新品 カメラ", "price": 3000},
        ],
    )
    monkeypatch.setattr(api, "save_to_database", lambda keyword, items, run=None: None)
    request = RequestFactory().get(
        "/taskle/perform_search",
        {"keyword": " カメラ ", "condition": "used", "minimumPrice": "1000"},
    )

    response = api.perform_search(request)
    payload = json.loads(response.content)
    run = SearchRun.objects.get()

    assert response.status_code == 200
    assert [item["name"] for item in payload["data"]] == ["中古 カメラ"]
    assert run.item_count == 1
    assert run.trigger == "manual"
    assert run.criteria_snapshot["keyword"] == "カメラ"
    assert run.criteria_snapshot["condition"] == "used"
    assert run.duration_ms is not None
    assert run.failure_code == ""


def test_saved_data_refresh_reuses_and_records_common_criteria(monkeypatch):
    monkeypatch.setattr(
        utils,
        "scrape_data",
        lambda keyword: [
            {"name": "中古 カメラ A", "price": 1000},
            {"name": "中古 カメラ B", "price": 3000},
        ],
    )
    monkeypatch.setattr(utils, "save_to_database", lambda keyword, items, run=None: None)
    request = RequestFactory().post(
        "/taskle/update_market_data?keyword=カメラ&minimumPrice=2000&condition=used"
    )

    response = api.update_market_data(request)
    run = SearchRun.objects.get()

    assert response.status_code == 200
    assert run.item_count == 1
    assert run.criteria_snapshot["minimumPrice"] == 2000
    assert run.criteria_snapshot["condition"] == "used"


def test_target_analysis_records_original_target_criteria_for_both_runs(monkeypatch):
    monkeypatch.setattr(
        utils,
        "scrape_data",
        lambda keyword: [{"name": "中古 落札商品", "price": 10000}],
    )
    monkeypatch.setattr(
        utils,
        "scrape_current_listings",
        lambda keyword: [
            {
                "name": "中古 現在商品",
                "currentPrice": 7000,
                "bidding": 0,
                "remainingTime": "30分",
                "url": "https://auctions.yahoo.co.jp/jp/auction/x123456789",
            }
        ],
    )
    monkeypatch.setattr(utils, "save_to_database", lambda keyword, items, run=None: None)
    request = RequestFactory().get(
        "/taskle/complex_market_data",
        {"keyword": "カメラ", "condition": "used", "endingWithinMinutes": "60"},
    )

    response = api.complex_market_data(request)
    runs = list(SearchRun.objects.order_by("search_type"))

    assert response.status_code == 200
    assert len(runs) == 2
    assert {run.search_type for run in runs} == {SearchRun.CLOSED, SearchRun.CURRENT}
    assert all(run.criteria_snapshot["searchType"] == "target" for run in runs)
    assert all(run.criteria_snapshot["endingWithinMinutes"] == 60 for run in runs)
    assert all(run.duration_ms is not None for run in runs)
    assert all(run.failure_code == "" for run in runs)


def test_target_analysis_records_current_failure_without_overwriting_closed_run(monkeypatch):
    monkeypatch.setattr(
        utils,
        "scrape_data",
        lambda keyword: [{"name": "落札商品", "price": 10000}],
    )
    monkeypatch.setattr(
        utils,
        "scrape_current_listings",
        lambda keyword: (_ for _ in ()).throw(ExternalServiceError("private detail")),
    )
    monkeypatch.setattr(utils, "save_to_database", lambda keyword, items, run=None: None)

    response = api.complex_market_data(
        RequestFactory().get("/taskle/complex_market_data", {"keyword": "カメラ"})
    )
    runs = {run.search_type: run for run in SearchRun.objects.all()}

    assert response.status_code == 503
    assert runs[SearchRun.CLOSED].succeeded is True
    assert runs[SearchRun.CLOSED].failure_code == ""
    assert runs[SearchRun.CURRENT].succeeded is False
    assert runs[SearchRun.CURRENT].failure_code == "external_service_unavailable"
    assert all(run.duration_ms is not None for run in runs.values())


def test_prediction_records_no_data_as_safe_failure(monkeypatch):
    monkeypatch.setattr(utils, "scrape_data", lambda keyword: [])

    response = api.prediction_market(
        RequestFactory().get("/taskle/prediction_market", {"keyword": "カメラ"})
    )
    run = SearchRun.objects.get()

    assert response.status_code == 404
    assert run.succeeded is False
    assert run.failure_code == "no_data"
    assert run.duration_ms is not None


@pytest.mark.parametrize(
    "handler",
    [
        api.perform_search,
        utils.update_market_data_logic,
        utils.complex_market_data_logic,
        utils.prediction_market_logic,
    ],
)
def test_parse_failure_keeps_public_503_and_records_distinct_code(monkeypatch, handler):
    from Main.services.exceptions import SearchParseError

    def fail(keyword):
        raise SearchParseError("private parser detail")

    cache.clear()
    monkeypatch.setattr(api, "scrape_data", fail)
    monkeypatch.setattr(utils, "scrape_data", fail)
    request = RequestFactory().get("/taskle/search", {"keyword": "カメラ"})
    if handler is utils.update_market_data_logic:
        request = RequestFactory().post("/taskle/search?keyword=カメラ")
    response = handler(request)
    assert response.status_code == 503
    assert json.loads(response.content)["code"] == "external_service_unavailable"
    run = SearchRun.objects.get()
    assert not run.succeeded
    assert run.failure_code == "html_parse_error"
    assert "private parser detail" not in response.content.decode()
