import logging
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .utils import scrape_data, save_to_database, scrape_current_listings, get_search_words
from Main.models.scraping import scraping

logger = logging.getLogger('search_logger')


def handle_search_response(request, data_fetch_func, save_func=None):
    """
    検索リクエストを処理し、スクレイピングされたデータを含むJSONレスポンスを返す。
    """
    logger.info("Logger initialized")
    if request.method != 'GET':
        logger.warning("Invalid request method received")
        return render(request, '400.html', status=400)

    searchname = request.GET.get('keyword', '')
    logger.info(f"Search started for keyword: {searchname}")
    if not searchname:
        return render(request, '400.html', status=400)

    try:
        scraped_data_list = data_fetch_func(searchname)
        logger.info(
            f"Scraped {len(scraped_data_list)} items for keyword: {searchname}")
        if save_func:
            save_func(searchname, scraped_data_list)
            logger.info(f"Data saved to database for keyword: {searchname}")
        return JsonResponse({'data': scraped_data_list})
    except Exception as e:
        logger.error(f"Error during search for keyword {searchname}: {str(e)}")
        return render(request, '500.html', status=500)


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


def get_search_words_api(request):
    """
    APIエンドポイントで、検索ワードのリストを取得する。
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    try:
        search_words = get_search_words()
        return JsonResponse({'searchWords': search_words})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_market_data(request):
    """
    APIエンドポイントで、特定のキーワードに関連する相場データを取得する。
    """
    searchname = request.GET.get('keyword', '')
    if not searchname:
        return JsonResponse({'error': 'Keyword is required'}, status=400)

    try:
        data = list(scraping.objects.filter(SearchWord=searchname).values())
        search_day = scraping.objects.filter(
            SearchWord=searchname).values_list('SearchDay', flat=True).first()
        return JsonResponse({'data': data, 'searchDay': search_day})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def update_market_data(request):
    """
    APIエンドポイントで、特定のキーワードに関連する相場データを更新する。
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    searchname = request.GET.get('keyword', '')
    if not searchname:
        return JsonResponse({'error': 'Keyword is required'}, status=400)
    try:
        scraped_data_list = scrape_data(searchname)
        save_to_database(searchname, scraped_data_list)
        return JsonResponse({'message': '相場データを更新しました'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def delete_market_data(request):
    """
    APIエンドポイントで、特定のキーワードに関連する相場データを削除する。
    """
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    searchname = request.GET.get('keyword', '')
    if not searchname:
        return JsonResponse({'error': 'Keyword is required'}, status=400)
    try:
        scraping.objects.filter(SearchWord=searchname).delete()
        return JsonResponse({'message': '相場データを削除しました'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
