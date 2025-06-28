# models.py
from django.db import models

class Stock(models.Model):
    symbol = models.CharField(max_length=10)
    company = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    change = models.DecimalField(max_digits=5, decimal_places=2)
    volume = models.DecimalField(max_digits=15, decimal_places=2)
    time = models.TimeField()

    def __str__(self):
        return self.symbol

class RecommendedStock(models.Model):
    RISK_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ]
    symbol = models.CharField(max_length=10)
    company = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    target_price = models.DecimalField(max_digits=10, decimal_places=2)
    risk_level = models.CharField(max_length=6, choices=RISK_LEVELS)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    recommendation_text = models.TextField()
    image = models.ImageField(upload_to='stock_images/', blank=True, null=True, verbose_name='Hisse Fotoğrafı')

    def __str__(self):
        return self.symbol

class QuestionAnswer(models.Model):
    stock = models.ForeignKey(RecommendedStock, on_delete=models.CASCADE, related_name='questions')
    question = models.TextField(verbose_name='Soru')
    answer = models.TextField(verbose_name='Cevap', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.stock.symbol} - {self.question[:30]}..."

class StockImage(models.Model):
    title = models.CharField(max_length=200, verbose_name='Başlık')
    image = models.ImageField(upload_to='stock_analysis_images/', verbose_name='PNG Fotoğraf')
    description = models.TextField(blank=True, null=True, verbose_name='Açıklama')
    gemini_analysis = models.TextField(blank=True, null=True, verbose_name='Gemini Analizi')
    created_at = models.DateTimeField(auto_now_add=True)
    is_analyzed = models.BooleanField(default=False, verbose_name='Analiz Edildi mi?')

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Hisse Analiz Görseli'
        verbose_name_plural = 'Hisse Analiz Görselleri'
        permissions = [
            ("can_upload_stock_image", "Stok görseli yükleyebilir")
        ]