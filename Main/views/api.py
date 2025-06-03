import logging
from django.http import JsonResponse
from django.shortcuts import render
from .utils import scrape_data, save_to_database, scrape_current_listings, get_search_words
from Main.models.scraping import scraping

logger = logging.getLogger('search_logger')


def handle_search_response(request, data_fetch_func, save_func=None):
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
    return handle_search_response(request, scrape_data, save_to_database)


def RealtimeSearch(request):
    return handle_search_response(request, scrape_current_listings)


def get_search_words_api(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    try:
        search_words = get_search_words()
        return JsonResponse({'searchWords': search_words})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_market_data(request):
    searchname = request.GET.get('keyword', '')
    if not searchname:
        return JsonResponse({'error': 'Keyword is required'}, status=400)

    try:
        data = list(scraping.objects.filter(SearchWord=searchname).values())
        search_day = scraping.objects.filter(SearchWord=searchname).values_list('SearchDay', flat=True).first()
        return JsonResponse({'data': data, 'searchDay': search_day})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
