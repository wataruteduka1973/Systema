import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

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


def handle_search_response(request, data_fetch_func, save_func=None):
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
        return JsonResponse({"data": scraped_data_list})
    except Exception as e:
        logger.error(f"Error during search for keyword {searchname}: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


def perform_search(request):
    """
    相場のデータを取得して処理する。
    """
    return handle_search_response(request, scrape_data, save_to_database)


def RealtimeSearch(request):
    """
    現在出品されている商品のデータを取得して処理する。
    """
    return handle_search_response(request, scrape_current_listings)


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
