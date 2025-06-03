from django.contrib import admin
from django.urls import path
from django.http import HttpResponse
from . import views

def health_check(request):
    return HttpResponse("OK", content_type="text/plain")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('tavsiye-hisse/', views.tavsiye_hisse, name='tavsiye_hisse'),
    path('stock-plot/', views.stock_plot, name='stock_plot'),
    path('get-analysis/', views.get_analysis, name='get_analysis'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('get-stock-data/', views.get_stock_data, name='get_stock_data'),
    path('demo/', views.demo_view, name='demo'),
    path('kayıt/', views.kayit_view, name='kayit'),
    path('stock-card/', views.stock_card, name='stock_card'),
    path('health/', health_check, name='health_check'),
] 