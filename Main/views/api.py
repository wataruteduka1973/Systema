import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from Main.domain.product_condition import enrich_market_items, summarize_condition_market
from Main.models.watchitem import WatchItem
from Main.services.market_statistics import (
    analyze_market_prices,
    enrich_items_with_market_comparison,
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
    save_to_database,
    scrape_current_listings,
    scrape_data,
    update_market_data_logic,
)

logger = logging.getLogger("search_logger")


def handle_search_response(
    request, data_fetch_func, save_func=None, include_condition_analysis=False
):
    """
    共通の検索処理を行うヘルパー関数。
    """
    logger.info("Logger initialized")
    if request.method != "GET":
        logger.warning("Invalid request method received")
        return JsonResponse({"error": "Invalid request method"}, status=400)

    searchname = request.GET.get("keyword", "")
    logger.info(f"Search started for keyword: {searchname}")
    if not searchname:
        return JsonResponse({"error": "Keyword is required"}, status=400)
    if request.method not in ["GET", "POST", "DELETE"]:
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        scraped_data_list = data_fetch_func(searchname)
        logger.info(f"Scraped {len(scraped_data_list)} items for keyword: {searchname}")
        if save_func:
            save_func(searchname, scraped_data_list)
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
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(f"Error during search for keyword {searchname}: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


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
    return handle_search_response(request, scrape_current_listings, include_condition_analysis=True)


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


@csrf_exempt
def update_market_data(request):
    """
    フロントエンドから取得した対象を更新する
    """
    return update_market_data_logic(request)


@csrf_exempt
def delete_market_data(request):
    """
    フロントエンドから取得した対象を削除する
    """
    return delete_market_data_logic(request)


def complex_market_data(request):
    """
    指定キーワードの落札履歴と現在出品中データを取得し、分析結果を返す
    """
    return complex_market_data_logic(request)


def prediction_market(request):
    """
    過去90日間の価格推移を分析し、異常値を排除した90日移動平均と1ヶ月予測を返す。
    """
    return prediction_market_logic(request)


def get_popular_words(request):
    """
    使用頻度の高い検索ワードを返す
    """
    return get_popular_words_logic(request)


@csrf_exempt
def watchlist(request):
    """Systema内のウォッチリストを取得、または商品を登録する。"""
    if request.method == "GET":
        return JsonResponse({"items": list_watch_items()})
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        payload = json.loads(request.body or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("リクエスト形式が正しくありません")
        item, created = save_watch_item(payload)
        return JsonResponse(
            {"item": serialize_watch_item(item), "created": created},
            status=201 if created else 200,
        )
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"error": str(error)}, status=400)


@csrf_exempt
def watchlist_item(request, item_id):
    """ウォッチ商品を解除する。"""
    if request.method != "DELETE":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    deleted, _ = WatchItem.objects.filter(pk=item_id).delete()
    if not deleted:
        return JsonResponse({"error": "Watch item not found"}, status=404)
    return JsonResponse({"message": "ウォッチを解除しました"})
