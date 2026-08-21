import json

import pytest
from django.core.cache import cache
from django.test import RequestFactory, override_settings

from Main.models.searchrun import SearchRun
from Main.services.exceptions import ExternalServiceError
from Main.views import api

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
    assert SearchRun.objects.get().succeeded is False


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
