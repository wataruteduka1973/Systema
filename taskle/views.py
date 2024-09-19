from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.http import HttpResponseNotAllowed
from django.views.decorators.http import require_http_methods
from bs4 import BeautifulSoup
import requests

from .models import SelectDestination
from .models import scraping

from datetime import datetime
import os
import re


def index(request):
    # プロジェクトのベースディレクトリを取得し、StartMenu.htmlをレンダリング
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(
        BASE_DIR, 'taskle', 'templates', 'StartMenu.html')
    return render(request, template_path)


def SendMailMode(request):
    # DeleteFlagが0のSelectDestinationオブジェクトをフィルタリングし、Sendmail.htmlをレンダリング
    objectives = SelectDestination.objects.filter(DeleteFlag=0)
    return render(request, 'Sendmail.html', {'objectives': objectives})


def Yahuoku(request):
    # Yahuoku.htmlをレンダリング
    return render(request, 'Yahuoku.html')


def change_template(request):
    # POSTリクエストを受け取り、指定されたObjectiveのテンプレートデータを更新
    if request.method == 'POST':
        objective_value = request.POST.get('Objective', None)
        template_data = get_object_or_404(
            SelectDestination, Objective=objective_value)
        template_data.Adress = request.POST.get('Adress', template_data.Adress)
        template_data.Subject = request.POST.get(
            'Subject', template_data.Subject)
        template_data.Mailtext = request.POST.get(
            'Mailtext', template_data.Mailtext)
        template_data.save()
        return JsonResponse({'status': 'success', 'message': 'テンプレートを変更しました。'})
    else:
        return JsonResponse({'status': 'error', 'message': 'POSTリクエストがありません。'})


def delete_template(request):
    # POSTリクエストを受け取り、指定されたObjectiveのテンプレートデータを削除（DeleteFlagを変更）
    if request.method == 'POST':
        objective_value = request.POST.get('Objective', None)
        template_data = get_object_or_404(
            SelectDestination, Objective=objective_value)
        template_data.Objective = 'DELETEDETA'
        template_data.DeleteFlag = request.POST.get(
            'DeleteFlag', template_data.DeleteFlag)
        template_data.save()
        return JsonResponse({'status': 'success', 'message': 'テンプレートを削除しました。'})
    else:
        return JsonResponse({'status': 'error', 'message': 'POSTリクエストがありません。'})


def add_template(request):
    # POSTリクエストを受け取り、新しいテンプレートデータを追加または既存のデータを更新
    if request.method == 'POST':
        objective_value = request.POST.get('Objective', None)
        # データの妥当性を確認
        if not objective_value:
            return JsonResponse({'status': 'error', 'message': 'Objectiveが提供されていません'})
        template_data, created = SelectDestination.objects.get_or_create(
            Objective=objective_value)
        template_data.Objective = request.POST.get(
            'Objective', template_data.Objective)
        template_data.Adress = request.POST.get('Adress', template_data.Adress)
        template_data.Subject = request.POST.get(
            'Subject', template_data.Subject)
        template_data.Mailtext = request.POST.get(
            'Mailtext', template_data.Mailtext)
        template_data.Todays = request.POST.get('Todays', template_data.Todays)
        template_data.DeleteFlag = request.POST.get(
            'DeleteFlag', template_data.DeleteFlag)

        try:
            template_data.save()
            return JsonResponse({'status': 'success', 'message': 'テンプレートを作成しました。'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'保存エラー: {str(e)}'})

    else:
        return JsonResponse({'status': 'error', 'message': 'POSTリクエストがありません。'})


@require_http_methods(["POST"])
def update_fields(request, **kwargs):
    # POSTリクエストを受け取り、指定されたObjectiveに基づいてフィールドデータを更新
    selected_Option = kwargs['selected_Option']
    if request.method == 'POST':
        objective = SelectDestination.objects.filter(
            Objective=selected_Option).first()

        if objective:
            data = {
                'Adress': objective.Adress,
                'Mailtext': objective.Mailtext,
                'Subject': objective.Subject,
                'Todays': objective.Todays,
            }
            return JsonResponse(data)
        else:
            return HttpResponse(status=404)
    else:
        return HttpResponseNotAllowed(['POST'])


def delete_fields(request, **kwargs):
    # POSTリクエストを受け取り、指定されたObjectiveに基づいてフィールドデータを更新
    selected_Option = kwargs['selected_Option']
    if request.method == 'POST':
        objective = SelectDestination.objects.filter(
            Objective=selected_Option).first()

        if objective:
            data = {
                'Adress': objective.Adress,
                'Mailtext': objective.Mailtext,
                'Subject': objective.Subject,
                'Todays': objective.Todays,
            }
            return JsonResponse(data)
        else:
            return HttpResponse(status=404)
    else:
        return HttpResponseNotAllowed(['POST'])


def perform_search(request):
    # GETリクエストを受け取り、指定されたキーワードでデータをスクレイピングし、データベースに保存
    if request.method == 'GET':
        # クエリパラメータから検索キーワードを取得
        searchname = request.GET.get('keyword', '')
        # スクレイピング関数を呼び出し、データを取得
        scraped_data_list = scrape_data(searchname)
        # 取得したデータをデータベースに保存
        save_to_database(searchname, scraped_data_list)
        # スクレイピングしたデータをJSONで返す
        return JsonResponse({'data': scraped_data_list})
    # GET以外のリクエストが来た場合のエラーレスポンス
    return JsonResponse({'error': 'Invalid request method'})


def scrape_data(searchname):
    base_url = 'https://auctions.yahoo.co.jp/closedsearch/closedsearch'
    urls = [
        f'{base_url}?p={searchname}&va={searchname}&b=1&n=100&select=6',
        f'{base_url}?p={searchname}&va={searchname}&b=101&n=100&select=6'
    ]

    scraped_data_list = []  # スクレイピングしたデータを格納するリスト

    for url in urls:
        response = requests.get(url)
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # 商品のタイトルを取得
        product_titles = soup.find_all('a', class_='Product__titleLink')
        names = [title.text for title in product_titles]  # タイトルテキストをリストに格納

        # 商品の価格を取得し、数値に変換
        Product__priceValue = soup.find_all(
            'span', class_='Product__priceValue')
        prices = [int(re.sub(r'[^\d]+', '', price.text))
                  for price in Product__priceValue if "Product__priceValue--start" not in price['class']]

        # 入札情報を取得
        Product__bid = soup.find_all('a', class_='Product__bid')
        bids = [title.text for title in Product__bid]

        # 開始価格を取得し、数値に変換
        Product__start = soup.find_all(
            'span', class_='Product__priceValue Product__priceValue--start')
        startprices = [int(re.sub(r'[^\d]+', '', priceValue.text))
                       for priceValue in Product__start]

        # 各商品情報を辞書にまとめ、リストに追加
        for name, price, bid, startprice in zip(names, prices, bids, startprices):
            url_value = product_titles[names.index(name)]['href']  # 商品のURLを取得
            scraped_data = {
                'name': name,
                'price': price,
                'startPrice': startprice,
                'bidding': bid,
                'url': url_value,
            }

            scraped_data_list.append(scraped_data)

    return scraped_data_list  # スクレイピングしたデータを返す


def save_to_database(searchname, scraped_data_list):
    # スクレイピングしたデータをデータベースに保存
    now_time = datetime.now()  # 現在の日時を取得
    SearchDay = now_time.strftime("%Y-%m-%d %H:%M:%S")  # 日時を文字列にフォーマット

    # 各スクレイピングデータをデータベースに挿入
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
            # データベースへの挿入が失敗した場合はエラーメッセージを出力
            print(f"Error inserting into the database: {e}")
