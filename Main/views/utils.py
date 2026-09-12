import logging
import re
from collections import Counter
from datetime import datetime
from urllib.parse import urlencode

from django.http import JsonResponse

from Main.domain.auction_time import format_remaining_time
from Main.domain.market_listing import MarketListingObservation
from Main.domain.product_condition import enrich_market_items
from Main.infrastructure.http import get_with_retry
from Main.infrastructure.marketplaces.yahoo import (
    YahooMarketplaceProvider,
    closed_items,
    current_items,
)
from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.models.searchwordlog import searchwordlog
from Main.scraping.yahoo import YahooAuctionParser
from Main.services.exceptions import ExternalServiceError
from Main.services.external_search import normalize_search_keyword
from Main.services.market_search import TargetSearchFailure, execute_target_search
from Main.services.market_statistics import enrich_items_with_market_comparison
from Main.services.ownership import get_request_owner, owner_query
from Main.services.search_criteria import SearchCriteria
from Main.services.search_observability import (
    FAILURE_INSUFFICIENT_DATA,
    FAILURE_NO_DATA,
    FAILURE_UNEXPECTED,
    SearchTimer,
    external_failure_code,
)
from Main.services.search_persistence import (
    DjangoSearchRepository,
    persist_successful_search,
    replace_items_for_existing_run,
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
    """後方互換名を維持してYahoo Providerへ委譲する。"""
    provider = YahooMarketplaceProvider(
        fetch=_request_with_retry,
        extract=_extract_listing_items,
        normalize=_normalize_yahoo_item,
    )
    return closed_items(provider, searchname)


def scrape_current_listings(searchname):
    """後方互換名を維持してYahoo Providerへ委譲する。"""
    provider = YahooMarketplaceProvider(
        fetch=_request_with_retry,
        extract=_extract_listing_items,
        normalize=_normalize_yahoo_item,
    )
    return current_items(provider, searchname)


class _YahooSearchProvider:
    """既存の差替え可能な取得関数をDTO契約へ変換するWeb互換アダプター。"""

    marketplace = YahooMarketplaceProvider.marketplace

    def search_closed(self, keyword: str) -> list[MarketListingObservation]:
        return [
            MarketListingObservation(
                marketplace=self.marketplace,
                external_id="",
                name=str(item.get("name") or ""),
                price=int(item.get("price") or 0),
                start_price=int(item.get("startPrice") or 0),
                bidding=int(item.get("bidding") or 0),
                time=str(item.get("time") or ""),
                url=str(item.get("url") or ""),
            )
            for item in scrape_data(keyword)
        ]

    def search_current(self, keyword: str) -> list[MarketListingObservation]:
        return [
            MarketListingObservation(
                marketplace=self.marketplace,
                external_id="",
                name=str(item.get("name") or ""),
                price=int(item.get("currentPrice") or 0),
                start_price=int(item.get("currentPrice") or 0),
                bidding=int(item.get("bidding") or 0),
                time=str(item.get("remainingTime") or ""),
                url=str(item.get("url") or ""),
            )
            for item in scrape_current_listings(keyword)
        ]


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
    """後方互換のため公開名を維持し、保存サービスへ委譲する。"""
    if search_run is None:
        raise ValueError("search_run is required")
    replace_items_for_existing_run(searchname, scraped_data_list, search_run)


def persist_search_results(
    request,
    searchname,
    search_type,
    items,
    *,
    record_word=True,
    criteria_snapshot=None,
    trigger="manual",
    duration_ms=None,
    saved_search=None,
):
    """HTTP情報を所有者へ変換し、成功した検索全体を原子的に保存する。"""
    owner = get_request_owner(request)
    saved_search = saved_search or getattr(request, "saved_search", None)
    if trigger == "manual":
        trigger = getattr(request, "search_trigger", trigger)
    run = persist_successful_search(
        owner=owner,
        keyword=searchname,
        search_type=search_type,
        items=items,
        record_word=record_word,
        criteria_snapshot=criteria_snapshot,
        trigger=trigger,
        duration_ms=duration_ms,
        saved_search=saved_search,
    )
    recorded_runs = getattr(request, "recorded_search_runs", None)
    if recorded_runs is None:
        recorded_runs = []
        request.recorded_search_runs = recorded_runs
    recorded_runs.append(run)
    return run


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
        run = persist_search_results(
            request,
            searchname,
            SearchRun.CLOSED,
            scraped_data_list,
            criteria_snapshot=criteria.snapshot(),
            duration_ms=timer.elapsed_ms(),
        )
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
    """終了商品と出品中商品を検索し、target分析の既存JSON契約を返す。"""
    if request.method != "GET" and criteria is None:
        return JsonResponse({"error": "Invalid request method"}, status=400)

    if criteria is None:
        try:
            criteria = SearchCriteria.from_query(request.GET, SearchRun.TARGET)
        except Exception as error:
            return JsonResponse({"error": str(error), "code": "invalid_keyword"}, status=400)

    try:
        result = execute_target_search(
            criteria=criteria,
            owner=get_request_owner(request),
            provider=_YahooSearchProvider(),
            repository=DjangoSearchRepository(),
            refresh_watch=refresh_watched_item,
            trigger=getattr(request, "search_trigger", "manual"),
            saved_search=getattr(request, "saved_search", None),
        )
        request.recorded_search_runs = list(result.runs)
        return JsonResponse(result.payload)
    except TargetSearchFailure as failure:
        request.recorded_search_runs = list(failure.completed_runs)
        error = failure.cause
        failure_code = (
            external_failure_code(error)
            if isinstance(error, ExternalServiceError)
            else FAILURE_UNEXPECTED
        )
        if failure.active_run is None:
            record_search_run(
                request,
                criteria.keyword,
                failure.search_type,
                0,
                succeeded=False,
                record_word=failure.search_type == SearchRun.CLOSED,
                criteria_snapshot=criteria.snapshot(),
                duration_ms=failure.duration_ms,
                failure_code=failure_code,
            )
        else:
            update_search_run_observability(
                failure.active_run,
                duration_ms=failure.duration_ms,
                succeeded=False,
                failure_code=failure_code,
            )
        if isinstance(error, ExternalServiceError):
            logger.error(
                "Complex market search failed",
                exc_info=(type(error), error, error.__traceback__),
            )
            return JsonResponse(
                {"error": EXTERNAL_SERVICE_MESSAGE, "code": "external_service_unavailable"},
                status=503,
            )
        logger.error(
            "Unexpected complex market search error",
            exc_info=(type(error), error, error.__traceback__),
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
