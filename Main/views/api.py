import json
import logging

from django.http import JsonResponse

from Main.domain.product_condition import enrich_market_items, summarize_condition_market
from Main.models.watchitem import WatchItem
from Main.services.exceptions import (
    ExternalServiceError,
    SearchInputError,
    SearchRateLimitError,
)
from Main.services.external_search import enforce_search_rate_limit
from Main.services.market_statistics import (
    analyze_market_prices,
    enrich_items_with_market_comparison,
)
from Main.services.ownership import get_request_owner, owner_query
from Main.services.search_criteria import SearchCriteria
from Main.services.search_observability import (
    FAILURE_EXTERNAL_SERVICE,
    FAILURE_UNEXPECTED,
    SearchTimer,
)
from Main.services.watchlist import (
    list_watch_items,
    save_watch_item,
    serialize_watch_item,
)

from .utils import (
    complex_market_data_logic,
    delete_market_data_logic,
    get_market_data_logic,
    get_popular_words_logic,
    get_search_words_logic,
    prediction_market_logic,
    record_search_run,
    save_to_database,
    scrape_current_listings,
    scrape_data,
    update_market_data_logic,
    update_search_run_observability,
)

logger = logging.getLogger("search_logger")

EXTERNAL_SERVICE_MESSAGE = "外部サービスからデータを取得できませんでした"


def _external_search_guard(request, search_type="closed"):
    try:
        criteria = SearchCriteria.from_query(request.GET, search_type)
        enforce_search_rate_limit(request)
        return criteria, None
    except SearchInputError as error:
        return None, JsonResponse({"error": str(error), "code": "invalid_keyword"}, status=400)
    except SearchRateLimitError as error:
        response = JsonResponse({"error": str(error), "code": "rate_limit_exceeded"}, status=429)
        response["Retry-After"] = str(error.retry_after)
        return None, response


def handle_search_response(
    request,
    data_fetch_func,
    save_func=None,
    include_condition_analysis=False,
    search_type="closed",
):
    """
    共通の検索処理を行うヘルパー関数。
    """
    logger.info("Logger initialized")
    if request.method != "GET":
        logger.warning("Invalid request method received")
        return JsonResponse({"error": "Invalid request method"}, status=400)

    criteria, guard_response = _external_search_guard(request, search_type)
    if guard_response is not None:
        return guard_response
    searchname = criteria.keyword
    logger.info("External search started keyword_length=%s", len(searchname))
    timer = SearchTimer.start()
    search_run = None

    try:
        scraped_data_list = criteria.apply(data_fetch_func(searchname))
        logger.info(f"Scraped {len(scraped_data_list)} items for keyword: {searchname}")
        search_run = record_search_run(
            request,
            searchname,
            search_type,
            len(scraped_data_list),
            criteria_snapshot=criteria.snapshot(),
            duration_ms=timer.elapsed_ms(),
        )
        if save_func:
            save_func(searchname, scraped_data_list, search_run)
            logger.info(f"Data saved to database for keyword: {searchname}")
        response_data = {"data": scraped_data_list}
        if include_condition_analysis:
            enriched_items = enrich_market_items(scraped_data_list)
            market_statistics = analyze_market_prices(enriched_items)
            enriched_items = enrich_items_with_market_comparison(
                enriched_items, market_statistics["median"]
            )
            response_data = {
                "data": enriched_items,
                "conditionSummary": summarize_condition_market(enriched_items),
                "marketStatistics": market_statistics,
            }
        update_search_run_observability(search_run, duration_ms=timer.elapsed_ms())
        return JsonResponse(response_data)
    except ExternalServiceError:
        logger.exception("External search failed")
        if search_run is None:
            record_search_run(
                request,
                searchname,
                search_type,
                0,
                succeeded=False,
                criteria_snapshot=criteria.snapshot(),
                duration_ms=timer.elapsed_ms(),
                failure_code=FAILURE_EXTERNAL_SERVICE,
            )
        else:
            update_search_run_observability(
                search_run,
                duration_ms=timer.elapsed_ms(),
                succeeded=False,
                failure_code=FAILURE_EXTERNAL_SERVICE,
            )
        return JsonResponse(
            {"error": EXTERNAL_SERVICE_MESSAGE, "code": "external_service_unavailable"},
            status=503,
        )
    except Exception:
        logger.exception("Unexpected external search error")
        if search_run is None:
            record_search_run(
                request,
                searchname,
                search_type,
                0,
                succeeded=False,
                criteria_snapshot=criteria.snapshot(),
                duration_ms=timer.elapsed_ms(),
                failure_code=FAILURE_UNEXPECTED,
            )
        else:
            update_search_run_observability(
                search_run,
                duration_ms=timer.elapsed_ms(),
                succeeded=False,
                failure_code=FAILURE_UNEXPECTED,
            )
        return JsonResponse(
            {"error": "検索処理中にエラーが発生しました", "code": "search_failed"},
            status=500,
        )


def perform_search(request):
    """
    相場のデータを取得して処理する。
    """
    return handle_search_response(
        request, scrape_data, save_to_database, include_condition_analysis=True
    )


def RealtimeSearch(request):
    """
    現在出品されている商品のデータを取得して処理する。
    """
    return handle_search_response(
        request,
        scrape_current_listings,
        save_to_database,
        include_condition_analysis=True,
        search_type="current",
    )


def get_search_words(request):
    """
    データベースにアクセスして過去の検索履歴を取得する
    """
    return get_search_words_logic(request)


def get_market_data(request):
    """
    データベースにアクセスして過去の検索履歴を取得する。
    """
    return get_market_data_logic(request)


def update_market_data(request):
    """
    フロントエンドから取得した対象を更新する
    """
    if request.method == "POST":
        criteria, guard_response = _external_search_guard(request)
        if guard_response is not None:
            return guard_response
        return update_market_data_logic(request, criteria)
    return update_market_data_logic(request)


def delete_market_data(request):
    """
    フロントエンドから取得した対象を削除する
    """
    return delete_market_data_logic(request)


def complex_market_data(request):
    """
    指定キーワードの落札履歴と現在出品中データを取得し、分析結果を返す
    """
    if request.method == "GET":
        criteria, guard_response = _external_search_guard(request, "target")
        if guard_response is not None:
            return guard_response
        return complex_market_data_logic(request, criteria)
    return complex_market_data_logic(request)


def prediction_market(request):
    """
    過去90日間の価格推移を分析し、異常値を排除した90日移動平均と1ヶ月予測を返す。
    """
    if request.method == "GET":
        criteria, guard_response = _external_search_guard(request, "prediction")
        if guard_response is not None:
            return guard_response
        return prediction_market_logic(request, criteria)
    return prediction_market_logic(request)


def get_popular_words(request):
    """
    使用頻度の高い検索ワードを返す
    """
    return get_popular_words_logic(request)


def watchlist(request):
    """Systema内のウォッチリストを取得、または商品を登録する。"""
    owner = get_request_owner(request)
    if request.method == "GET":
        return JsonResponse({"items": list_watch_items(owner)})
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        payload = json.loads(request.body or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("リクエスト形式が正しくありません")
        item, created = save_watch_item(payload, owner)
        return JsonResponse(
            {"item": serialize_watch_item(item), "created": created},
            status=201 if created else 200,
        )
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"error": str(error)}, status=400)


def watchlist_item(request, item_id):
    """ウォッチ商品を解除する。"""
    owner = get_request_owner(request)
    if request.method != "DELETE":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    deleted, _ = WatchItem.objects.filter(owner_query(owner), pk=item_id).delete()
    if not deleted:
        return JsonResponse({"error": "Watch item not found"}, status=404)
    return JsonResponse({"message": "ウォッチを解除しました"})
