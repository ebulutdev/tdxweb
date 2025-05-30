from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('tavsiye-hisse/', views.tavsiye_hisse, name='tavsiye_hisse'),
    path('stock-plot/', views.stock_plot, name='stock_plot'),
    path('get-analysis/', views.get_analysis, name='get_analysis'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('get-stock-data/', views.get_stock_data, name='get_stock_data'),
] 