"""外部HTTP通信の共通実装。"""

import logging
from collections.abc import Mapping
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
) -> requests.Response:
    """GETを再試行し、最終失敗をドメイン固有例外へ変換する。"""
    _validate_external_url(url)
    parsed = urlsplit(url)
    safe_target = f"{parsed.hostname}{parsed.path}"
    last_error: requests.RequestException | None = None
    for attempt in range(1, max_retries + 1):
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
                content.extend(chunk)
                if len(content) > MAX_EXTERNAL_RESPONSE_BYTES:
                    response.close()
                    raise ExternalServiceError("外部ページの応答サイズが上限を超えました")
            response._content = bytes(content)
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_retries:
                logger.warning(
                    "retrying external request attempt=%s target=%s", attempt, safe_target
                )

    raise ExternalServiceError("外部ページの取得に失敗しました") from last_error
