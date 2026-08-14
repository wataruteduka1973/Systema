import json
from datetime import datetime
from pathlib import Path

import pytest
from django.conf import settings
from django.test import RequestFactory

from Main.views import api, utils

# テスト開始、レポート生成
# pytest tests/api_test.py --html=tests/report.html


@pytest.mark.django_db
class TestAPIUtils:
    def setup_method(self):
        self.factory = RequestFactory()

    def test_log_directory_exists(self):
        assert (Path(settings.BASE_DIR) / "logs").is_dir()

    # perform_search
    def test_perform_search_get_no_keyword(self):
        request = self.factory.get("/taskle/perform_search")
        response = api.perform_search(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_perform_search_post(self):
        request = self.factory.post("/taskle/perform_search")
        response = api.perform_search(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_perform_search_adds_condition_analysis(self, monkeypatch):
        monkeypatch.setattr(
            api,
            "scrape_data",
            lambda keyword: [
                {
                    "name": "中古 動作確認済み 商品",
                    "price": 2000,
                    "startPrice": 1000,
                    "bidding": 3,
                    "time": "2026-08-12T10:00:00+09:00",
                    "url": "#",
                },
                {
                    "name": "ジャンク 商品",
                    "price": 500,
                    "startPrice": 1,
                    "bidding": 1,
                    "time": "2026-08-11T10:00:00+09:00",
                    "url": "#",
                },
            ],
        )
        monkeypatch.setattr(api, "save_to_database", lambda keyword, items: None)

        response = api.perform_search(self.factory.get("/taskle/perform_search?keyword=test"))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["data"][0]["condition"] == "used"
        assert data["data"][0]["conditionLabel"] == "中古・動作品"
        assert data["conditionSummary"]["medianPriceExcludingJunk"] == 2000
        assert data["marketStatistics"]["median"] == 1250
        assert data["data"][0]["marketComparison"]["position"] == "above"

    # RealtimeSearch
    def test_realtime_search_get_no_keyword(self):
        request = self.factory.get("/taskle/realtime_search")
        response = api.RealtimeSearch(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_realtime_search_post(self):
        request = self.factory.post("/taskle/realtime_search")
        response = api.RealtimeSearch(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_realtime_search_adds_condition_analysis(self, monkeypatch):
        monkeypatch.setattr(
            api,
            "scrape_current_listings",
            lambda keyword: [
                {"name": "新品 未開封 商品", "currentPrice": 3000},
                {"name": "ジャンク 商品", "currentPrice": 500},
            ],
        )

        response = api.RealtimeSearch(self.factory.get("/taskle/RealtimeSearch?keyword=test"))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["data"][0]["condition"] == "new"
        assert data["data"][1]["condition"] == "junk"
        assert data["conditionSummary"]["medianPriceExcludingJunk"] == 3000
        assert data["marketStatistics"]["median"] == 1750
        assert data["data"][1]["marketComparison"]["position"] == "below"

    # get_search_words
    def test_get_search_words_get(self):
        request = self.factory.get("/taskle/get_search_words")
        response = api.get_search_words(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "searchWords" in data

    def test_get_search_words_post(self):
        request = self.factory.post("/taskle/get_search_words")
        response = api.get_search_words(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    # get_market_data
    def test_get_market_data_get_no_keyword(self):
        request = self.factory.get("/taskle/get_market_data")
        response = api.get_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_get_market_data_post(self):
        request = self.factory.post("/taskle/get_market_data")
        response = api.get_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    # update_market_data
    def test_update_market_data_post_no_keyword(self):
        request = self.factory.post("/taskle/update_market_data")
        response = api.update_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_update_market_data_get(self):
        request = self.factory.get("/taskle/update_market_data")
        response = api.update_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    # delete_market_data
    def test_delete_market_data_delete_no_keyword(self):
        request = self.factory.delete("/taskle/delete_market_data")
        response = api.delete_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_delete_market_data_get(self):
        request = self.factory.get("/taskle/delete_market_data")
        response = api.delete_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    # complex_market_data
    def test_complex_market_data_post(self):
        request = self.factory.post("/taskle/complex_market_data")
        response = api.complex_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_complex_market_data_get_no_keyword(self):
        request = self.factory.get("/taskle/complex_market_data")
        response = api.complex_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    # prediction_market
    def test_prediction_market_post(self):
        request = self.factory.post("/taskle/prediction_market")
        response = api.prediction_market(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_prediction_market_get_no_keyword(self):
        request = self.factory.get("/taskle/prediction_market")
        response = api.prediction_market(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    # get_popular_words
    def test_get_popular_words_get(self):
        request = self.factory.get("/taskle/get_popular_words")
        response = api.get_popular_words(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "words" in data

    def test_get_popular_words_post(self):
        request = self.factory.post("/taskle/get_popular_words")
        response = api.get_popular_words(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_watchlist_create_list_update_and_delete(self):
        payload = {
            "name": "中古 動作確認済み 商品",
            "url": "https://auctions.yahoo.co.jp/jp/auction/test123",
            "currentPrice": 7000,
            "bidding": 3,
            "remainingTime": "30分",
            "remainingSeconds": 1800,
            "condition": "used",
            "conditionLabel": "中古・動作品",
            "marketMedian": 10000,
            "searchKeyword": "test",
        }
        create_response = api.watchlist(
            self.factory.post(
                "/taskle/watchlist",
                data=json.dumps(payload),
                content_type="application/json",
            )
        )
        assert create_response.status_code == 201
        created = json.loads(create_response.content)["item"]
        assert created["addedPrice"] == 7000
        assert created["buyDecision"]["status"] == "strong_buy"

        payload["currentPrice"] = 6500
        update_response = api.watchlist(
            self.factory.post(
                "/taskle/watchlist",
                data=json.dumps(payload),
                content_type="application/json",
            )
        )
        updated = json.loads(update_response.content)["item"]
        assert update_response.status_code == 200
        assert updated["addedPrice"] == 7000
        assert updated["priceChange"] == -500

        list_response = api.watchlist(self.factory.get("/taskle/watchlist"))
        assert len(json.loads(list_response.content)["items"]) == 1

        delete_response = api.watchlist_item(
            self.factory.delete(f"/taskle/watchlist/{created['id']}"), created["id"]
        )
        assert delete_response.status_code == 200

    def test_watchlist_rejects_non_yahoo_url(self):
        response = api.watchlist(
            self.factory.post(
                "/taskle/watchlist",
                data=json.dumps({"name": "商品", "url": "https://example.com/item"}),
                content_type="application/json",
            )
        )
        assert response.status_code == 400

    def test_complex_market_data_adds_buy_decision(self, monkeypatch):
        monkeypatch.setattr(
            utils,
            "scrape_data",
            lambda keyword: [
                {"name": "落札商品1", "price": 10000},
                {"name": "落札商品2", "price": 12000},
            ],
        )
        monkeypatch.setattr(utils, "save_to_database", lambda keyword, items: None)
        monkeypatch.setattr(
            utils,
            "scrape_current_listings",
            lambda keyword: [
                {
                    "name": "中古 動作確認済み 商品",
                    "currentPrice": 7000,
                    "bidding": 2,
                    "remainingTime": "30分",
                    "url": "https://auctions.yahoo.co.jp/jp/auction/target123",
                }
            ],
        )

        response = api.complex_market_data(
            self.factory.get("/taskle/complex_market_data?keyword=test")
        )

        assert response.status_code == 200
        item = json.loads(response.content)["recommend_items"][0]
        assert item["condition"] == "used"
        assert item["buyDecision"]["status"] == "strong_buy"

    # --- UTILS LOGIC 追加 ---
    def test_utils_get_search_words_logic_get(self):
        request = self.factory.get("/taskle/get_search_words")
        response = utils.get_search_words_logic(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "searchWords" in data

    def test_utils_get_search_words_logic_post(self):
        request = self.factory.post("/taskle/get_search_words")
        response = utils.get_search_words_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_utils_get_market_data_logic_no_keyword(self):
        request = self.factory.get("/taskle/get_market_data")
        response = utils.get_market_data_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_utils_get_market_data_logic_post(self):
        request = self.factory.post("/taskle/get_market_data")
        response = utils.get_market_data_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_utils_update_market_data_logic_get(self):
        request = self.factory.get("/taskle/update_market_data")
        response = utils.update_market_data_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_utils_delete_market_data_logic_get(self):
        request = self.factory.get("/taskle/delete_market_data")
        response = utils.delete_market_data_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_utils_complex_market_data_logic_post(self):
        request = self.factory.post("/taskle/complex_market_data")
        response = utils.complex_market_data_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_utils_prediction_market_logic_post(self):
        request = self.factory.post("/taskle/prediction_market")
        response = utils.prediction_market_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_utils_prediction_market_logic_year_wraps_to_previous_year(self, monkeypatch):
        fixed_now = datetime(2026, 1, 10, 12, 0, 0)
        FakeDateTime = type(
            "FakeDateTime", (datetime,), {"now": classmethod(lambda cls, tz=None: fixed_now)}
        )
        monkeypatch.setattr(utils, "datetime", FakeDateTime)
        monkeypatch.setattr(
            utils,
            "scrape_data",
            lambda keyword: [
                {"time": "12/31 23:59", "price": 1000},
                {"time": "01/05 12:00", "price": 1500},
                {"time": "10/01 09:00", "price": 2000},
            ],
        )

        request = self.factory.get("/taskle/prediction_market?keyword=test")
        response = utils.prediction_market_logic(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["keyword"] == "test"
        assert "predicted_price" in data
        assert "daily_trends" in data
        assert "quality" in data
        assert any(item["date"] == "12/31 23:59" for item in data["price_trends"])

    def test_utils_prediction_market_logic_accepts_iso_dates(self, monkeypatch):
        fixed_now = datetime(2026, 8, 13, 12, 0, 0)
        FakeDateTime = type(
            "FakeDateTime", (datetime,), {"now": classmethod(lambda cls, tz=None: fixed_now)}
        )
        monkeypatch.setattr(utils, "datetime", FakeDateTime)
        monkeypatch.setattr(
            utils,
            "scrape_data",
            lambda keyword: [
                {"time": "2026-08-12T10:00:00+09:00", "price": 1000},
                {"time": "2026-08-11T10:00:00+09:00", "price": 1500},
            ],
        )

        request = self.factory.get("/taskle/prediction_market?keyword=test")
        response = utils.prediction_market_logic(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert len(data["price_trends"]) == 2
        assert data["predicted_price"] > 0
        assert data["quality"]["sampleCount"] == 2

    def test_utils_get_popular_words_logic_get(self):
        request = self.factory.get("/taskle/get_popular_words")
        response = utils.get_popular_words_logic(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "words" in data

    def test_utils_get_popular_words_logic_post(self):
        request = self.factory.post("/taskle/get_popular_words")
        response = utils.get_popular_words_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_extract_next_data_items_for_yahoo_search_json(self):
        html = """
        <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"initialState":{"search":{"items":{"listing":{"items":[{"title":"iphone case","price":1200,"bidCount":3,"initPriceNoTax":800,"endTime":"2026-08-10T10:55:56+09:00","auctionId":"z123456789"}]}}}}}}}
        </script>
        """
        items = utils._extract_listing_items(html)
        assert len(items) == 1
        assert items[0]["title"] == "iphone case"
        assert items[0]["price"] == 1200
        assert items[0]["auctionId"] == "z123456789"

    def test_normalize_yahoo_item_url_and_time(self):
        item = {
            "auctionId": "z123456789",
            "url": "/jp/auction/z123456789",
            "title": "iphone case",
            "price": 1200,
            "bidCount": 3,
            "endTime": "2026-08-10T10:55:56+09:00",
        }
        normalized = utils._normalize_yahoo_item(item)
        assert normalized["url"] == "https://auctions.yahoo.co.jp/jp/auction/z123456789"
        assert normalized["time"] == "2026-08-10T10:55:56+09:00"
        assert normalized["price"] == 1200

    def test_normalize_yahoo_item_url_for_paypay_fleamarket(self):
        item = {
            "auctionId": "z658212182",
            "isFleamarketItem": True,
            "title": "paypay item",
            "price": 500,
            "bidCount": 2,
            "endTime": "2026-08-10T10:55:56+09:00",
        }
        normalized = utils._normalize_yahoo_item(item)
        assert normalized["url"] == "https://paypayfleamarket.yahoo.co.jp/item/z658212182"

    def test_extract_next_data_items_for_yahoo_live_search_json(self):
        html = """
        <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"initialState":{"search":{"result":{"items":[{"title":"live item","currentPrice":1500,"bidCount":8,"endTime":"2026-08-10T11:00:00+09:00","auctionId":"z777777777","url":"/jp/auction/z777777777"}]}}}}}}
        </script>
        """
        items = utils._extract_listing_items(html)
        assert len(items) == 1
        assert items[0]["title"] == "live item"
        assert items[0]["currentPrice"] == 1500
        assert items[0]["auctionId"] == "z777777777"

    def test_extract_listing_items_ignores_site_navigation_and_footer_links(self):
        html = """
        <html>
          <body>
            <nav><a href="/jp/auction/z999">Yahoo! JAPAN</a></nav>
            <div><a href="/jp/auction/z111">ヘルプ</a></div>
            <article data-auction-id="z777777777">
              <a href="/jp/auction/z777777777">live item</a>
              <span>1,500円</span>
            </article>
          </body>
        </html>
        """
        items = utils._extract_listing_items(html)
        assert len(items) >= 1
        assert all("Yahoo! JAPAN" not in item.get("title", "") for item in items)
        assert any(item.get("auctionId") == "z777777777" for item in items)

    def test_normalize_yahoo_item_from_live_search_fields(self):
        item = {
            "title": "live item",
            "currentPrice": 1500,
            "bidCount": 8,
            "endTime": "2026-08-10T11:00:00+09:00",
            "auctionId": "z777777777",
            "url": "/jp/auction/z777777777",
        }
        normalized = utils._normalize_yahoo_item(item)
        assert normalized["price"] == 1500
        assert normalized["bidding"] == 8
        assert normalized["time"] == "2026-08-10T11:00:00+09:00"
        assert normalized["url"] == "https://auctions.yahoo.co.jp/jp/auction/z777777777"
