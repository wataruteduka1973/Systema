from unittest.mock import Mock

import pytest
import requests

from Main.infrastructure import http
from Main.services.exceptions import ExternalServiceError


@pytest.mark.parametrize(
    "status,attempts", [(400, 1), (401, 1), (403, 1), (404, 1), (429, 3), (500, 3), (503, 3)]
)
def test_retry_status_policy_and_response_cleanup(monkeypatch, status, attempts):
    response = Mock(status_code=status)
    response.raise_for_status.side_effect = requests.HTTPError("private remote detail")
    fetch = Mock(return_value=response)
    monkeypatch.setattr(http.requests, "get", fetch)
    monkeypatch.setattr(http, "sleep", lambda seconds: None)
    with pytest.raises(ExternalServiceError):
        http.get_with_retry("https://auctions.yahoo.co.jp/search/search", {})
    assert fetch.call_count == attempts
    assert response.close.call_count == attempts


def test_stream_deadline_closes_response(monkeypatch):
    response = Mock(status_code=200, url="https://auctions.yahoo.co.jp/search/search", headers={})
    response.iter_content.return_value = [b"some bytes"]
    monkeypatch.setattr(http.requests, "get", lambda *args, **kwargs: response)
    ticks = iter([0, 0, 61])
    monkeypatch.setattr(http, "monotonic", lambda: next(ticks))
    with pytest.raises(ExternalServiceError, match="取得時間"):
        http.get_with_retry(response.url, {})
    response.close.assert_called_once()
