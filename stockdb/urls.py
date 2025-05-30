from django.urls import path
from . import views

urlpatterns = [
    path('stock-plot/', views.stock_plot, name='stock_plot'),
    path('get-analysis/', views.get_analysis, name='get_analysis'),
] 