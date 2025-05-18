from django.http import JsonResponse
from .utils import scrape_data, save_to_database
import logging

# ロガーの取得
logger = logging.getLogger('search_logger')


def perform_search(request):
    logger.info("Logger initialized")
    print("Logger initialized")

    if request.method == 'GET':
        searchname = request.GET.get('keyword', '')
        logger.info(f"Search started for keyword: {searchname}")

        try:
            scraped_data_list = scrape_data(searchname)
            logger.info(
                f"Scraped {len(scraped_data_list)} items for keyword: {searchname}")
            save_to_database(searchname, scraped_data_list)
            logger.info(f"Data saved to database for keyword: {searchname}")
            return JsonResponse({'data': scraped_data_list})
        except Exception as e:
            logger.error(
                f"Error during search for keyword {searchname}: {str(e)}")
            return JsonResponse({'error': 'An error occurred'}, status=500)

    logger.warning("Invalid request method received")
    return JsonResponse({'error': 'Invalid request method'}, status=400)
