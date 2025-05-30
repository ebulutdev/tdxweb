import matplotlib
matplotlib.use('Agg')
import yfinance as yf
import matplotlib.pyplot as plt
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from io import BytesIO
import datetime
import base64
import requests
import json
from django.shortcuts import render
from django.core.cache import cache

def stock_plot(request):
    # Son bir ayın tarih aralığını hesapla
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=30)
    
    # MIATK.IS hissesinin verilerini çek
    stock = yf.Ticker("MIATK.IS")
    hist = stock.history(start=start_date, end=end_date)
    
    # Matplotlib grafiğini oluştur
    plt.figure(figsize=(12, 6))
    plt.plot(hist.index, hist['Close'], label='Kapanış Fiyatı')
    plt.title('MIATK.IS Son 1 Aylık Kapanış Fiyatları')
    plt.xlabel('Tarih')
    plt.ylabel('Fiyat (TL)')
    plt.grid(True)
    plt.legend()
    
    # Grafiği HttpResponse olarak döndür
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()
    
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    dates = [str(d.date()) for d in hist.index]
    closes = [float(c) for c in hist['Close']]
    return render(request, 'stock_plot.html', {'img_base64': img_base64, 'dates': json.dumps(dates), 'closes': json.dumps(closes)})

@csrf_exempt
def get_analysis(request):
    if request.method == 'POST':
        ip = request.META.get('REMOTE_ADDR')
        if cache.get(f"ratelimit_{ip}"):
            return JsonResponse({'error': 'Çok sık istek attınız, lütfen bekleyin.'}, status=429)
        cache.set(f"ratelimit_{ip}", True, timeout=10)  # 10 saniye bekletme
        data = json.loads(request.body)
        closes = data.get('closes', [])
        dates = data.get('dates', [])
        cache_key = f"analysis_{hash(str(closes))}_{hash(str(dates))}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return JsonResponse({'analysis': cached_result})
        # Gemini API çağrısı (kullanıcıdan gelen anahtar ile)
        api_key = 'AIzaSyBSJJob1ovfUYHgyV4pbKGF0uBuL5v7VxQ'
        url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=' + api_key
        prompt = f"Son 1 ayın MIATK.IS kapanış fiyatları: {closes}. Tarihler: {dates}. Bu veriye göre kısa bir borsa yorumu yapar mısın?"
        headers = {'Content-Type': 'application/json'}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            result = response.json()
            analysis = result['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            analysis = f"API hatası: {e}"
        cache.set(cache_key, analysis, timeout=60*60)  # 1 saat cache
        return JsonResponse({'analysis': analysis})
    return JsonResponse({'error': 'Invalid request'}, status=400) 