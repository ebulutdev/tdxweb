# admin.py
from django.contrib import admin
from .models import Stock, RecommendedStock, QuestionAnswer

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'company', 'price', 'change', 'volume', 'time')
    search_fields = ('symbol', 'company')
    list_filter = ('time',)

@admin.register(RecommendedStock)
class RecommendedStockAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'company', 'price', 'target_price', 'risk_level', 'is_active', 'created_at')
    list_filter = ('risk_level', 'is_active', 'created_at')
    search_fields = ('symbol', 'company', 'recommendation_text')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Hisse Bilgileri', {
            'fields': ('symbol', 'company', 'price', 'change')
        }),
        ('Tavsiye Detayları', {
            'fields': ('target_price', 'risk_level', 'recommendation_text')
        }),
        ('Durum', {
            'fields': ('is_active', 'created_at')
        }),
    )

@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    list_display = ('stock', 'question', 'answer', 'created_at', 'answered_at')
    search_fields = ('question', 'answer')
    list_filter = ('created_at', 'answered_at', 'stock')
    readonly_fields = ('created_at',)
