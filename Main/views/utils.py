import logging
import re
from collections import Counter
from datetime import datetime

import numpy as np
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from Main.domain.auction_time import format_remaining_time, parse_duration_seconds
from Main.domain.buying_opportunity import evaluate_buying_opportunity
from Main.domain.product_condition import enrich_market_items
from Main.infrastructure.http import get_with_retry
from Main.models.scraping import scraping
from Main.models.searchwordlog import searchwordlog
from Main.scraping.yahoo import YahooAuctionParser
from Main.services.exceptions import ExternalServiceError
from Main.services.watchlist import refresh_watched_item
from Main.services.time_series_analysis import analyze_stored_market, predict_market_prices

logger = logging.getLogger("search_logger")


def _normalize_url(raw_url):
    if not raw_url:
        return "#"
    value = str(raw_url).strip()
    if not value or value == "#":
        return "#"
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("/"):
        return "https://auctions.yahoo.co.jp" + value
    if value.startswith("jp/auction/") or value.startswith("auction/"):
        return "https://auctions.yahoo.co.jp/" + value
    return value


def _safe_int(value):
    return YahooAuctionParser._safe_int(value)


def _find_item_list(node):
    return YahooAuctionParser._find_item_list(node)


def _extract_listing_items(html):
    return YahooAuctionParser.extract_listing_items(html)


def _build_item_url(raw_url, auction_id=None, item=None):
    return YahooAuctionParser.build_item_url(raw_url, auction_id, item)


def _normalize_yahoo_item(item):
    return YahooAuctionParser.normalize_item(item)


def _format_remaining_time(end_time):
    """後方互換のため公開名を維持し、ドメイン層へ委譲する。"""
    return format_remaining_time(end_time)


def _request_with_retry(url, headers, max_retries=3, timeout=15):
    """後方互換のため公開名を維持し、infrastructure層へ委譲する。"""
    return get_with_retry(url, headers, max_retries=max_retries, timeout=timeout)


def scrape_data(searchname):
    """
    指定されたキーワードでヤフオクの落札履歴をスクレイピングする。
    """
    base_url = "https://auctions.yahoo.co.jp/closedsearch/closedsearch"
    urls = [
        f"{base_url}?p={searchname}&va={searchname}&b=1&n=100&select=6",
        f"{base_url}?p={searchname}&va={searchname}&b=101&n=100&select=6",
    ]

    scraped_data_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    if searchname:
        searchwordlog.objects.create(word=searchname)

    for url in urls:
        try:
            response = _request_with_retry(url, headers=headers)
            html = response.text
            items = _extract_listing_items(html)
            if not items:
                logger.warning(f"No Yahoo item data extracted from {url}")
                continue

            for item in items:
                normalized = _normalize_yahoo_item(item)
                if normalized:
                    scraped_data_list.append(
                        {
                            "name": normalized["name"],
                            "price": normalized["price"],
                            "startPrice": normalized["startPrice"],
                            "bidding": normalized["bidding"],
                            "time": normalized["time"],
                            "url": normalized["url"],
                        }
                    )

        except ExternalServiceError:
            logger.exception("Yahoo終了商品ページの取得に失敗しました url=%s", url)
            continue
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            continue

    return scraped_data_list[:200]


def scrape_current_listings(searchname):
    """
    指定されたキーワードでヤフオクの現在出品されている商品をスクレイピングする。
    """
    base_url = "https://auctions.yahoo.co.jp/search/search"
    urls = [
        f"{base_url}?auccat=&tab_ex=commerce&aq=-&p={searchname}&f=0:1&b=1&n=100",
        f"{base_url}?auccat=&tab_ex=commerce&aq=-&p={searchname}&f=0:1&b=101&n=100",
    ]
    if searchname:
        searchwordlog.objects.create(word=searchname)
    scraped_data_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for url in urls:
        try:
            response = _request_with_retry(url, headers=headers)
            items = _extract_listing_items(response.text)
            for item in items:
                normalized = _normalize_yahoo_item(item)
                if not normalized:
                    continue
                scraped_data_list.append(
                    {
                        "name": normalized["name"],
                        "currentPrice": normalized["price"],
                        "bidding": normalized["bidding"],
                        "remainingTime": _format_remaining_time(normalized["time"]),
                        "url": normalized["url"],
                    }
                )

        except ExternalServiceError:
            logger.exception("Yahoo出品中ページの取得に失敗しました url=%s", url)
            continue
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            continue

    return scraped_data_list[:200]


def save_to_database(searchname, scraped_data_list):
    """
    スクレイピングされたデータをデータベースに保存する。
    """
    now_time = datetime.now()
    SearchDay = now_time.strftime("%Y-%m-%d %H:%M:%S")

    # 同名のSearchWordが存在する場合、削除
    scraping.objects.filter(SearchWord=searchname).delete()

    for scraped_data in scraped_data_list:
        try:
            scraping.objects.create(
                SearchWord=searchname,
                SearchDay=SearchDay,
                Name=scraped_data["name"],
                EndPrice=scraped_data["price"],
                StartPrice=scraped_data["startPrice"],
                Bidding=scraped_data["bidding"],
                URL=scraped_data["url"],
            )
        except Exception:
            logger.exception("相場データの保存に失敗しました keyword=%s", searchname)


def get_search_words_logic(request):
    """
    データベースからユニークな検索ワードのリストを取得する。
    """
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        search_words = scraping.objects.values_list("SearchWord", flat=True).distinct()
        return JsonResponse({"searchWords": list(search_words)})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def get_market_data_logic(request):
    """
    指定キーワードの取引データをデータベースから取得し、JSONで返す。
    """
    searchname = request.GET.get("keyword", "")
    if not searchname:
        return JsonResponse({"error": "Keyword is required"}, status=400)
    try:
        data = list(scraping.objects.filter(SearchWord=searchname).values())
        search_day = (
            scraping.objects.filter(SearchWord=searchname)
            .values_list("SearchDay", flat=True)
            .first()
        )
        analysis = analyze_stored_market(data, datetime.now())
        return JsonResponse({"data": data, "searchDay": search_day, "analysis": analysis})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def update_market_data_logic(request):
    """
    指定キーワードで新たにデータを取得し、データベースを更新する。
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    searchname = request.GET.get("keyword", "")
    if not searchname:
        return JsonResponse({"error": "Keyword is required"}, status=400)
    try:
        scraped_data_list = scrape_data(searchname)
        save_to_database(searchname, scraped_data_list)
        return JsonResponse({"message": "相場データを更新しました"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def delete_market_data_logic(request):
    """
    指定キーワードの取引データをデータベースから削除する。
    """
    if request.method != "DELETE":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    searchname = request.GET.get("keyword", "")
    if not searchname:
        return JsonResponse({"error": "Keyword is required"}, status=400)
    try:
        scraping.objects.filter(SearchWord=searchname).delete()
        return JsonResponse({"message": "相場データを削除しました"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def complex_market_data_logic(request):
    """
    指定キーワードの落札履歴と現在出品中データから、価格リスト・商品名リスト・中央値・おすすめ出品リストを返す。
    また、落札履歴データはデータベースにも保存・更新する。
    """
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    searchname = request.GET.get("keyword", "")
    if not searchname:
        return JsonResponse({"error": "Keyword is required"}, status=400)

    try:
        # 落札履歴データ取得＆DB更新
        closed_data = scrape_data(searchname)
        save_to_database(searchname, closed_data)
        closed_prices = [
            item["price"]
            for item in closed_data
            if "price" in item and isinstance(item["price"], (int, float))
        ]
        closed_names = [item["name"] for item in closed_data if "name" in item]

        # 現在出品中データ
        now_data = scrape_current_listings(searchname)

        now_items = []
        for item in now_data:
            price = item.get("currentPrice")
            name = item.get("name")
            url = item.get("url")
            remaining_time_str = item.get("remainingTime")
            bidding = item.get("bidding", 0)
            remaining_seconds = parse_duration_seconds(remaining_time_str)
            now_items.append(
                {
                    "price": price,
                    "name": name,
                    "url": url,
                    "remainingTime": remaining_time_str,
                    "remainingSeconds": remaining_seconds,
                    "bidding": bidding,
                }
            )

        if closed_prices:
            import numpy as np

            median_price = float(np.median(closed_prices))
        else:
            median_price = 0

        enriched_now_items = enrich_market_items(now_items)
        for item in enriched_now_items:
            item["marketMedian"] = median_price
            item["buyDecision"] = evaluate_buying_opportunity(
                item["price"],
                median_price,
                item["condition"],
                item["remainingSeconds"],
            )
            refresh_watched_item(item)

        now_items_sorted = sorted(
            enriched_now_items,
            key=lambda item: (
                -item["buyDecision"]["score"],
                item["remainingSeconds"],
            ),
        )[:30]

        response_items = [
            {
                "price": item["price"],
                "name": item["name"],
                "url": item["url"],
                "remainingTime": item["remainingTime"],
                "remainingSeconds": item["remainingSeconds"],
                "bidding": item["bidding"],
                "marketMedian": median_price,
                "condition": item["condition"],
                "conditionLabel": item["conditionLabel"],
                "attributes": item["attributes"],
                "attributeLabels": item["attributeLabels"],
                "buyDecision": item["buyDecision"],
            }
            for item in now_items_sorted
        ]

        return JsonResponse(
            {
                "closed_prices": closed_prices,
                "closed_names": closed_names,
                "medianPrice": median_price,
                "recommend_items": response_items,
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def prediction_market_logic(request):
    """
    過去90日間の価格推移取得し、分析、クラスタリングを行う
    """
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    searchname = request.GET.get("keyword", "")
    if not searchname:
        return JsonResponse({"error": "Keyword is required"}, status=400)

    try:
        # 過去180日間の落札データを取得
        closed_data = scrape_data(searchname)
        if not closed_data:
            return JsonResponse({"error": "No data available"}, status=404)

        prediction = predict_market_prices(closed_data, datetime.now())
        if prediction is None:
            return JsonResponse({"error": "No price data in the last 90 days"}, status=404)
        return JsonResponse({"keyword": searchname, **prediction})

    except Exception as e:
        logger.error(f"Error in prediction_market: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


def get_popular_words_logic(request):
    """
    人気のある検索ワードを取得する。
    """
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        top_n = int(request.GET.get("top", 10))
        # 全検索ワード履歴を取得
        all_words = searchwordlog.objects.values_list("word", flat=True)
        tokens = []
        for phrase in all_words:
            if phrase:
                tokens.extend(re.split(r"[\u3000\s]+", phrase.strip()))
        tokens = [t for t in tokens if t]
        counter = Counter(tokens)
        most_common = [w for w, _ in counter.most_common(top_n)]
        return JsonResponse({"words": most_common})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
