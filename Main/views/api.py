from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from Main.models.scraping import scraping
import numpy as np
from sklearn.cluster import KMeans

import logging
from datetime import datetime, timedelta

from .utils import scrape_data, save_to_database, scrape_current_listings, get_search_words

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


def prediction_market(request):
    """
    過去90日間の価格推移を分析し、異常値を排除した移動平均と1ヶ月予測を返す。
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    searchname = request.GET.get('keyword', '')
    if not searchname:
        return JsonResponse({'error': 'Keyword is required'}, status=400)

    try:
        # 過去180日間の落札データを取得
        closed_data = scrape_data(searchname)
        if not closed_data:
            return JsonResponse({'error': 'No data available'}, status=404)

        # 過去90日間のデータにフィルタリング
        current_date = datetime.now()
        past_90_days = current_date - timedelta(days=90)
        filtered_data = []
        for item in closed_data:
            if item['time'] != 'N/A':
                try:
                    month_day, time_part = item['time'].split()
                    month, day = month_day.split('/')
                    year = current_date.year
                    full_date = f"{year}-{month.zfill(2)}-{day.zfill(2)} {time_part}"
                    item_date = datetime.strptime(full_date, '%Y-%m-%d %H:%M')
                    if item_date >= past_90_days:
                        filtered_data.append(item)
                except Exception as e:
                    logger.error(
                        f"Date parsing error for {item['time']}: {str(e)}")
                    continue

        prices = [item['price'] for item in filtered_data if isinstance(
            item['price'], (int, float))]
        if not prices:
            return JsonResponse({'error': 'No price data in the last 90 days'}, status=404)

        # 異常値除去 (KMeansクラスタリング)
        if len(prices) > 10:  # 十分なデータがある場合
            kmeans = KMeans(n_clusters=2, random_state=42)  # 2クラスタで異常値と通常値を分離
            labels = kmeans.fit_predict(np.array(prices).reshape(-1, 1))
            # クラスタのサイズが小さい方を異常値とみなす
            cluster_sizes = np.bincount(labels)
            outlier_cluster = np.argmin(cluster_sizes)
            cleaned_prices = [p for i, p in enumerate(
                prices) if labels[i] != outlier_cluster]
        else:
            cleaned_prices = prices  # データが少ない場合はそのまま

        # 移動平均線 (30日)
        window_size = 30
        moving_averages = []
        for i in range(len(cleaned_prices)):
            if i >= window_size - 1:
                avg = np.mean(cleaned_prices[i - window_size + 1:i + 1])
                moving_averages.append(int(avg))
            else:
                moving_averages.append(None)

        # 1ヶ月予測 (最新の移動平均を基に簡易予測)
        latest_avg = moving_averages[-1] if moving_averages[-1] else np.mean(
            cleaned_prices)
        predicted_price = latest_avg * 1.02  # 仮に2%増加と仮定（トレンド調整可能）

        # 信頼区間（±10%）
        confidence_interval = [
            int(predicted_price * 0.9), int(predicted_price * 1.1)]

        # 過去90日分の価格推移と移動平均
        price_trends = [
            {'date': item['time'], 'price': item['price'],
                'moving_avg': moving_averages[i] if i < len(moving_averages) else None}
            for i, item in enumerate(filtered_data)
        ]

        # レスポンス準備
        response = {
            'keyword': searchname,
            'moving_average': int(np.mean(cleaned_prices) if cleaned_prices else 0),
            'predicted_price': int(predicted_price),
            'confidence_interval': confidence_interval,
            'price_trends': price_trends  # 過去90日分の推移と移動平均
        }

        return JsonResponse(response)

    except Exception as e:
        logger.error(f"Error in prediction_market: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
