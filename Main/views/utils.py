from bs4 import BeautifulSoup
import requests
import re
from datetime import datetime
from Main.models import scraping


def scrape_data(searchname):
    base_url = 'https://auctions.yahoo.co.jp/closedsearch/closedsearch'
    urls = [
        f'{base_url}?p={searchname}&va={searchname}&b=1&n=100&select=6',
        f'{base_url}?p={searchname}&va={searchname}&b=101&n=100&select=6'
    ]

    scraped_data_list = []
    for url in urls:
        response = requests.get(url)
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        product_titles = soup.find_all('a', class_='Product__titleLink')
        names = [title.text for title in product_titles]

        Product__priceValue = soup.find_all(
            'span', class_='Product__priceValue')
        prices = [int(re.sub(r'[^\d]+', '', price.text))
                  for price in Product__priceValue if "Product__priceValue--start" not in price['class']]

        Product__bid = soup.find_all('a', class_='Product__bid')
        bids = [title.text for title in Product__bid]

        Product__start = soup.find_all(
            'span', class_='Product__priceValue Product__priceValue--start')
        startprices = [int(re.sub(r'[^\d]+', '', priceValue.text))
                       for priceValue in Product__start]

        for name, price, bid, startprice in zip(names, prices, bids, startprices):
            url_value = product_titles[names.index(name)]['href']
            scraped_data = {
                'name': name,
                'price': price,
                'startPrice': startprice,
                'bidding': bid,
                'url': url_value,
            }
            scraped_data_list.append(scraped_data)

    return scraped_data_list


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
