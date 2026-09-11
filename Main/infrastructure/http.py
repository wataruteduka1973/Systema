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
    total_timeout: int = 60,
) -> requests.Response:
    """GETを再試行し、最終失敗をドメイン固有例外へ変換する。"""
    _validate_external_url(url)
    if max_retries < 1 or timeout < 1 or total_timeout < 1:
        raise ValueError("HTTP attempt and timeout limits must be positive")
    parsed = urlsplit(url)
    safe_target = f"{parsed.hostname}{parsed.path}"
    last_error: requests.RequestException | None = None
    deadline = monotonic() + total_timeout
    for attempt in range(1, max_retries + 1):
        response = None
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
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
                timeout=min(timeout, remaining),
                allow_redirects=False,
                stream=True,
            )
            if 300 <= response.status_code < 400:
                raise ExternalServiceError("外部ページから予期しない転送応答を受信しました")
            response.raise_for_status()
            _validate_external_url(response.url)
            content_length = response.headers.get("Content-Length")
            try:
                declared_size = int(content_length) if content_length else None
            except ValueError:
                declared_size = None
            if declared_size is not None and declared_size > MAX_EXTERNAL_RESPONSE_BYTES:
                response.close()
                raise ExternalServiceError("外部ページの応答サイズが上限を超えました")
            content = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if monotonic() >= deadline:
                    raise ExternalServiceError("外部ページの取得時間が上限を超えました")
                content.extend(chunk)
                if len(content) > MAX_EXTERNAL_RESPONSE_BYTES:
                    response.close()
                    raise ExternalServiceError("外部ページの応答サイズが上限を超えました")
            response._content = bytes(content)
            return response
        except requests.RequestException as exc:
            last_error = exc
            retryable = isinstance(exc, (requests.Timeout, requests.ConnectionError)) or (
                isinstance(exc, requests.HTTPError)
                and response is not None
                and (response.status_code == 429 or 500 <= response.status_code < 600)
            )
            if not retryable:
                break
            if attempt < max_retries:
                logger.warning(
                    "retrying external request attempt=%s target=%s", attempt, safe_target
                )
                sleep(max(0, min(2 ** (attempt - 1), deadline - monotonic())))
        finally:
            if response is not None:
                response.close()

    raise ExternalServiceError("外部ページの取得に失敗しました") from last_error
