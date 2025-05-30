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
from django.shortcuts import render, redirect
from django.core.cache import cache
from bs4 import BeautifulSoup
import logging
import feedparser
import urllib.parse
import re
import plotly.graph_objs as go
import plotly.io as pio

def get_latest_news(symbol="MIATK", count=10):
    symbol = symbol.upper()
    query = f"{symbol} hisse"
    query_encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={query_encoded}&hl=tr&gl=TR&ceid=TR:tr"
    feed = feedparser.parse(url)
    news_data = []
    for entry in feed.entries:
        # Sadece başlık veya özetinde MIATK geçenleri al
        title = entry.title if 'title' in entry else ""
        summary = entry.summary if 'summary' in entry else ""
        if symbol in title.upper() or symbol in summary.upper():
            # Kaynak bilgisini bul
            source = ''
            if 'source' in entry and entry.source and hasattr(entry.source, 'title'):
                source = entry.source.title
            elif 'summary' in entry and entry.summary:
                match = re.search(r'-\s*([\wÇçĞğİıÖöŞşÜü\s]+)$', entry.summary)
                if match:
                    source = match.group(1).strip()
            elif 'title' in entry and entry.title:
                match = re.search(r'-\s*([\wÇçĞğİıÖöŞşÜü\s]+)$', entry.title)
                if match:
                    source = match.group(1).strip()
            news_data.append({
                'title': title,
                'link': entry.link,
                'summary': summary,
                'published': entry.published if 'published' in entry else "",
                'source': source
            })
        if len(news_data) >= count:
            break
    return news_data

def find_support_resistance(prices):
    support_levels = []
    resistance_levels = []
    for i in range(1, len(prices)-1):
        if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
            support_levels.append(prices[i])
        elif prices[i] > prices[i-1] and prices[i] > prices[i+1]:
            resistance_levels.append(prices[i])
    return support_levels, resistance_levels

def stock_plot(request):
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=30)
    symbol = "MIATK.IS"
    cache_key = f"yf_{symbol}_{start_date.date()}_{end_date.date()}"
    hist = cache.get(cache_key)
    if hist is None:
        stock = yf.Ticker(symbol)
        hist_df = stock.history(start=start_date, end=end_date)
        hist = {
            'index': [str(d.date()) for d in hist_df.index],
            'close': [float(c) for c in hist_df['Close']]
        }
        cache.set(cache_key, hist, timeout=60*60)
    dates = hist['index']
    closes = hist['close']
    support_levels, resistance_levels = find_support_resistance(closes)

    # Plotly ile interaktif grafik (gri arka plan, geniş, modern)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=closes, mode='lines+markers', name='Fiyat', line=dict(color='blue')
    ))
    for s in support_levels:
        fig.add_hline(y=s, line=dict(color='green', dash='dash'), name='Destek')
    for r in resistance_levels:
        fig.add_hline(y=r, line=dict(color='red', dash='dash'), name='Direnç')
    fig.update_layout(
        title='MIATK.IS Son 1 Aylık Kapanış Fiyatları',
        xaxis_title='Tarih',
        yaxis_title='Fiyat (TL)',
        plot_bgcolor='#f3f3f3',
        paper_bgcolor='#e0e0e0',
        font=dict(color='#222', size=16),
        xaxis=dict(gridcolor='#cccccc'),
        yaxis=dict(gridcolor='#cccccc'),
        height=600,
        width=1000,
        margin=dict(l=60, r=40, t=60, b=60)
    )
    plotly_html = pio.to_html(fig, full_html=False)

    news = get_latest_news()
    return render(request, 'stock_plot.html', {
        'plotly_html': plotly_html,
        'dates': json.dumps(dates),
        'closes': json.dumps(closes),
        'news': news
    })

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
        # Haberleri de ekle
        news = get_latest_news()
        news_text = "\n".join([f"Başlık: {item['title']}\nÖzet: {item['summary']}" for item in news])
        cache_key = f"analysis_{hash(str(closes))}_{hash(str(dates))}_{hash(news_text)}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return JsonResponse({'analysis': cached_result})
        # Gemini API çağrısı (kullanıcıdan gelen anahtar ile)
        api_key = 'AIzaSyBSJJob1ovfUYHgyV4pbKGF0uBuL5v7VxQ'
        url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=' + api_key
        prompt = (
            f"Son 1 ayın MIATK.IS kapanış fiyatları: {closes}. Tarihler: {dates}. "
            f"Son 1 haftadaki MIATK ile ilgili haber başlıkları ve özetleri:\n{news_text}\n"
            "Bu verilere göre MIATK hissesinin genel gidişatı hakkında kısa bir analiz ve gelecek haftaya dair tahmin üret."
        )
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