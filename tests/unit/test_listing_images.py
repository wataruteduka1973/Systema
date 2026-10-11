from pathlib import Path

import pytest

from Main.domain.listing_image import safe_image_url
from Main.domain.market_listing import MarketListingObservation
from Main.infrastructure.marketplaces.yahoo import YahooMarketplaceProvider
from Main.scraping.yahoo import YahooAuctionParser

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://auctions.c.yimg.jp/images/a/x.jpg", "https://auctions.c.yimg.jp/images/a/x.jpg"),
        ("//auc-pctr.c.yimg.jp/i/x.jpg", "https://auc-pctr.c.yimg.jp/i/x.jpg"),
        ({"url": "https://s.yimg.jp/x.png"}, "https://s.yimg.jp/x.png"),
        ("http://auctions.c.yimg.jp/x.jpg", ""),
        ("https://evil.example.com/x.jpg", ""),
        ("https://yimg.jp.evil.example.com/x.jpg", ""),
        ("https://user:pass@auctions.c.yimg.jp/x.jpg", ""),
        ("https://auctions.c.yimg.jp:8443/x.jpg", ""),
        ("javascript:alert(1)", ""),
        ("data:image/png;base64,AAAA", ""),
        ("https://auctions.c.yimg.jp/x .jpg", ""),
        (None, ""),
        ("", ""),
    ],
)
def test_safe_image_url_allows_only_https_yahoo_image_hosts(value, expected):
    assert safe_image_url(value) == expected


def _normalized(name: str) -> dict[str, dict]:
    html = (FIXTURE_DIR / name).read_text(encoding="utf-8")
    items = [
        YahooAuctionParser.normalize_item(item)
        for item in YahooAuctionParser.extract_listing_items(html)
    ]
    return {item["name"]: item for item in items}


def test_html_cards_prefer_lazy_image_and_drop_disallowed_hosts():
    items = _normalized("search_with_images.html")

    assert items["遅延読み込み画像の商品"]["imageUrl"].endswith("/c100000001-1.jpg")
    assert items["プロトコル省略画像の商品"]["imageUrl"] == (
        "https://auctions.c.yimg.jp/images/a/c100000002-1.jpg"
    )
    assert items["外部ホスト画像の商品"]["imageUrl"] == ""
    assert items["不正スキーム画像の商品"]["imageUrl"] == ""
    assert items["画像なしの商品"]["imageUrl"] == ""


def test_structured_data_images_are_read_and_validated():
    items = _normalized("search_next_data_images.html")

    assert items["構造化データ画像の商品"]["imageUrl"] == (
        "https://auctions.c.yimg.jp/images/a/d200000001-1.jpg"
    )
    assert (
        items["サムネイル辞書の商品"]["imageUrl"] == "https://auc-pctr.c.yimg.jp/i/d200000002.jpg"
    )
    assert items["許可外画像の商品"]["imageUrl"] == ""


class _Response:
    def __init__(self, text: str) -> None:
        self.text = text


def test_provider_carries_image_url_into_current_items():
    html = (FIXTURE_DIR / "search_with_images.html").read_text(encoding="utf-8")
    provider = YahooMarketplaceProvider(
        fetch=lambda url, **kwargs: _Response(html if "b=1&" in url else "")
    )

    current = {item.name: item.as_current_item("2時間") for item in provider.search_current("x")}

    assert current["遅延読み込み画像の商品"]["imageUrl"].endswith("/c100000001-1.jpg")
    assert current["画像なしの商品"]["imageUrl"] == ""


def test_observation_without_image_keeps_closed_item_contract():
    observation = MarketListingObservation("m", "a1", "n", 1, 1, 0, "t", "https://x")

    assert observation.image_url == ""
    assert "imageUrl" not in observation.as_closed_item()
