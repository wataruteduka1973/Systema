from django.urls import path
from Main.views.urls import (
    index,
    Yahuoku,
    Yahuoku_now,
    Deep_Analysis,
    Deep_Analysis_now,
    Yahuoku_history,
    Yahuoku_prediction,
    introduction,
)
from Main.views.api import (
    perform_search,
    RealtimeSearch,
    get_search_words,
    get_market_data,
    update_market_data,
    delete_market_data,
    complex_market_data,
    prediction_market,
    get_popular_words,
)

urlpatterns = [
    path('', index, name='index'),
    path('yahuoku', Yahuoku, name='yahuoku'),
    path('yahuoku_now', Yahuoku_now, name='yahuoku_now'),
    path('yahuoku_history', Yahuoku_history, name='yahuoku_history'),
    path('Deep_Analysis', Deep_Analysis, name='Deep_Analysis'),
    path('Deep_Analysis_now', Deep_Analysis_now, name='Deep_Analysis_now'),
    path('Yahuoku_prediction', Yahuoku_prediction, name='Yahuoku_prediction'),
    path('introduction', introduction, name='introduction'),
    path('perform_search', perform_search, name='perform_search'),
    path('RealtimeSearch', RealtimeSearch, name='RealtimeSearch'),
    path('get_search_words', get_search_words, name='get_search_words'),
    path('get_market_data', get_market_data, name='get_market_data'),
    path('update_market_data', update_market_data, name='update_market_data'),
    path('delete_market_data', delete_market_data, name='delete_market_data'),
    path('complex_market_data', complex_market_data, name='complex_market_data'),
    path('prediction_market', prediction_market, name='prediction_market'),
    path('get_popular_words', get_popular_words, name='get_popular_words'),
]
