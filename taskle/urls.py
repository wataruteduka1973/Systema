from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),

    path('SendMail', views.SendMailMode, name='SendMailMode'),

    path('add_template', views.add_template, name='add_template'),

    path('change_template', views.change_template, name='change_template'),

    path('delete_template', views.delete_template, name='delete_template'),

    path('update_fields/<str:selected_Option>/',
         views.update_fields, name='update_fields'),

    path('delete_fields/<str:selected_Option>/',
         views.delete_fields, name='delete_fields'),

    path('Yahuoku', views.Yahuoku, name='Yahuoku'),

    path('search/', views.perform_search, name='search')
]
