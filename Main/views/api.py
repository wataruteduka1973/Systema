import logging
import numpy as np
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


def complex_market_data(request):
    """
    APIエンドポイントで、指定キーワードの落札履歴と現在出品中データから
    金額リストと商品名リストを返す。さらに、落札価格の中央値に近く、
    残り時間が短い現在出品中商品を優先して30件抽出して返す。
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    searchname = request.GET.get('keyword', '')
    if not searchname:
        return JsonResponse({'error': 'Keyword is required'}, status=400)

    try:
        # 落札履歴データ
        closed_data = scrape_data(searchname)
        closed_prices = [item['price'] for item in closed_data if 'price' in item and isinstance(
            item['price'], (int, float))]

        # 現在出品中データ
        now_data = scrape_current_listings(searchname)
        # 残り時間を秒数に変換する関数

        def parse_time(time_str):
            # 例: "1日 2時間 3分" → 秒数
            if not isinstance(time_str, str):
                return float('inf')
            days = hours = minutes = 0
            import re
            m = re.search(r'(\d+)日', time_str)
            if m:
                days = int(m.group(1))
            m = re.search(r'(\d+)時間', time_str)
            if m:
                hours = int(m.group(1))
            m = re.search(r'(\d+)分', time_str)
            if m:
                minutes = int(m.group(1))
            return days * 86400 + hours * 3600 + minutes * 60

        now_items = []
        for item in now_data:
            price = item.get('currentPrice')
            name = item.get('name')
            url = item.get('url')
            remaining_time_str = item.get('remainingTime')
            bidding = item.get('bidding', 0)
            remaining_seconds = parse_time(remaining_time_str)
            now_items.append({
                'price': price,
                'name': name,
                'url': url,
                'remainingTime': remaining_time_str,
                'remainingSeconds': remaining_seconds,
                'bidding': bidding
            })

        if closed_prices:
            median_price = float(np.median(closed_prices))
        else:
            median_price = 0

        def score(item):
            price = item['price'] if isinstance(
                item['price'], (int, float)) else 0
            price_diff = abs(price - median_price)
            remaining = item['remainingSeconds']
            return price_diff + (remaining / 300)

        now_items_sorted = sorted(now_items, key=score)[:30]

        response_items = [
            {
                'price': item['price'],
                'name': item['name'],
                'url': item['url'],
                'remainingTime': item['remainingTime'],
                'bidding': item['bidding']
            }
            for item in now_items_sorted
        ]

        return JsonResponse({
            'medianPrice': median_price,
            'recommend_items': response_items
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
