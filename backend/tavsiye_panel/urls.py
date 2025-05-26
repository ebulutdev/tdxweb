from django.urls import path
from . import views

app_name = 'tavsiye_panel'

urlpatterns = [
    path('', views.stock_recommendations, name='recommendations'),
    path('recommendation/', views.api_recommendation, name='api-recommendation'),
    path('tavsiye/', views.stock_recommendations, name='tavsiye'),
    path('hakkinda/', views.hakkinda, name='hakkinda'),
] 