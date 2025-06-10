from django.urls import path
from Main.views.urls import index, Yahuoku, Yahuoku_now, Deep_Analysis, Deep_Analysis_now, Yahuoku_history
from Main.views.api import perform_search, RealtimeSearch, get_search_words_api, get_market_data, update_market_data, delete_market_data

urlpatterns = [
    path('', index, name='index'),
    path('yahuoku/', Yahuoku, name='yahuoku'),
    path('yahuoku_now/', Yahuoku_now, name='yahuoku_now'),
    path('Deep_Analysis/', Deep_Analysis, name='Deep_Analysis'),
    path('perform_search/', perform_search, name='perform_search'),
    path('RealtimeSearch/', RealtimeSearch, name='RealtimeSearch'),
    path('yahuoku_history/', Yahuoku_history, name='yahuoku_history'),
    path('Deep_Analysis_now/', Deep_Analysis_now, name='Deep_Analysis_now'),
    path('get_search_words/', get_search_words_api, name='get_search_words'),
    path('get_market_data/', get_market_data, name='get_market_data'),
    path('update_market_data', update_market_data, name='update_market_data'),
    path('delete_market_data', delete_market_data, name='delete_market_data'),
]
