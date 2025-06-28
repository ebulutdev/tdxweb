from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
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
    path('giris/', views.giris_view, name='giris'),
    path('cikis/', views.cikis_view, name='cikis'),
    path('stock-card/', views.stock_card, name='stock_card'),
    path('health/', health_check, name='health_check'),
    path('api/important-news/', views.important_news_api, name='important_news_api'),
    path('stock-image-analysis/', views.stock_image_analysis_view, name='stock_image_analysis'),
    path('stock-image-analysis/delete/<int:image_id>/', views.delete_stock_image, name='delete_stock_image'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 