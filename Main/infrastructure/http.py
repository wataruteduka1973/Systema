"""外部HTTP通信の共通実装。"""

import logging
from collections.abc import Mapping

import requests

from Main.services.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


def get_with_retry(
    url: str,
    headers: Mapping[str, str],
    *,
    max_retries: int = 3,
    timeout: int = 15,
) -> requests.Response:
    """GETを再試行し、最終失敗をドメイン固有例外へ変換する。"""
    last_error: requests.RequestException | None = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("fetching external page attempt=%s/%s url=%s", attempt, max_retries, url)
            response = requests.get(url, headers=dict(headers), timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_retries:
                logger.warning("retrying external request attempt=%s url=%s", attempt, url)

    raise ExternalServiceError(f"外部ページの取得に失敗しました: {url}") from last_error
