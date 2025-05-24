from django.urls import path
from Main.views.urls import index, Yahuoku, Yahuoku_now
from Main.views.api import perform_search, RealtimeSearch

urlpatterns = [
    path('', index, name='index'),
    path('yahuoku/', Yahuoku, name='yahuoku'),
    path('yahuoku_now/', Yahuoku_now, name='yahuoku_now'),
    path('perform_search/', perform_search, name='perform_search'),
    path('RealtimeSearch/', RealtimeSearch, name='RealtimeSearch'),


]
