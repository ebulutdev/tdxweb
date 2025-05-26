from django.contrib import admin
from .models import StockRecommendation

@admin.register(StockRecommendation)
class StockRecommendationAdmin(admin.ModelAdmin):
    list_display = ('date', 'title', 'description', 'stock_symbols')
    list_filter = ('date',)
    search_fields = ('title', 'description', 'stock_symbols')
