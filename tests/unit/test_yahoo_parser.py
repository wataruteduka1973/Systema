from pathlib import Path

from Main.scraping.yahoo import YahooAuctionParser

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"


def test_yahoo_parser_rejects_ui_component_titles():
    assert not YahooAuctionParser._is_valid_title_text("Item acls")
    assert not YahooAuctionParser._is_valid_title_text("Item searchSortSelect")
    assert not YahooAuctionParser._is_valid_title_text("Item searchModeLink")
    assert not YahooAuctionParser._is_valid_title_text("Item searchListControls")
    assert not YahooAuctionParser._is_valid_title_text("Item optionFilterExpand")
    assert not YahooAuctionParser._is_valid_title_text("Item categoryFilterExpand")
    assert not YahooAuctionParser._is_valid_title_text("Item brandFilterExpand")
    assert not YahooAuctionParser._is_valid_title_text("検索条件")
    assert not YahooAuctionParser._is_valid_title_text("__next")
    assert not YahooAuctionParser._is_valid_title_text("wrapper")
    assert not YahooAuctionParser._is_valid_title_text("searchSortSelect")
    assert not YahooAuctionParser._is_valid_title_text("mediumSearchConditions")
    # Valid product titles should still pass
    assert YahooAuctionParser._is_valid_title_text("iPhone 13 Pro")
    assert YahooAuctionParser._is_valid_title_text("新品 未使用")


def test_yahoo_parser_extracts_normal_listing_from_fixture():
    html = (FIXTURE_DIR / "closed_search_sample.html").read_text(encoding="utf-8")

    items = YahooAuctionParser.extract_listing_items(html)

    assert len(items) == 1
    first = items[0]
    assert first["title"] == "テスト商品"
    assert first["price"] == 1234
    assert first["auctionId"] == "1234567890"
    assert first["url"].endswith("/jp/auction/1234567890")
    assert all(item["price"] > 0 for item in items)


def test_yahoo_parser_normalizes_missing_optional_fields():
    item = {
        "auctionId": "2345678901",
        "title": "価格なし商品",
        "url": "/jp/auction/2345678901",
    }

    normalized = YahooAuctionParser.normalize_item(item)

    assert normalized["title"] == "価格なし商品"
    assert normalized["price"] == 0
    assert normalized["bidding"] == 0
    assert normalized["url"].endswith("/jp/auction/2345678901")


def test_yahoo_parser_extracts_product_fields_from_product_cards():
    html = """
    <div class="Product" data-auction-id="z123456789">
      <a class="Product__titleLink" href="/jp/auction/z123456789">テスト商品</a>
      <span class="Product__priceValue u-textRed">1,234円</span>
      <dd class="Product__bid">3</dd>
      <span class="Product__time">10時間</span>
    </div>
    """

    items = YahooAuctionParser.extract_listing_items(html)

    assert len(items) == 1
    assert items[0]["title"] == "テスト商品"
    assert items[0]["price"] == 1234
    assert items[0]["auctionId"] == "z123456789"
    assert items[0]["url"].endswith("/jp/auction/z123456789")


def test_yahoo_parser_does_not_extract_nested_product_badges_as_items():
    html = """
    <div class="Product" data-auction-id="z123456789">
      <a class="Product__titleLink" href="/jp/auction/z123456789">HG ザクII</a>
      <span class="Product__priceValue">1,234円</span>
      <span class="Product__badge">
        <a href="/jp/auction/z123456789">送料無料</a>
      </span>
      <span class="Product__time">2日</span>
    </div>
    """

    items = YahooAuctionParser.extract_listing_items(html)

    assert len(items) == 1
    assert items[0]["title"] == "HG ザクII"
    assert items[0]["price"] == 1234


def test_yahoo_parser_rejects_search_controls_disguised_as_items():
    html = """
    <div data-item-id="acls"><h3>Item acls</h3><span>800円</span></div>
    <div data-item-id="searchListControls">
      <h3>Item searchListControls</h3><span>1,002,050,100円</span>
    </div>
    <div class="Product" data-auction-id="x123456789">
      <a class="Product__titleLink" href="/jp/auction/x123456789">実際の商品</a>
      <span class="Product__priceValue">3,000円</span>
    </div>
    """

    items = YahooAuctionParser.extract_listing_items(html)

    assert [item["title"] for item in items] == ["実際の商品"]


def test_yahoo_parser_preserves_relative_time_units():
    html = """
    <div class="Product" data-auction-id="z987654321">
      <a class="Product__titleLink" href="/jp/auction/z987654321">残り時間商品</a>
      <span class="Product__priceValue u-textRed">2,000円</span>
      <dd class="Product__bid">5</dd>
      <span class="Product__time">2日5時間20分</span>
    </div>
    """

    items = YahooAuctionParser.extract_listing_items(html)

    assert len(items) == 1
    assert items[0]["time"] == "2日5時間20分"


def test_yahoo_parser_normalizes_compound_remaining_time_units():
    assert YahooAuctionParser._normalize_time_value("3日5時間20分") == "3日5時間20分"
    assert YahooAuctionParser._normalize_time_value("5時間20分") == "5時間20分"
    assert YahooAuctionParser._normalize_time_value("1日 2時間 30分") == "1日2時間30分"


def test_format_remaining_time_returns_japanese_duration_unchanged():
    from Main.views.utils import _format_remaining_time

    assert _format_remaining_time("3日5時間20分") == "3日5時間20分"
    assert _format_remaining_time("0分") == "0分"


def test_yahoo_parser_handles_paypay_flea_market_urls():
    item = {
        "auctionId": "z631755388",
        "isFleamarketItem": True,
        "title": "フリマ商品",
        "price": 999,
        "bidCount": 2,
        "endTime": "2026-08-10T10:55:56+09:00",
    }

    normalized = YahooAuctionParser.normalize_item(item)

    assert normalized["url"] == "https://paypayfleamarket.yahoo.co.jp/item/z631755388"
