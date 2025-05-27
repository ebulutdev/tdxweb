from django.db import models

# Create your models here.

class StockRecommendation(models.Model):
    date = models.DateField(auto_now_add=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True, verbose_name="Açıklama")
    stock_symbols = models.CharField(max_length=100, help_text="Comma-separated list of 5 stock symbols")
    
    class Meta:
        ordering = ['-date']
        verbose_name = "Stock Recommendation"
        verbose_name_plural = "Stock Recommendations"
    
    def __str__(self):
        return f"{self.date} - {self.title}"
    
    def get_stock_list(self):
        return [symbol.strip() for symbol in self.stock_symbols.split(',')]
