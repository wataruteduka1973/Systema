from django.urls import path
from Main.views.index import index
from Main.views.yahuoku import Yahuoku
from Main.views.api import perform_search

urlpatterns = [
    path('', index, name='index'),
    path('yahuoku/', Yahuoku, name='yahuoku'),
    path('perform_search/', perform_search, name='perform_search'),
]
