import json
from pathlib import Path

from Main.scraping.yahoo import YahooAuctionParser


FIXTURE_DIR = Path(__file__).resolve().parent / 'fixtures' / 'yahoo'


def test_yahoo_parser_extracts_normal_listing_from_fixture():
    html = (FIXTURE_DIR / 'closed_search_sample.html').read_text(encoding='utf-8')

    items = YahooAuctionParser.extract_listing_items(html)

    assert len(items) >= 2
    first = items[0]
    assert first['title'] == 'テスト商品'
    assert first['price'] == 1234
    assert first['auctionId'] == '1234567890'
    assert first['url'].endswith('/jp/auction/1234567890')


def test_yahoo_parser_normalizes_missing_optional_fields():
    item = {
        'auctionId': '2345678901',
        'title': '価格なし商品',
        'url': '/jp/auction/2345678901',
    }

    normalized = YahooAuctionParser.normalize_item(item)

    assert normalized['title'] == '価格なし商品'
    assert normalized['price'] == 0
    assert normalized['bidding'] == 0
    assert normalized['url'].endswith('/jp/auction/2345678901')


def test_yahoo_parser_extracts_product_fields_from_product_cards():
    html = '''
    <div class="Product" data-auction-id="z123456789">
      <a class="Product__titleLink" href="/jp/auction/z123456789">テスト商品</a>
      <span class="Product__priceValue u-textRed">1,234円</span>
      <dd class="Product__bid">3</dd>
      <span class="Product__time">10時間</span>
    </div>
    '''

    items = YahooAuctionParser.extract_listing_items(html)

    assert len(items) == 1
    assert items[0]['title'] == 'テスト商品'
    assert items[0]['price'] == 1234
    assert items[0]['auctionId'] == 'z123456789'
    assert items[0]['url'].endswith('/jp/auction/z123456789')


def test_yahoo_parser_converts_relative_time_to_datetime_string():
    html = '''
    <div class="Product" data-auction-id="z987654321">
      <a class="Product__titleLink" href="/jp/auction/z987654321">残り時間商品</a>
      <span class="Product__priceValue u-textRed">2,000円</span>
      <dd class="Product__bid">5</dd>
      <span class="Product__time">2日</span>
    </div>
    '''

    items = YahooAuctionParser.extract_listing_items(html)

    assert len(items) == 1
    assert items[0]['time'] != '2日'
    assert '202' in items[0]['time'] or 'T' in items[0]['time'] or items[0]['time'] == 'N/A'


def test_yahoo_parser_handles_paypay_flea_market_urls():
    item = {
        'auctionId': 'z631755388',
        'isFleamarketItem': True,
        'title': 'フリマ商品',
        'price': 999,
        'bidCount': 2,
        'endTime': '2026-08-10T10:55:56+09:00'
    }

    normalized = YahooAuctionParser.normalize_item(item)

    assert normalized['url'] == 'https://paypayfleamarket.yahoo.co.jp/item/z631755388'
