from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from Main.infrastructure.marketplaces.yahoo import YahooMarketplaceProvider
from Main.services.exceptions import ExternalServiceError


def _normalized_item(raw):
    return {
        "name": raw["name"],
        "price": 12000,
        "startPrice": 8000,
        "bidding": 4,
        "time": "残り30分",
        "url": "https://auctions.yahoo.co.jp/jp/auction/a123456789",
        "auctionId": "a123456789",
    }


def test_yahoo_provider_normalizes_closed_and_current_through_one_contract():
    requested_urls = []

    def fetch(url, headers):
        requested_urls.append(url)
        return SimpleNamespace(text="fixture")

    provider = YahooMarketplaceProvider(
        fetch=fetch,
        extract=lambda html: [{"name": "中古カメラ"}],
        normalize=_normalized_item,
    )

    closed = provider.search_closed("カメラ & レンズ")
    current = provider.search_current("カメラ & レンズ")

    assert len(closed) == 2
    assert len(current) == 2
    assert closed[0] == current[0]
    assert closed[0].marketplace == "yahoo_auctions_jp"
    assert closed[0].external_id == "a123456789"
    closed_query = parse_qs(urlsplit(requested_urls[0]).query)
    current_query = parse_qs(urlsplit(requested_urls[2]).query)
    assert closed_query["p"] == ["カメラ & レンズ"]
    assert closed_query["va"] == ["カメラ & レンズ"]
    assert current_query["p"] == ["カメラ & レンズ"]


def test_yahoo_provider_fails_only_when_every_page_fetch_fails():
    provider = YahooMarketplaceProvider(
        fetch=lambda *args, **kwargs: (_ for _ in ()).throw(ExternalServiceError("private")),
        extract=lambda html: [],
        normalize=_normalized_item,
    )

    with pytest.raises(ExternalServiceError, match="外部サービス"):
        provider.search_closed("カメラ")


def test_yahoo_provider_derives_external_id_from_public_url():
    def normalize_without_id(raw):
        item = _normalized_item(raw)
        item.pop("auctionId")
        return item

    provider = YahooMarketplaceProvider(
        fetch=lambda *args, **kwargs: SimpleNamespace(text="fixture"),
        extract=lambda html: [{"name": "中古カメラ"}],
        normalize=normalize_without_id,
    )

    assert provider.search_current("カメラ")[0].external_id == "a123456789"
