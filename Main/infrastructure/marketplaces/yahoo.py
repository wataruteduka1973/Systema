"""Yahoo!オークションの検索取得アダプター。"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from typing import Any, Protocol
from urllib.parse import urlencode

from Main.domain.auction_time import format_remaining_time
from Main.domain.market_listing import MarketListingObservation
from Main.infrastructure.http import get_with_retry
from Main.scraping.yahoo import YahooAuctionParser
from Main.services.exceptions import ExternalServiceError, SearchParseError
from Main.services.external_search import normalize_search_keyword
from Main.services.marketplace import MarketplaceProvider

logger = logging.getLogger("search_logger")
EXTERNAL_SERVICE_MESSAGE = "外部サービスからデータを取得できませんでした"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


class Response(Protocol):
    text: str


Fetch = Callable[..., Response]
Extract = Callable[[str], list[dict[str, Any]]]
Normalize = Callable[[object], dict[str, Any]]


def _build_url(base_url: str, parameters: Mapping[str, object]) -> str:
    return f"{base_url}?{urlencode(parameters)}"


def _listing_external_id(item: Mapping[str, Any]) -> str:
    external_id = str(item.get("auctionId") or "").strip()
    if external_id:
        return external_id
    match = re.search(
        r"/(?:auction|item)/([a-z]?\d{8,})(?:[/?#]|$)", str(item.get("url") or ""), re.I
    )
    return match.group(1) if match else ""


def _is_valid_listing(item: Mapping[str, Any]) -> bool:
    title = str(item.get("name") or "").strip()
    price = item.get("price")
    external_id = _listing_external_id(item)
    return (
        YahooAuctionParser._is_valid_title_text(title)
        and isinstance(price, (int, float))
        and not isinstance(price, bool)
        and price > 0
        and re.fullmatch(r"[a-z]?\d{8,}", external_id, re.I) is not None
    )


class YahooMarketplaceProvider:
    marketplace = "yahoo_auctions_jp"

    def __init__(
        self,
        *,
        fetch: Fetch = get_with_retry,
        extract: Extract = YahooAuctionParser.extract_listing_items,
        normalize: Normalize = YahooAuctionParser.normalize_item,
    ) -> None:
        self._fetch = fetch
        self._extract = extract
        self._normalize = normalize

    def search_closed(self, keyword: str) -> list[MarketListingObservation]:
        normalized_keyword = normalize_search_keyword(keyword)
        urls = [
            _build_url(
                "https://auctions.yahoo.co.jp/closedsearch/closedsearch",
                {
                    "p": normalized_keyword,
                    "va": normalized_keyword,
                    "b": offset,
                    "n": 100,
                    "select": 6,
                },
            )
            for offset in (1, 101)
        ]
        return self._search_pages(urls, current=False)

    def search_current(self, keyword: str) -> list[MarketListingObservation]:
        normalized_keyword = normalize_search_keyword(keyword)
        urls = [
            _build_url(
                "https://auctions.yahoo.co.jp/search/search",
                {
                    "auccat": "",
                    "tab_ex": "commerce",
                    "aq": "-",
                    "p": normalized_keyword,
                    "f": "0:1",
                    "b": offset,
                    "n": 100,
                },
            )
            for offset in (1, 101)
        ]
        return self._search_pages(urls, current=True)

    def _search_pages(self, urls: list[str], *, current: bool) -> list[MarketListingObservation]:
        observations: list[MarketListingObservation] = []
        successful_pages = 0
        for url in urls:
            try:
                response = self._fetch(url, headers=HEADERS)
                successful_pages += 1
                items = self._extract(response.text)
                if not items and not current:
                    logger.warning("No Yahoo item data extracted")
                for raw_item in items:
                    item = self._normalize(raw_item)
                    if not _is_valid_listing(item):
                        continue
                    observations.append(
                        MarketListingObservation(
                            marketplace=self.marketplace,
                            external_id=_listing_external_id(item),
                            name=str(item["name"]),
                            price=int(item["price"]),
                            start_price=int(item["startPrice"]),
                            bidding=int(item["bidding"]),
                            time=str(item["time"]),
                            url=str(item["url"]),
                        )
                    )
            except SearchParseError:
                raise
            except ExternalServiceError:
                logger.exception("Yahoo検索ページの取得に失敗しました")
                continue
            except Exception:
                logger.exception("Yahoo検索ページの解析に失敗しました")
                raise SearchParseError("検索ページを解析できませんでした") from None
        if successful_pages == 0:
            raise ExternalServiceError(EXTERNAL_SERVICE_MESSAGE)
        return observations[:200]


def closed_items(provider: MarketplaceProvider, keyword: str) -> list[dict[str, object]]:
    return [item.as_closed_item() for item in provider.search_closed(keyword)]


def current_items(provider: MarketplaceProvider, keyword: str) -> list[dict[str, object]]:
    return [
        item.as_current_item(format_remaining_time(item.time))
        for item in provider.search_current(keyword)
    ]
