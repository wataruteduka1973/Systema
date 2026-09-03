from pathlib import Path
from unittest.mock import Mock

import pytest

from Main.domain.seller_listing import money, normalize_listing_url
from Main.scraping.seller_listing import ListingParseError, fetch_listing, parse_listing

FIXTURES = Path(__file__).parents[1] / "fixtures" / "yahoo"


def test_canonical_listing_url():
    assert normalize_listing_url(
        "https://auctions.yahoo.co.jp:443/jp/auction/X1234567890/?a=1#top"
    ) == ("https://auctions.yahoo.co.jp/jp/auction/x1234567890", "x1234567890")


@pytest.mark.parametrize(
    "url",
    [
        "http://auctions.yahoo.co.jp/jp/auction/x1234567890",
        "https://auctions.yahoo.co.jp.evil.test/jp/auction/x1234567890",
        "https://user:password@auctions.yahoo.co.jp/jp/auction/x1234567890",
        "https://auctions.yahoo.co.jp:8000/jp/auction/x1234567890",
        "https://127.0.0.1/jp/auction/x1234567890",
        "https://auctions.yahoo.co.jp/search/search?x=1",
        "https://auctions.yahoo.co.jp/jp/auction/x1234567890\n",
        "https://auctions.yahoo.co.jp/jp/auction/../x1234567890",
        None,
    ],
)
def test_reject_unsafe_urls(url):
    with pytest.raises(ValueError):
        normalize_listing_url(url)


@pytest.mark.parametrize("value", [-1, True, 1.5, "NaN", "Infinity", 10**13, None, {}, ""])
def test_money_validation(value):
    with pytest.raises(ValueError):
        money(value)


@pytest.mark.parametrize(
    "filename,status,price,bids",
    [
        ("seller_detail_active.html", "active", 12000, 3),
        ("seller_detail_ended.html", "ended", 13000, 4),
    ],
)
def test_detail_fixture(filename, status, price, bids):
    result = parse_listing((FIXTURES / filename).read_text(encoding="utf-8"), "x1234567890")
    assert (result.status, result.current_price, result.bidding) == (status, price, bids)
    assert result.ends_at.tzinfo is not None


@pytest.mark.parametrize(
    "before,after",
    [
        ('"price":12000', '"otherPrice":12000'),
        ('"bids":3', '"otherCount":3'),
        ('"endTime":"2099-09-05T20:00:00+09:00"', '"endTime":"unknown"'),
        ('"auctionId":"x1234567890"', '"auctionId":"x9999999999"'),
        ('"price":12000', '"price":-1'),
        ('"bids":3', '"bids":true'),
    ],
)
def test_incomplete_or_wrong_item_is_not_zero_observation(before, after):
    html = (FIXTURES / "seller_detail_active.html").read_text(encoding="utf-8")
    with pytest.raises(ListingParseError):
        parse_listing(html.replace(before, after), "x1234567890")


def test_error_page_and_transport_cleanup(monkeypatch):
    response = Mock(text="<html>ログインしてください</html>")
    get = Mock(return_value=response)
    monkeypatch.setattr("Main.scraping.seller_listing.get_with_retry", get)
    with pytest.raises(ListingParseError):
        fetch_listing("https://auctions.yahoo.co.jp/jp/auction/x1234567890?tracking=1")
    response.close.assert_called_once()
    assert get.call_args.args[0] == "https://auctions.yahoo.co.jp/jp/auction/x1234567890"
    assert get.call_args.kwargs["max_retries"] == 1
