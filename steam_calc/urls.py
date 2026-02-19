# steam_calc/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.steam_calculator, name='steam_calculator'),
]