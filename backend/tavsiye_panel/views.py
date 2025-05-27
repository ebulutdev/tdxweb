from django.shortcuts import render
from .models import StockRecommendation
from django.http import JsonResponse

# Create your views here.

def stock_recommendations(request):
    recommendations = StockRecommendation.objects.all()
    context = {
        'recommendations': [
            {
                'title': rec.title,
                'date': rec.date.strftime('%d %B %Y'),
                'description': rec.description,
                'stocks': rec.get_stock_list()
            } for rec in recommendations
        ],
        'error': None if recommendations else 'Henüz tavsiye bulunamadı.'
    }
    return render(request, 'tavsiye_panel/tavsiye.html', context)

def api_recommendation(request):
    latest = StockRecommendation.objects.first()
    if latest:
        data = {
            "title": latest.title,
            "date": latest.date.strftime("%d.%m.%Y"),
            "description": latest.description,
            "stocks": latest.get_stock_list() if latest.get_stock_list() else []
        }
    else:
        data = {"error": "Tavsiye bulunamadı."}
    return JsonResponse(data)

def hakkinda(request):
    return render(request, 'tavsiye_panel/hakkinda.html')
