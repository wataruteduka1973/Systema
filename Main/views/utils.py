import logging
import math
import re
from collections import Counter
from datetime import datetime
from urllib.parse import urlencode

from django.http import JsonResponse

from Main.domain.auction_time import format_remaining_time, parse_duration_seconds
from Main.domain.buying_opportunity import evaluate_buying_opportunity
from Main.domain.product_condition import enrich_market_items
from Main.infrastructure.http import get_with_retry
from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.models.searchwordlog import searchwordlog
from Main.scraping.yahoo import YahooAuctionParser
from Main.services.exceptions import ExternalServiceError, SearchParseError
from Main.services.external_search import normalize_search_keyword
from Main.services.market_statistics import (
    analyze_market_prices,
    enrich_items_with_market_comparison,
)
from Main.services.ownership import get_request_owner, owner_query
from Main.services.search_criteria import SearchCriteria
from Main.services.search_observability import (
    FAILURE_INSUFFICIENT_DATA,
    FAILURE_NO_DATA,
    FAILURE_UNEXPECTED,
    SearchTimer,
    external_failure_code,
)
from Main.services.time_series_analysis import (
    analyze_snapshot_history,
    analyze_stored_market,
    predict_market_prices,
)
from Main.services.watchlist import refresh_watched_item

logger = logging.getLogger("search_logger")
EXTERNAL_SERVICE_MESSAGE = "外部サービスからデータを取得できませんでした"


def _build_search_url(base_url, parameters):
    return f"{base_url}?{urlencode(parameters)}"


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


def _is_valid_listing(normalized):
    """商品ID・価格・商品名を持つ実際の出品だけを許可する。"""
    if not normalized:
        return False
    title = str(normalized.get("name") or "").strip()
    price = normalized.get("price")
    auction_id = str(normalized.get("auctionId") or "").strip()
    if not auction_id:
        url_match = re.search(
            r"/(?:auction|item)/([a-z]?\d{8,})(?:[/?#]|$)",
            str(normalized.get("url") or ""),
            re.I,
        )
        auction_id = url_match.group(1) if url_match else ""
    return (
        YahooAuctionParser._is_valid_title_text(title)
        and isinstance(price, (int, float))
        and not isinstance(price, bool)
        and price > 0
        and re.fullmatch(r"[a-z]?\d{8,}", auction_id, re.I) is not None
    )


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
    searchname = normalize_search_keyword(searchname)
    urls = [
        _build_search_url(
            base_url,
            {"p": searchname, "va": searchname, "b": offset, "n": 100, "select": 6},
        )
        for offset in (1, 101)
    ]

    scraped_data_list = []
    successful_pages = 0
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for url in urls:
        try:
            response = _request_with_retry(url, headers=headers)
            successful_pages += 1
            html = response.text
            items = _extract_listing_items(html)
            if not items:
                logger.warning("No Yahoo item data extracted")
                continue

            for item in items:
                normalized = _normalize_yahoo_item(item)
                if _is_valid_listing(normalized):
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

        except SearchParseError:
            raise
        except ExternalServiceError:
            logger.exception("Yahoo終了商品ページの取得に失敗しました")
            continue
        except Exception:
            logger.exception("Yahoo終了商品ページの解析に失敗しました")
            raise SearchParseError("検索ページを解析できませんでした") from None

    if successful_pages == 0:
        raise ExternalServiceError(EXTERNAL_SERVICE_MESSAGE)
    return scraped_data_list[:200]


def scrape_current_listings(searchname):
    """
    指定されたキーワードでヤフオクの現在出品されている商品をスクレイピングする。
    """
    base_url = "https://auctions.yahoo.co.jp/search/search"
    searchname = normalize_search_keyword(searchname)
    urls = [
        _build_search_url(
            base_url,
            {
                "auccat": "",
                "tab_ex": "commerce",
                "aq": "-",
                "p": searchname,
                "f": "0:1",
                "b": offset,
                "n": 100,
            },
        )
        for offset in (1, 101)
    ]
    scraped_data_list = []
    successful_pages = 0
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for url in urls:
        try:
            response = _request_with_retry(url, headers=headers)
            successful_pages += 1
            items = _extract_listing_items(response.text)
            for item in items:
                normalized = _normalize_yahoo_item(item)
                if not _is_valid_listing(normalized):
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

        except SearchParseError:
            raise
        except ExternalServiceError:
            logger.exception("Yahoo出品中ページの取得に失敗しました")
            continue
        except Exception:
            logger.exception("Yahoo出品中ページの解析に失敗しました")
            raise SearchParseError("検索ページを解析できませんでした") from None

    if successful_pages == 0:
        raise ExternalServiceError(EXTERNAL_SERVICE_MESSAGE)
    return scraped_data_list[:200]


def record_search_run(
    request,
    searchname,
    search_type,
    item_count,
    succeeded=True,
    record_word=True,
    criteria_snapshot=None,
    trigger="manual",
    duration_ms=None,
    failure_code="",
    saved_search=None,
):
    owner = get_request_owner(request)
    saved_search = saved_search or getattr(request, "saved_search", None)
    if trigger == "manual":
        trigger = getattr(request, "search_trigger", trigger)
    run = SearchRun.objects.create(
        **owner.model_values,
        saved_search=saved_search,
        keyword=searchname,
        search_type=search_type,
        item_count=item_count,
        succeeded=succeeded,
        criteria_snapshot=criteria_snapshot or {},
        trigger=trigger,
        duration_ms=duration_ms,
        failure_code=failure_code,
    )
    recorded_runs = getattr(request, "recorded_search_runs", None)
    if recorded_runs is None:
        recorded_runs = []
        request.recorded_search_runs = recorded_runs
    recorded_runs.append(run)
    if record_word:
        searchwordlog.objects.create(**owner.model_values, word=searchname)
    return run


def update_search_run_observability(run, *, duration_ms, succeeded=True, failure_code=""):
    run.duration_ms = duration_ms
    run.succeeded = succeeded
    run.failure_code = failure_code
    run.save(update_fields=("duration_ms", "succeeded", "failure_code"))
    return run


def save_to_database(searchname, scraped_data_list, search_run=None):
    """
    スクレイピングされたデータをデータベースに保存する。
    """
    now_time = datetime.now()
    SearchDay = now_time.strftime("%Y-%m-%d %H:%M:%S")

    for scraped_data in scraped_data_list:
        try:
            scraping.objects.create(
                search_run=search_run,
                SearchWord=searchname,
                SearchDay=SearchDay,
                Name=scraped_data["name"],
                EndPrice=scraped_data.get("price", scraped_data.get("currentPrice", 0)),
                StartPrice=scraped_data.get("startPrice", scraped_data.get("currentPrice", 0)),
                Bidding=scraped_data.get("bidding", 0),
                URL=scraped_data.get("url", "#"),
            )
        except Exception:
            logger.exception("相場データの保存に失敗しました")

    if search_run is not None:
        owner = {"user": search_run.user, "session_key": search_run.session_key}
        retained_ids = list(
            SearchRun.objects.filter(
                **owner, keyword=searchname, search_type=search_run.search_type
            ).values_list("id", flat=True)[:50]
        )
        SearchRun.objects.filter(
            **owner, keyword=searchname, search_type=search_run.search_type
        ).exclude(pk__in=retained_ids).delete()


def get_search_words_logic(request):
    """
    データベースからユニークな検索ワードのリストを取得する。
    """
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        owner = get_request_owner(request)
        search_words = (
            SearchRun.objects.filter(owner_query(owner), search_type=SearchRun.CLOSED)
            .order_by("-created_at")
            .values_list("keyword", flat=True)
        )
        unique_words = list(dict.fromkeys(str(word).strip() for word in search_words if word))
        return JsonResponse({"searchWords": unique_words})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def get_market_data_logic(request):
    """
    指定キーワードの取引データをデータベースから取得し、JSONで返す。
    """
    try:
        searchname = normalize_search_keyword(request.GET.get("keyword", ""))
    except Exception as error:
        return JsonResponse({"error": str(error), "code": "invalid_keyword"}, status=400)
    try:
        owner = get_request_owner(request)
        runs = SearchRun.objects.filter(
            owner_query(owner), keyword=searchname, search_type=SearchRun.CLOSED
        )
        latest_run = runs.first()
        records = scraping.objects.filter(search_run__in=runs).order_by("SearchDay")
        search_day = latest_run.created_at.isoformat() if latest_run else None
        data = list(scraping.objects.filter(search_run=latest_run).values()) if latest_run else []
        history = list(records.values("SearchDay", "EndPrice"))
        analysis = analyze_stored_market(data, datetime.now())
        analysis["timeSeries"] = analyze_snapshot_history(history)
        normalized = [
            {
                "name": item["Name"],
                "price": item["EndPrice"],
                "startPrice": item["StartPrice"],
                "bidding": item["Bidding"],
                "url": item["URL"],
                "searchDay": item["SearchDay"],
            }
            for item in data
        ]
        enriched = enrich_market_items(normalized)
        enriched = enrich_items_with_market_comparison(enriched, analysis["summary"]["median"])
        response_data = [original | extra for original, extra in zip(data, enriched, strict=True)]
        return JsonResponse({"data": response_data, "searchDay": search_day, "analysis": analysis})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def update_market_data_logic(request, criteria=None):
    """
    指定キーワードで新たにデータを取得し、データベースを更新する。
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    if criteria is None:
        try:
            criteria = SearchCriteria.from_query(request.GET, SearchRun.CLOSED)
        except Exception as error:
            return JsonResponse({"error": str(error), "code": "invalid_keyword"}, status=400)
    searchname = criteria.keyword
    timer = SearchTimer.start()
    run = None
    try:
        scraped_data_list = criteria.apply(scrape_data(searchname))
        run = record_search_run(
            request,
            searchname,
            SearchRun.CLOSED,
            len(scraped_data_list),
            criteria_snapshot=criteria.snapshot(),
            duration_ms=timer.elapsed_ms(),
        )
        save_to_database(searchname, scraped_data_list, run)
        update_search_run_observability(run, duration_ms=timer.elapsed_ms())
        return JsonResponse({"message": "相場データを更新しました"})
    except ExternalServiceError as error:
        logger.exception("Market data update failed")
        if run is None:
            record_search_run(
                request,
                searchname,
                SearchRun.CLOSED,
                0,
                succeeded=False,
                criteria_snapshot=criteria.snapshot(),
                duration_ms=timer.elapsed_ms(),
                failure_code=external_failure_code(error),
            )
        else:
            update_search_run_observability(
                run,
                duration_ms=timer.elapsed_ms(),
                succeeded=False,
                failure_code=external_failure_code(error),
            )
        return JsonResponse(
            {"error": EXTERNAL_SERVICE_MESSAGE, "code": "external_service_unavailable"},
            status=503,
        )
    except Exception:
        logger.exception("Unexpected market data update error")
        if run is None:
            record_search_run(
                request,
                searchname,
                SearchRun.CLOSED,
                0,
                succeeded=False,
                criteria_snapshot=criteria.snapshot(),
                duration_ms=timer.elapsed_ms(),
                failure_code=FAILURE_UNEXPECTED,
            )
        else:
            update_search_run_observability(
                run,
                duration_ms=timer.elapsed_ms(),
                succeeded=False,
                failure_code=FAILURE_UNEXPECTED,
            )
        return JsonResponse({"error": "相場データを更新できませんでした"}, status=500)


def delete_market_data_logic(request):
    """
    指定キーワードの取引データをデータベースから削除する。
    """
    if request.method != "DELETE":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        searchname = normalize_search_keyword(request.GET.get("keyword", ""))
    except Exception as error:
        return JsonResponse({"error": str(error), "code": "invalid_keyword"}, status=400)
    try:
        owner = get_request_owner(request)
        SearchRun.objects.filter(
            owner_query(owner), keyword=searchname, search_type=SearchRun.CLOSED
        ).delete()
        return JsonResponse({"message": "相場データを削除しました"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def complex_market_data_logic(request, criteria=None):
    """
    指定キーワードの落札履歴と現在出品中データから、価格リスト・商品名リスト・中央値・おすすめ出品リストを返す。
    また、落札履歴データはデータベースにも保存・更新する。
    """
    if request.method != "GET" and criteria is None:
        return JsonResponse({"error": "Invalid request method"}, status=400)

    if criteria is None:
        try:
            criteria = SearchCriteria.from_query(request.GET, SearchRun.TARGET)
        except Exception as error:
            return JsonResponse({"error": str(error), "code": "invalid_keyword"}, status=400)
    searchname = criteria.keyword
    active_search_type = SearchRun.CLOSED
    active_timer = SearchTimer.start()
    active_run = None

    try:
        # 落札履歴データ取得＆DB更新
        closed_data = criteria.apply(scrape_data(searchname), search_type=SearchRun.CLOSED)
        closed_run = record_search_run(
            request,
            searchname,
            SearchRun.CLOSED,
            len(closed_data),
            criteria_snapshot=criteria.snapshot(),
            duration_ms=active_timer.elapsed_ms(),
        )
        active_run = closed_run
        save_to_database(searchname, closed_data, closed_run)
        update_search_run_observability(closed_run, duration_ms=active_timer.elapsed_ms())
        closed_prices = [
            item["price"]
            for item in closed_data
            if "price" in item and isinstance(item["price"], (int, float))
        ]
        closed_names = [item["name"] for item in closed_data if "name" in item]

        # 現在出品中データ
        active_search_type = SearchRun.CURRENT
        active_timer = SearchTimer.start()
        active_run = None
        now_data = criteria.apply(
            scrape_current_listings(searchname), search_type=SearchRun.CURRENT
        )
        current_run = record_search_run(
            request,
            searchname,
            SearchRun.CURRENT,
            len(now_data),
            record_word=False,
            criteria_snapshot=criteria.snapshot(),
            duration_ms=active_timer.elapsed_ms(),
        )
        active_run = current_run
        save_to_database(searchname, now_data, current_run)

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
        enriched_now_items = enrich_items_with_market_comparison(enriched_now_items, median_price)
        for item in enriched_now_items:
            item["marketMedian"] = median_price
            item["buyDecision"] = evaluate_buying_opportunity(
                item["price"],
                median_price,
                item["condition"],
                item["remainingSeconds"],
            )
            refresh_watched_item(item, get_request_owner(request))

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
                "remainingSeconds": (
                    item["remainingSeconds"] if math.isfinite(item["remainingSeconds"]) else None
                ),
                "bidding": item["bidding"],
                "marketMedian": median_price,
                "condition": item["condition"],
                "conditionLabel": item["conditionLabel"],
                "attributes": item["attributes"],
                "attributeLabels": item["attributeLabels"],
                "buyDecision": item["buyDecision"],
                "marketComparison": item["marketComparison"],
            }
            for item in now_items_sorted
        ]

        response_data = {
            "closed_prices": closed_prices,
            "closed_names": closed_names,
            "medianPrice": median_price,
            "marketStatistics": analyze_market_prices(
                [{"price": price} for price in closed_prices]
            ),
            "recommend_items": response_items,
        }
        current_run.result_snapshot = response_data
        current_run.save(update_fields=("result_snapshot",))
        update_search_run_observability(current_run, duration_ms=active_timer.elapsed_ms())
        return JsonResponse(response_data)
    except ExternalServiceError as error:
        logger.exception("Complex market search failed")
        if active_run is None:
            record_search_run(
                request,
                searchname,
                active_search_type,
                0,
                succeeded=False,
                record_word=active_search_type == SearchRun.CLOSED,
                criteria_snapshot=criteria.snapshot(),
                duration_ms=active_timer.elapsed_ms(),
                failure_code=external_failure_code(error),
            )
        else:
            update_search_run_observability(
                active_run,
                duration_ms=active_timer.elapsed_ms(),
                succeeded=False,
                failure_code=external_failure_code(error),
            )
        return JsonResponse(
            {"error": EXTERNAL_SERVICE_MESSAGE, "code": "external_service_unavailable"},
            status=503,
        )
    except Exception:
        logger.exception("Unexpected complex market search error")
        if active_run is None:
            record_search_run(
                request,
                searchname,
                active_search_type,
                0,
                succeeded=False,
                record_word=active_search_type == SearchRun.CLOSED,
                criteria_snapshot=criteria.snapshot(),
                duration_ms=active_timer.elapsed_ms(),
                failure_code=FAILURE_UNEXPECTED,
            )
        else:
            update_search_run_observability(
                active_run,
                duration_ms=active_timer.elapsed_ms(),
                succeeded=False,
                failure_code=FAILURE_UNEXPECTED,
            )
        return JsonResponse({"error": "市場分析を実行できませんでした"}, status=500)


def prediction_market_logic(request, criteria=None):
    """
    過去90日間の価格推移取得し、分析、クラスタリングを行う
    """
    if request.method != "GET" and criteria is None:
        return JsonResponse({"error": "Invalid request method"}, status=400)

    if criteria is None:
        try:
            criteria = SearchCriteria.from_query(request.GET, SearchRun.PREDICTION)
        except Exception as error:
            return JsonResponse({"error": str(error), "code": "invalid_keyword"}, status=400)
    searchname = criteria.keyword
    timer = SearchTimer.start()
    run = None

    try:
        # 過去180日間の落札データを取得
        closed_data = criteria.apply(scrape_data(searchname), search_type=SearchRun.CLOSED)
        run = record_search_run(
            request,
            searchname,
            SearchRun.PREDICTION,
            len(closed_data),
            bool(closed_data),
            criteria_snapshot=criteria.snapshot(),
            duration_ms=timer.elapsed_ms(),
            failure_code="" if closed_data else FAILURE_NO_DATA,
        )
        if not closed_data:
            return JsonResponse({"error": "No data available"}, status=404)

        prediction = predict_market_prices(closed_data, datetime.now())
        if prediction is None:
            update_search_run_observability(
                run,
                duration_ms=timer.elapsed_ms(),
                succeeded=False,
                failure_code=FAILURE_INSUFFICIENT_DATA,
            )
            return JsonResponse({"error": "No price data in the last 90 days"}, status=404)
        update_search_run_observability(run, duration_ms=timer.elapsed_ms())
        return JsonResponse({"keyword": searchname, **prediction})

    except ExternalServiceError as error:
        logger.exception("Prediction market search failed")
        if run is None:
            record_search_run(
                request,
                searchname,
                SearchRun.PREDICTION,
                0,
                succeeded=False,
                criteria_snapshot=criteria.snapshot(),
                duration_ms=timer.elapsed_ms(),
                failure_code=external_failure_code(error),
            )
        else:
            update_search_run_observability(
                run,
                duration_ms=timer.elapsed_ms(),
                succeeded=False,
                failure_code=external_failure_code(error),
            )
        return JsonResponse(
            {"error": EXTERNAL_SERVICE_MESSAGE, "code": "external_service_unavailable"},
            status=503,
        )
    except Exception:
        logger.exception("Unexpected prediction market error")
        if run is None:
            record_search_run(
                request,
                searchname,
                SearchRun.PREDICTION,
                0,
                succeeded=False,
                criteria_snapshot=criteria.snapshot(),
                duration_ms=timer.elapsed_ms(),
                failure_code=FAILURE_UNEXPECTED,
            )
        else:
            update_search_run_observability(
                run,
                duration_ms=timer.elapsed_ms(),
                succeeded=False,
                failure_code=FAILURE_UNEXPECTED,
            )
        return JsonResponse({"error": "相場予想を実行できませんでした"}, status=500)


def get_popular_words_logic(request):
    """
    人気のある検索ワードを取得する。
    """
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        top_n = int(request.GET.get("top", 10))
        owner = get_request_owner(request)
        all_words = searchwordlog.objects.filter(owner_query(owner)).values_list("word", flat=True)
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
