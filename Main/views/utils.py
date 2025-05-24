from bs4 import BeautifulSoup
from datetime import datetime
from Main.models import scraping

import requests
import re
import logging


logger = logging.getLogger('search_logger')


def scrape_data(searchname):
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

            # データのマッチングと結合
            min_length = min(len(names), len(prices), len(
                bids), len(startprices), len(urls))
            for i in range(min_length):
                scraped_data = {
                    'name': names[i],
                    'price': prices[i] if i < len(prices) else 0,
                    'startPrice': startprices[i] if i < len(startprices) else 0,
                    'bidding': bids[i] if i < len(bids) else 0,
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
    base_url = 'https://auctions.yahoo.co.jp/search/search'
    urls = [
        f'{base_url}?auccat=&tab_ex=commerce&aq=-&p={searchname}&f=0:1&b=1&n=100',

        f'{base_url}?auccat=&tab_ex=commerce&aq=-&p={searchname}&f=0:1&b=101&n=100'
    ]

    scraped_data_list = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # HTTPエラーをチェック
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            # 商品名
            product_titles = soup.find_all(
                'a', class_=re.compile(r'Product__titleLink'))
            names = [title.text.strip()
                     for title in product_titles if title.text.strip()]

            # 現在価格
            price_elements = soup.find_all(
                'span', class_=re.compile(r'Product__priceValue'))
            current_prices = [
                int(re.sub(r'[^\d]+', '', price.text))
                for price in price_elements
                if price and "Product__priceValue--start" not in price.get('class', [])

            ]

            # 入札数
            bid_elements = soup.find_all(
                'dd', class_=re.compile(r'Product__bid'))
            bids = [bid.text.strip()
                    for bid in bid_elements if bid.text.strip()]

            # 残り時間
            time_elements = soup.find_all(
                'dd', class_=re.compile(r'Product__time'))
            remaining_times = [time.text.strip()
                               for time in time_elements if time.text.strip()]

            # URL
            urls = [title.get('href', '#')
                    for title in product_titles if title.get('href')]

            # データのマッチングと結合
            min_length = min(len(names), len(current_prices),
                             len(bids), len(remaining_times), len(urls))
            for i in range(min_length):
                scraped_data = {
                    'name': names[i],
                    'currentPrice': current_prices[i] if i < len(current_prices) else '0',
                    'bidding': bids[i] if i < len(bids) else '0',
                    'remainingTime': remaining_times[i] if i < len(remaining_times) else 'N/A',
                    'url': urls[i],
                }
                scraped_data_list.append(scraped_data)
        except requests.RequestException as e:
            logger.error(f"Request failed for URL {url}: {str(e)}")
            continue
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            continue

    return scraped_data_list[:200]  # 最大200件を返す


def save_to_database(searchname, scraped_data_list):
    now_time = datetime.now()
    SearchDay = now_time.strftime("%Y-%m-%d %H:%M:%S")

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
