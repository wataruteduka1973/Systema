from unittest.mock import Mock

import pytest
import requests

from Main.infrastructure import http
from Main.services.exceptions import ExternalServiceError

URL = "https://auctions.yahoo.co.jp/search/search"


def _response(status=200, *, headers=None, chunks=(b"<html></html>",)):
    response = Mock(status_code=status, url=URL, headers=headers or {})
    response.iter_content.return_value = list(chunks)
    return response


@pytest.fixture
def sleeps(monkeypatch):
    calls: list[float] = []
    monkeypatch.setattr(http, "sleep", calls.append)
    return calls


@pytest.mark.parametrize(
    ("status", "attempts"),
    [(400, 1), (401, 1), (403, 1), (404, 1), (429, 3), (500, 3), (502, 3), (503, 3)],
)
def test_only_rate_limit_and_server_errors_are_retried_and_responses_closed(
    monkeypatch, sleeps, status, attempts
):
    response = _response(status)
    fetch = Mock(return_value=response)
    monkeypatch.setattr(http.requests, "get", fetch)

    with pytest.raises(ExternalServiceError):
        http.get_with_retry(URL, {})

    assert fetch.call_count == attempts
    assert response.close.call_count == attempts
    assert sleeps == [1.0, 2.0][: attempts - 1]


def test_connection_errors_are_retried_then_succeed(monkeypatch, sleeps):
    ok = _response()
    fetch = Mock(side_effect=[requests.ConnectionError("down"), requests.Timeout("slow"), ok])
    monkeypatch.setattr(http.requests, "get", fetch)

    response = http.get_with_retry(URL, {})

    assert response is ok
    assert response._content == b"<html></html>"
    assert sleeps == [1.0, 2.0]
    ok.close.assert_not_called()


def test_retry_after_is_honoured_up_to_a_cap(monkeypatch, sleeps):
    limited = _response(429, headers={"Retry-After": "7"})
    flooded = _response(429, headers={"Retry-After": "3600"})
    monkeypatch.setattr(http.requests, "get", Mock(side_effect=[limited, flooded, _response()]))

    http.get_with_retry(URL, {})

    assert sleeps == [7.0, http.MAX_RETRY_AFTER_SECONDS]


def test_failure_message_hides_remote_detail(monkeypatch, sleeps):
    monkeypatch.setattr(
        http.requests, "get", Mock(side_effect=requests.ConnectionError("private remote detail"))
    )

    with pytest.raises(ExternalServiceError) as raised:
        http.get_with_retry(URL, {})

    assert "private" not in str(raised.value)
    assert raised.value.__cause__ is None


def test_fetch_deadline_closes_response_without_retrying(monkeypatch, sleeps):
    response = _response(chunks=[b"some bytes"])
    fetch = Mock(return_value=response)
    monkeypatch.setattr(http.requests, "get", fetch)
    ticks = iter([0, 0, http.FETCH_DEADLINE_SECONDS + 1])
    monkeypatch.setattr(http, "monotonic", lambda: next(ticks))

    with pytest.raises(ExternalServiceError, match="取得時間"):
        http.get_with_retry(URL, {})

    response.close.assert_called_once()
    assert fetch.call_count == 1
    assert sleeps == []


def test_deadline_spans_attempts_and_skips_a_retry_that_cannot_finish(monkeypatch, sleeps):
    unavailable = _response(503)
    fetch = Mock(return_value=unavailable)
    monkeypatch.setattr(http.requests, "get", fetch)
    # Start of the call, then the backoff check after the first 503 is already near the limit.
    ticks = iter([0, http.FETCH_DEADLINE_SECONDS - 0.5])
    monkeypatch.setattr(http, "monotonic", lambda: next(ticks))

    with pytest.raises(ExternalServiceError, match="取得時間"):
        http.get_with_retry(URL, {})

    assert fetch.call_count == 1
    unavailable.close.assert_called_once()
    assert sleeps == []


def test_redirect_and_oversize_fail_once_and_close(monkeypatch, sleeps):
    redirect = _response(302)
    oversize = _response(headers={"Content-Length": str(http.MAX_EXTERNAL_RESPONSE_BYTES + 1)})
    fetch = Mock(side_effect=[redirect, oversize])
    monkeypatch.setattr(http.requests, "get", fetch)

    for _ in range(2):
        with pytest.raises(ExternalServiceError):
            http.get_with_retry(URL, {})

    assert fetch.call_count == 2
    redirect.close.assert_called_once()
    oversize.close.assert_called_once()
    assert sleeps == []
