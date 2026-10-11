"""外部HTTP通信の共通実装。"""

import logging
from collections.abc import Mapping
from time import monotonic, sleep
from urllib.parse import urlsplit

import requests

from Main.services.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)
ALLOWED_EXTERNAL_HOSTS = {"auctions.yahoo.co.jp"}
MAX_EXTERNAL_RESPONSE_BYTES = 5 * 1024 * 1024
# Only rate limiting and server-side failures are worth repeating; other 4xx answers will not
# change on a retry and repeating them only adds load on the remote site.
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRY_BACKOFF_SECONDS = (1.0, 2.0, 4.0)
MAX_RETRY_AFTER_SECONDS = 10.0
# Whole-attempt budget. `timeout` only bounds each socket wait, so a slow trickle of chunks
# could otherwise keep one fetch open indefinitely.
FETCH_DEADLINE_SECONDS = 60.0


class _RetryableFetchError(Exception):
    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__("retryable external fetch failure")
        self.retry_after = retry_after


def _retry_after_seconds(response: requests.Response) -> float | None:
    value = response.headers.get("Retry-After") if response.headers else None
    try:
        return min(max(float(value), 0.0), MAX_RETRY_AFTER_SECONDS) if value else None
    except (TypeError, ValueError):
        return None


def _backoff_seconds(attempt: int, retry_after: float | None) -> float:
    base = RETRY_BACKOFF_SECONDS[min(attempt - 1, len(RETRY_BACKOFF_SECONDS) - 1)]
    return max(base, retry_after or 0.0)


def _validate_external_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_EXTERNAL_HOSTS:
        raise ExternalServiceError("許可されていない外部URLです")


def get_with_retry(
    url: str,
    headers: Mapping[str, str],
    *,
    max_retries: int = 3,
    timeout: int = 15,
) -> requests.Response:
    """GET with bounded retries; every failure becomes ExternalServiceError.

    Connection errors, timeouts and 429/5xx are retried with backoff (honouring a short
    Retry-After). Other 4xx, redirects, oversize bodies fail at once. The total deadline
    covers every attempt and backoff; a retry that cannot start within it is not made. A response that is not returned is always closed.
    """
    _validate_external_url(url)
    parsed = urlsplit(url)
    safe_target = f"{parsed.hostname}{parsed.path}"
    started = monotonic()
    for attempt in range(1, max_retries + 1):
        response: requests.Response | None = None
        try:
            logger.info(
                "fetching external page attempt=%s/%s target=%s",
                attempt,
                max_retries,
                safe_target,
            )
            response = requests.get(
                url,
                headers=dict(headers),
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            )
            if 300 <= response.status_code < 400:
                raise ExternalServiceError("外部ページから予期しない転送応答を受信しました")
            if response.status_code >= 400:
                if response.status_code in RETRYABLE_STATUS_CODES:
                    raise _RetryableFetchError(_retry_after_seconds(response))
                raise ExternalServiceError("外部ページの取得に失敗しました")
            _validate_external_url(response.url)
            content_length = response.headers.get("Content-Length")
            try:
                declared_size = int(content_length) if content_length else None
            except ValueError:
                declared_size = None
            if declared_size is not None and declared_size > MAX_EXTERNAL_RESPONSE_BYTES:
                raise ExternalServiceError("外部ページの応答サイズが上限を超えました")
            content = bytearray()
            _check_deadline(started)
            for chunk in response.iter_content(chunk_size=64 * 1024):
                content.extend(chunk)
                if len(content) > MAX_EXTERNAL_RESPONSE_BYTES:
                    raise ExternalServiceError("外部ページの応答サイズが上限を超えました")
                _check_deadline(started)
            response._content = bytes(content)
            return response
        except (_RetryableFetchError, requests.RequestException) as error:
            if response is not None:
                response.close()
            if attempt >= max_retries:
                raise ExternalServiceError("外部ページの取得に失敗しました") from None
            retry_after = error.retry_after if isinstance(error, _RetryableFetchError) else None
            delay = _backoff_seconds(attempt, retry_after)
            if monotonic() - started + delay > FETCH_DEADLINE_SECONDS:
                raise ExternalServiceError("外部ページの取得時間が上限を超えました") from None
            logger.warning(
                "retrying external request attempt=%s target=%s delay=%.1fs",
                attempt,
                safe_target,
                delay,
            )
            sleep(delay)
        except ExternalServiceError:
            if response is not None:
                response.close()
            raise

    raise ExternalServiceError("外部ページの取得に失敗しました")


def _check_deadline(started: float) -> None:
    if monotonic() - started > FETCH_DEADLINE_SECONDS:
        raise ExternalServiceError("外部ページの取得時間が上限を超えました")
