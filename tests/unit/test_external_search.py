from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.cache import cache
from django.test import RequestFactory, override_settings

from Main.infrastructure.http import get_with_retry
from Main.services.exceptions import ExternalServiceError, SearchInputError, SearchRateLimitError
from Main.services.external_search import enforce_search_rate_limit, normalize_search_keyword
from Main.views import utils


def test_keyword_is_normalized_and_limited():
    assert normalize_search_keyword("  カメラ　 レンズ  ") == "カメラ レンズ"

    with pytest.raises(SearchInputError):
        normalize_search_keyword("bad\nkeyword")
    with override_settings(EXTERNAL_SEARCH_KEYWORD_MAX_LENGTH=3):
        with pytest.raises(SearchInputError):
            normalize_search_keyword("1234")


def test_external_search_rate_limit_returns_retry_window():
    cache.clear()
    request = RequestFactory().get("/taskle/perform_search", REMOTE_ADDR="192.0.2.10")
    with override_settings(
        EXTERNAL_SEARCH_RATE_LIMIT=2,
        EXTERNAL_SEARCH_RATE_WINDOW_SECONDS=45,
    ):
        enforce_search_rate_limit(request)
        enforce_search_rate_limit(request)
        with pytest.raises(SearchRateLimitError) as captured:
            enforce_search_rate_limit(request)

    assert captured.value.retry_after == 45


def test_scrape_data_encodes_keyword_as_query_parameters(monkeypatch):
    requested_urls = []

    def fake_request(url, headers, max_retries=3, timeout=15):
        requested_urls.append(url)
        return SimpleNamespace(text="")

    monkeypatch.setattr(utils, "_request_with_retry", fake_request)
    monkeypatch.setattr(utils, "_extract_listing_items", lambda html: [])

    assert utils.scrape_data("カメラ & レンズ") == []
    query = parse_qs(urlsplit(requested_urls[0]).query)
    assert query["p"] == ["カメラ & レンズ"]
    assert query["va"] == ["カメラ & レンズ"]
    assert query["b"] == ["1"]


def test_scrape_data_raises_when_every_page_fetch_fails(monkeypatch):
    def fail_request(url, headers, max_retries=3, timeout=15):
        raise ExternalServiceError("upstream failed")

    monkeypatch.setattr(utils, "_request_with_retry", fail_request)

    with pytest.raises(ExternalServiceError):
        utils.scrape_data("カメラ")


def test_http_client_rejects_non_yahoo_destination():
    with pytest.raises(ExternalServiceError):
        get_with_retry("https://example.com/", headers={})


def test_http_client_does_not_follow_redirects(monkeypatch):
    response = SimpleNamespace(
        status_code=302,
        url="https://auctions.yahoo.co.jp/redirect",
        headers={"Location": "http://127.0.0.1/private"},
        close=lambda: None,
    )
    monkeypatch.setattr("Main.infrastructure.http.requests.get", lambda *args, **kwargs: response)

    with pytest.raises(ExternalServiceError):
        get_with_retry("https://auctions.yahoo.co.jp/search/search", headers={})


@pytest.mark.parametrize("scrape", [utils.scrape_data, utils.scrape_current_listings])
def test_malformed_search_fixture_is_not_reported_as_success(monkeypatch, scrape):
    from pathlib import Path

    from Main.services.exceptions import SearchParseError

    fixture = Path(__file__).resolve().parents[1] / "fixtures/yahoo/search_malformed_payload.html"
    monkeypatch.setattr(
        utils,
        "_request_with_retry",
        lambda *args, **kwargs: SimpleNamespace(text=fixture.read_text(encoding="utf-8")),
    )
    with pytest.raises(SearchParseError):
        scrape("private-query")


@pytest.mark.parametrize("scrape", [utils.scrape_data, utils.scrape_current_listings])
def test_parser_exception_is_not_swallowed(monkeypatch, scrape):
    from Main.services.exceptions import SearchParseError

    monkeypatch.setattr(
        utils, "_request_with_retry", lambda *args, **kwargs: SimpleNamespace(text="html")
    )

    def fail(html):
        raise ValueError("private-query")

    monkeypatch.setattr(utils, "_extract_listing_items", fail)
    with pytest.raises(SearchParseError):
        scrape("private-query")
