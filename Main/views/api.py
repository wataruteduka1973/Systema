import logging
from django.http import JsonResponse
from django.shortcuts import render
from .utils import scrape_data, save_to_database, scrape_current_listings

logger = logging.getLogger('search_logger')


def handle_search_response(request, data_fetch_func, save_func=None):
    logger.info("Logger initialized")
    if request.method != 'GET':
        logger.warning("Invalid request method received")
        return render(request, '400.html', status=400)

    searchname = request.GET.get('keyword', '')
    logger.info(f"Search started for keyword: {searchname}")

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
