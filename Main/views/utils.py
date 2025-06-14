from bs4 import BeautifulSoup

import requests
import re
import logging
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from Main.models.scraping import scraping
import numpy as np
from sklearn.cluster import KMeans

logger = logging.getLogger('search_logger')


def scrape_data(searchname):
    """
    指定されたキーワードでヤフオクの落札履歴をスクレイピングする。
    """
    base_url = 'https://auctions.yahoo.co.jp/closedsearch/closedsearch'
    urls = [
        f'{base_url}?p={searchname}&va={searchname}&b=1&n=100&select=6',
        f'{base_url}?p={searchname}&va={searchname}&b=101&n=100&select=6'
    ]

    scraped_data_list = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            # 商品名
            product_titles = soup.find_all(
                'a', class_=re.compile(r'Product__titleLink'))
            names = [title.text.strip()
                     for title in product_titles if title.text.strip()]

            # 落札価格
            price_elements = soup.find_all(
                'span', class_=re.compile(r'Product__priceValue'))
            prices = [
                int(re.sub(r'[^\d]+', '', price.text))
                for price in price_elements
                if price and "Product__priceValue--start" not in price.get('class', [])
            ]

            # 入札数
            bid_elements = soup.find_all(
                'a', class_=re.compile(r'Product__bid'))
            bids = [bid.text.strip()
                    for bid in bid_elements if bid.text.strip()]

            # 開始価格
            start_elements = soup.find_all('span', class_=re.compile(
                r'Product__priceValue Product__priceValue--start'))
            startprices = [
                int(re.sub(r'[^\d]+', '', price.text))
                for price in start_elements
                if price and price.text.strip()
            ]

            # URL
            urls = [title.get('href', '#')
                    for title in product_titles if title.get('href')]

            time_elements = soup.find_all(
                'span', class_='Product__time')  # 追加: 落札時間帯と日付
            times = [time.text.strip()
                     for time in time_elements if time.text.strip()]

            urls = [title.get('href', '#')
                    for title in product_titles if title.get('href')]

            # データのマッチングと結合
            min_length = min(len(names), len(prices), len(
                bids), len(startprices), len(urls))
            for i in range(min_length):
                scraped_data = {
                    'name': names[i],
                    'price': prices[i] if i < len(prices) else 0,
                    'startPrice': startprices[i] if i < len(startprices) else 0,
                    'bidding': bids[i] if i < len(bids) else 0,
                    'time': times[i] if i < len(times) else 'N/A',
                    'url': urls[i],
                }
                scraped_data_list.append(scraped_data)

        except requests.RequestException as e:
            logger.error(f"Request failed for URL {url}: {str(e)}")
            continue
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            continue

    return scraped_data_list[:200]


def scrape_current_listings(searchname):
    """
    指定されたキーワードでヤフオクの現在出品されている商品をスクレイピングする。
    """
    base_url = 'https://auctions.yahoo.co.jp/search/search'
    urls = [
        f'{base_url}?auccat=&tab_ex=commerce&aq=-&p={searchname}&f=0:1&b=1&n=100',
        f'{base_url}?auccat=&tab_ex=commerce&aq=-&p={searchname}&f=0:1&b=101&n=100'
    ]

    scraped_data_list = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 商品ごとに親要素でループ
            product_cards = soup.find_all('li', class_=re.compile(r'Product'))
            for card in product_cards:
                # 商品名
                title_tag = card.find(
                    'a', class_=re.compile(r'Product__titleLink'))
                name = title_tag.text.strip() if title_tag else 'N/A'
                url_ = title_tag['href'] if title_tag and title_tag.has_attr(
                    'href') else '#'

                # 現在価格
                price_tag = card.find(
                    'span', class_=re.compile(r'Product__priceValue'))
                price = 0
                if price_tag:
                    price_text = price_tag.text
                    price = int(
                        re.sub(r'[^\d]+', '', price_text)) if price_text else 0

                # 入札数
                bid_tag = card.find('dd', class_=re.compile(r'Product__bid'))
                bidding = 0
                if bid_tag:
                    bidding_text = bid_tag.text
                    bidding = int(
                        re.sub(r'[^\d]+', '', bidding_text)) if bidding_text else 0

                # 残り時間
                time_tag = card.find('dd', class_=re.compile(r'Product__time'))
                remaining_time = time_tag.text.strip() if time_tag else 'N/A'

                scraped_data_list.append({
                    'name': name,
                    'currentPrice': price,
                    'bidding': bidding,
                    'remainingTime': remaining_time,
                    'url': url_
                })

        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            continue

    return scraped_data_list[:200]  # 最大200件を返す


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
                Name=scraped_data['name'],
                EndPrice=scraped_data['price'],
                StartPrice=scraped_data['startPrice'],
                Bidding=scraped_data['bidding'],
                URL=scraped_data['url']
            )
        except Exception as e:
            print(f"Error inserting into the database: {e}")


def get_search_words_logic(request):
    """
    データベースからユニークな検索ワードのリストを取得する。
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    try:
        search_words = scraping.objects.values_list(
            'SearchWord', flat=True).distinct()
        return JsonResponse({'searchWords': list(search_words)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_market_data_logic(request):
    """
    指定キーワードの取引データをデータベースから取得し、JSONで返す。
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
def update_market_data_logic(request):
    """
    指定キーワードで新たにデータを取得し、データベースを更新する。
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
def delete_market_data_logic(request):
    """
    指定キーワードの取引データをデータベースから削除する。
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


def complex_market_data_logic(request):
    """
    指定キーワードの落札履歴と現在出品中データから、価格リスト・商品名リスト・中央値・おすすめ出品リストを返す。
    また、落札履歴データはデータベースにも保存・更新する。
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    searchname = request.GET.get('keyword', '')
    if not searchname:
        return JsonResponse({'error': 'Keyword is required'}, status=400)

    try:
        # 落札履歴データ取得＆DB更新
        closed_data = scrape_data(searchname)
        save_to_database(searchname, closed_data)
        closed_prices = [item['price'] for item in closed_data if 'price' in item and isinstance(
            item['price'], (int, float))]
        closed_names = [item['name'] for item in closed_data if 'name' in item]

        # 現在出品中データ
        now_data = scrape_current_listings(searchname)

        def parse_time(time_str):
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
            import numpy as np
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
            'closed_prices': closed_prices,
            'closed_names': closed_names,
            'medianPrice': median_price,
            'recommend_items': response_items
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def prediction_market_logic(request):
    """
    過去90日間の価格推移取得し、分析、クラスタリングを行う
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
            cluster_sizes = np.bincount(labels)
            outlier_cluster = np.argmin(cluster_sizes)
            cleaned_prices = [p for i, p in enumerate(
                prices) if labels[i] != outlier_cluster]
        else:
            cleaned_prices = prices  # データが少ない場合はそのまま

        # 90日移動平均線
        window_size = 90
        moving_averages = []
        for i in range(len(cleaned_prices)):
            if i >= window_size - 1 and len(cleaned_prices) >= window_size:
                avg = np.mean(cleaned_prices[i - window_size + 1:i + 1])
                moving_averages.append(int(avg))
            else:
                moving_averages.append(None)

        # 1ヶ月予測 (最新の移動平均を基に)
        latest_avg = moving_averages[-1] if moving_averages[-1] is not None else np.mean(
            cleaned_prices)
        predicted_price = latest_avg * 1.02  # 仮に2%増加（トレンド調整可能）

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
