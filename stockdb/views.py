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
from django.shortcuts import render, redirect, get_object_or_404
from django.core.cache import cache
from bs4 import BeautifulSoup
import logging
import feedparser
import urllib.parse
import re
import plotly.graph_objs as go
import plotly.io as pio
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser
import pandas as pd
import time
from google.generativeai import GenerativeModel
import random
from .models import Stock, RecommendedStock, QuestionAnswer
from django.urls import reverse
from django.conf import settings
import google.generativeai as genai
import edge_tts
import asyncio
from pathlib import Path
import aiofiles
from curl_cffi import requests as curl_requests

CACHE_DIR = "cache"
CACHE_TIMEOUTS = {
    'stock_data': 5 * 60,  # 5 minutes
    'analysis': 60 * 60,   # 1 hour
    'news': 30 * 60,      # 30 minutes
    'chat_history': 30 * 60,  # 30 minutes
}

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Samimi karşılama mesajları
GREETING_MESSAGES = [
    "Merhaba! Ben TDX AI Bot. Borsa konusunda size yardımcı olmak için buradayım! 📈",
    "Selam! TDX AI Bot olarak hizmetinizdeyim. Birlikte piyasaları analiz edelim! 💹",
    "Hoş geldiniz! Ben TDX AI Bot, finansal piyasalardaki asistanınız. Size nasıl yardımcı olabilirim? 🤝",
    "Merhaba! Borsada yolunuzu bulmak için buradayım. Hangi konuda yardıma ihtiyacınız var? 🎯"
]

# Hisse analizi için prompt template
STOCK_ANALYSIS_TEMPLATE = """
Merhaba! Ben TDX AI Bot. {symbol} hissesi için detaylı bir analiz hazırladım:

Teknik Veriler:
{technical_data}

Son 1 Aylık Performans:
{performance_summary}

Önemli Göstergeler:
{key_indicators}

Benim Yorumum:
{analysis}

Size nasıl yardımcı olabilirim? Başka bir hisse için analiz yapmamı ister misiniz? 📊
"""

class RateLimiter:
    def __init__(self, key_prefix, limit, period):
        self.key_prefix = key_prefix
        self.limit = limit
        self.period = period

    def is_allowed(self, identifier):
        cache_key = f"{self.key_prefix}_{identifier}"
        current = cache.get(cache_key)
        if current is None:
            cache.set(cache_key, 1, self.period)
            return True
        if current >= self.limit:
            return False
        cache.incr(cache_key)
        return True

STOCK_LIMITER = RateLimiter('stock', 60, 60)  # 60 requests/minute

class TDXBotRateLimiter:
    def __init__(self, max_requests=60, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.cache_prefix = "tdx_bot_ratelimit"

    def is_allowed(self, user_id):
        cache_key = f"{self.cache_prefix}_{user_id}"
        current_usage = cache.get(cache_key, 0)
        
        if current_usage >= self.max_requests:
            return False
        
        cache.set(cache_key, current_usage + 1, self.time_window)
        return True

rate_limiter = TDXBotRateLimiter()

class AdvancedRateLimiter:
    def __init__(self, key_prefix, limit, period):
        self.key_prefix = key_prefix
        self.limit = limit
        self.period = period

    def is_allowed(self, identifier):
        cache_key = f"{self.key_prefix}_{identifier}"
        current = cache.get(cache_key)
        if current is None:
            cache.set(cache_key, 1, self.period)
            return True, self.period
        if current >= self.limit:
            try:
                ttl = cache.ttl(cache_key)
            except Exception:
                ttl = self.period
            return False, ttl
        cache.incr(cache_key)
        try:
            ttl = cache.ttl(cache_key)
        except Exception:
            ttl = self.period
        return True, ttl

# Eski rate_limiter yerine gelişmişi kullan
advanced_rate_limiter = AdvancedRateLimiter('analysis', 1, 10)  # 10 saniyede 1 istek

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

def scrape_bist_news(symbol=None, company_name=None, count=10, days=30):
    import feedparser
    import urllib.parse
    import re
    from dateutil import parser as dateparser
    from datetime import datetime, timedelta, timezone

    queries = []
    if symbol:
        queries.append(f"{symbol} BIST")
        queries.append(f"{symbol}")
    if company_name:
        queries.append(f"{company_name} BIST")
        queries.append(f"{company_name}")
    queries.append("BIST Borsa İstanbul")

    news_data = []
    seen_links = set()
    now = datetime.now(timezone.utc)
    min_date = now - timedelta(days=days)
    symbol_key = symbol.lower().replace('.is', '') if symbol else None
    company_key = company_name.lower() if company_name else None

    for query in queries:
        query_encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={query_encoded}&hl=tr&gl=TR&ceid=TR:tr"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if entry.link in seen_links:
                continue  # Aynı haberi tekrar ekleme
            seen_links.add(entry.link)
            title_lower = entry.title.lower()
            summary_lower = (entry.summary if 'summary' in entry else '').lower()
            # Filtre: başlık veya özet içinde sembol veya şirket adı geçmeli
            if symbol_key and symbol_key not in title_lower and (not company_key or company_key not in title_lower) and symbol_key not in summary_lower and (not company_key or company_key not in summary_lower):
                continue
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
            published = entry.published if 'published' in entry else ""
            try:
                published_dt = dateparser.parse(published)
                if published_dt is not None and published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=timezone.utc)
            except Exception:
                published_dt = None
            # Sadece son X gün içindeki haberleri al
            if published_dt is None or published_dt < min_date or published_dt > now + timedelta(days=1):
                continue
            news_data.append({
                'title': entry.title,
                'link': entry.link,
                'summary': entry.summary if 'summary' in entry else "",
                'published': published,
                'published_dt': published_dt,
                'source': source
            })
            if len(news_data) >= count:
                break
        if len(news_data) >= count:
            break

    # Eğer hiç haber yoksa, genel BIST haberlerinden doldur
    if not news_data:
        query_encoded = urllib.parse.quote("BIST Borsa İstanbul")
        url = f"https://news.google.com/rss/search?q={query_encoded}&hl=tr&gl=TR&ceid=TR:tr"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if entry.link in seen_links:
                continue
            seen_links.add(entry.link)
            published = entry.published if 'published' in entry else ""
            try:
                published_dt = dateparser.parse(published)
                if published_dt is not None and published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=timezone.utc)
            except Exception:
                published_dt = None
            if published_dt is None or published_dt < min_date or published_dt > now + timedelta(days=1):
                continue
            news_data.append({
                'title': entry.title,
                'link': entry.link,
                'summary': entry.summary if 'summary' in entry else "",
                'published': published,
                'published_dt': published_dt,
                'source': entry.source.title if 'source' in entry and entry.source and hasattr(entry.source, 'title') else ""
            })
            if len(news_data) >= count:
                break

    # En güncel 10 haberi sırala ve döndür
    news_data.sort(key=lambda x: x['published_dt'], reverse=True)
    return news_data[:count]

def save_news_to_json(symbol, news, out_dir=CACHE_DIR):
    try:
        os.makedirs(out_dir, exist_ok=True)
        news_file = os.path.join(out_dir, f"{symbol}_news.json")
        with open(news_file, 'w', encoding='utf-8') as f:
            json.dump({
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "news": news
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving news for {symbol}: {e}")

def stock_plot(request):
    symbol = request.GET.get('symbol', 'MIATK.IS').upper()
    symbol_to_company = {
        'THYAO.IS': 'Türk Hava Yolları',
        'GARAN.IS': 'Garanti Bankası',
        'AKBNK.IS': 'Akbank',
        'SISE.IS': 'Şişecam',
        'YKBNK.IS': 'Yapı Kredi',
        'KCHOL.IS': 'Koç Holding',
        'EREGL.IS': 'Ereğli Demir Çelik',
        'SASA.IS': 'Sasa Polyester',
        'TUPRS.IS': 'Tüpraş',
        'ISCTR.IS': 'İş Bankası',
        'MIATK.IS': 'Mia Teknoloji',
    }
    company_name = symbol_to_company.get(symbol, None)
    cache_key = f"yf_{symbol}_1mo"
    hist = cache.get(cache_key)
    if hist is None:
        try:
            session = curl_requests.Session(impersonate="chrome")
            stock = yf.Ticker(symbol, session=session)
            hist_df = stock.history(period='1mo')
            hist = {
                'index': [str(d.date()) for d in hist_df.index],
                'close': [float(c) for c in hist_df['Close']]
            }
            cache.set(cache_key, hist, timeout=60*60)  # 1 saat
        except Exception as e:
            hist = cache.get(cache_key, {'index': [], 'close': []})
    dates = hist['index']
    closes = hist['close']
    support_levels, resistance_levels = find_support_resistance(closes)
    # Profesyonel çizgi grafik
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=closes,
        mode='lines+markers',
        name='Fiyat',
        line=dict(color='#1976d2', width=4, shape='spline', smoothing=1.3),
        marker=dict(size=8, color='#1976d2', line=dict(width=2, color='white'), symbol='circle'),
        hovertemplate='<b>%{x}</b><br>Fiyat: %{y:.2f} TL<br><extra></extra>',
    ))
    # Son 1 haftadaki haberleri grafiğe ekle
    news = scrape_bist_news(symbol, company_name, count=10, days=7)
    news_dates = []
    news_titles = []
    news_summaries = []
    for item in news:
        try:
            news_date = pd.to_datetime(item['published']).date()
            if str(news_date) in dates:
                news_dates.append(str(news_date))
                news_titles.append(item['title'])
                news_summaries.append(item['summary'])
        except Exception:
            continue
    if news_dates:
        fig.add_trace(go.Scatter(
            x=news_dates,
            y=[closes[dates.index(d)] for d in news_dates],
            mode='markers',
            name='Haber',
            marker=dict(size=10, color='#ffd600', symbol='star'),
            hovertemplate='<b>%{customdata[0]}</b><br><span style="font-size:12px;">%{customdata[2]}</span><extra>Haber</extra>',
            customdata=[(t, s, (s[:50] + '...') if len(s) > 50 else s) for t, s in zip(news_titles, news_summaries)]
        ))
    for s in support_levels:
        fig.add_hline(y=s, line=dict(color='rgba(0,200,83,0.7)', width=2, dash='dot'), name='Destek')
    for r in resistance_levels:
        fig.add_hline(y=r, line=dict(color='rgba(229,57,53,0.7)', width=2, dash='dot'), name='Direnç')
    fig.update_layout(
        title=f'{symbol} Son 1 Aylık Kapanış Fiyatları',
        xaxis_title='Tarih',
        yaxis_title='Fiyat (TL)',
        plot_bgcolor='#23272e',
        paper_bgcolor='#181a20',
        font=dict(color='#e0e0e0', size=17),
        xaxis=dict(gridcolor='#444857', showgrid=True),
        yaxis=dict(gridcolor='#444857', showgrid=True),
        height=600,
        width=1000,
        margin=dict(l=60, r=40, t=60, b=60),
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor='rgba(0,0,0,0.2)'
        )
    )
    plotly_html = pio.to_html(fig, full_html=False)
    news = scrape_bist_news(symbol, company_name)
    return render(request, 'stock_plot.html', {
        'plotly_html': plotly_html,
        'dates': json.dumps(dates),
        'closes': json.dumps(closes),
        'news': news,
        'symbol': symbol,
        'error': ''
    })

@csrf_exempt
def get_analysis(request):
    if request.method == 'POST':
        symbol = request.GET.get('symbol', 'MIATK.IS').upper()
        ip = request.META.get('REMOTE_ADDR')
        # Gelişmiş rate limiting check
        allowed, wait_time = advanced_rate_limiter.is_allowed(ip)
        if not allowed:
            return JsonResponse({
                'status': 'error',
                'message': f'Lütfen {wait_time} saniye bekleyin.',
                'code': 'RATE_LIMIT_EXCEEDED',
                'retry_after': wait_time
            }, status=429)
        try:
            data = json.loads(request.body)
            closes = data.get('closes', [])
            dates = data.get('dates', [])
            if not closes or not dates:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Geçersiz veri formatı',
                    'code': 'INVALID_DATA'
                }, status=400)
            # Get latest news and prepare analysis context
            news = get_latest_news(symbol, count=5)  # Son 5 haber
            news_text = "\n".join([
                f"• {item['title']}\n  Kaynak: {item['source']}\n  Özet: {item['summary']}"
                for item in news
            ])
            # Calculate key metrics
            last_price = closes[-1]
            price_change = closes[-1] - closes[0]
            price_change_pct = (price_change / closes[0]) * 100
            avg_price = sum(closes) / len(closes)
            # Create cache key based on data hash
            cache_key = f"analysis_{symbol}_{hash(str(closes))}_{hash(str(dates))}_{hash(news_text)}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return JsonResponse({
                    'status': 'success',
                    'data': cached_result,
                    'cached': True
                })
            # Prepare enhanced prompt for better analysis (HTML output with explicit news analysis)
            price_table = "\n".join([f"{d}: {c:.2f} TL" for d, c in zip(dates, closes)])
            news_table = ""
            for item in news:
                try:
                    news_date = pd.to_datetime(item['published']).date()
                    if str(news_date) in dates:
                        price = closes[dates.index(str(news_date))]
                        news_table += f"- {news_date}: {price:.2f} TL | {item['title']} | {item['summary']}\n"
                except Exception:
                    continue
            prompt = f"""
Sen TDX AI Bot'sun. {symbol} hissesi için aşağıdaki YFINANCE verilerine dayanarak, matematiksel analiz ve senaryo üretimiyle, kullanıcının bu hissede neler yapabileceğini, farklı stratejiler ve olası senaryolar üzerinden açıkla:

- Son fiyat: {last_price:.2f} TL
- Aylık değişim: {price_change_pct:.2f}%
- En yüksek: {closes[-1]:.2f} TL
- En düşük: {closes[0]:.2f} TL
- Ortalama hacim: {avg_price:.2f} TL
- Hedef fiyat: {closes[-1]:.2f} TL
- Piyasa değeri: {closes[-1]:.2f} TL
- F/K oranı: {closes[-1]/closes[0]:.2f}

Aşağıdaki başlıklar altında, **her şeyi kısa, net ve madde madde** (bullet point) yaz:
1. Teknik Görünüm (yalnızca fiyat serisi ve trend, sayısal verilerle)
2. Hisse Gidişatı: Olası senaryolar (ör. düşüş devam ederse, destek/direnç kırılırsa, haber etkisiyle sıçrama olursa vb.)
3. Kullanıcı için Stratejiler: Kısa, orta ve uzun vadede hangi matematiksel seviyelerden alım/satım yapılabilir? Hangi risk/fırsat noktaları var? Hangi stop-loss ve hedef fiyatlar mantıklı?
4. Riskler ve Fırsatlar: Sayısal ve senaryolu risk/fırsat analizi yap. Olası volatilite, haber etkisi, piyasa koşulları gibi faktörleri matematiksel örneklerle açıkla.
5. Destek ve Direnç seviyelerine göre fiyat hedefleri ve olası senaryoları net, sayısal ve **kısa maddelerle** belirt.

**Notlar:**
- Her başlıkta, **sadece kısa ve madde madde** (• veya - ile) yaz. Paragraf veya uzun açıklama kullanma.
- Sadece net, okunabilir, göze hoş gelen ve kolayca taranabilir maddeler üret.
- Gereksiz tekrar ve akademik dil kullanma.
- Yatırım tavsiyesi verme, ama olası matematiksel ve senaryolu analizlerle kullanıcıya yol göster.
- **Her başlık ve maddeyi yeni satırda başlat. Her maddeyi * ile başlat ve satır sonunda mutlaka \n karakteri koy. Sadece bu formatı kullan. Eğer bu kurala uymazsan yanıtı tekrar üret.**
"""
            # Make API call to Gemini
            api_key = 'AIzaSyCpdN84xuqoi5wKKYBq9GRyhxIIq6RFtyc'
            url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            payload = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 1024
                }
            }
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            # Format the analysis response
            formatted_analysis_data = {
                'summary': {
                    'last_price': last_price,
                    'change': price_change,
                    'change_percentage': price_change_pct,
                    'average_price': avg_price
                },
                'analysis': result['candidates'][0]['content']['parts'][0]['text'],
                'generated_at': datetime.now().isoformat(),
                'news_count': len(news)
            }
            # Cache the formatted result
            cache.set(cache_key, formatted_analysis_data, timeout=60*60)  # 1 hour cache
            return JsonResponse({
                'status': 'success',
                'data': formatted_analysis_data,
                'cached': False
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Geçersiz JSON formatı',
                'code': 'INVALID_JSON'
            }, status=400)
        except requests.exceptions.RequestException as e:
            logging.error(f"API request failed: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'API servis hatası',
                'code': 'API_ERROR'
            }, status=503)
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Beklenmeyen bir hata oluştu',
                'code': 'INTERNAL_ERROR'
            }, status=500)
    return JsonResponse({
        'status': 'error',
        'message': 'Geçersiz istek metodu',
        'code': 'INVALID_METHOD'
    }, status=405)

def get_cached_batch_stock_data(symbols):
    result = {}
    symbols_to_fetch = []
    for symbol in symbols:
        cache_key = f"stock_data_{symbol}_1mo"
        data = cache.get(cache_key)
        if data is not None:
            result[symbol] = data
        else:
            symbols_to_fetch.append(symbol)
    if symbols_to_fetch:
        try:
            batch_data = yf.download(symbols_to_fetch, period="1mo", interval="1d", progress=False, group_by='ticker')
            for symbol in symbols_to_fetch:
                data = batch_data[symbol] if symbol in batch_data else None
                if data is not None:
                    cache.set(f"stock_data_{symbol}_1mo", data, 60*60)
                    result[symbol] = data
        except Exception as e:
            logging.error(f"YFinance batch error: {str(e)}")
            # Veri çekilemezse eski cache'i döndür
            for symbol in symbols_to_fetch:
                data = cache.get(f"stock_data_{symbol}_1mo")
                if data is not None:
                    result[symbol] = data
    return result

def home(request):
    stocks = [
        {'symbol': 'THYAO.IS', 'company': 'Türk Hava Yolları'},
        {'symbol': 'GARAN.IS', 'company': 'Garanti Bankası'},
        {'symbol': 'AKBNK.IS', 'company': 'Akbank'},
        {'symbol': 'SISE.IS', 'company': 'Şişecam'},
        {'symbol': 'YKBNK.IS', 'company': 'Yapı Kredi'},
        {'symbol': 'KCHOL.IS', 'company': 'Koç Holding'},
        {'symbol': 'EREGL.IS', 'company': 'Ereğli Demir Çelik'},
        {'symbol': 'SASA.IS', 'company': 'Sasa Polyester'},
        {'symbol': 'TUPRS.IS', 'company': 'Tüpraş'},
        {'symbol': 'ISCTR.IS', 'company': 'İş Bankası'},
        {'symbol': 'MIATK.IS', 'company': 'Mia Teknoloji'},
        {'symbol': 'FROTO.IS', 'company': 'Ford Otosan'},
    ]
    symbols = [stock['symbol'] for stock in stocks]
    user_ip = request.META.get('REMOTE_ADDR', 'unknown')
    if not STOCK_LIMITER.is_allowed(user_ip):
        return render(request, 'home.html', {'stocks': [], 'error': 'Çok fazla istek! Lütfen bekleyin.'})
    batch_data = get_cached_batch_stock_data(symbols)
    stock_data = []
    for stock in stocks:
        symbol = stock['symbol']
        data = batch_data.get(symbol)
        price = 0
        change = 0
        volume_str = "-"
        time_str = "-"
        try:
            if data is not None and not data.empty:
                latest_data = data.iloc[-1]
                price = float(latest_data['Close'])
                if len(data) > 1:
                    prev_close = float(data.iloc[-2]['Close'])
                    if prev_close != 0:
                        change = round((price - prev_close) / prev_close * 100, 2)
                volume = latest_data['Volume']
                if volume >= 1_000_000:
                    volume_str = f"{volume/1_000_000:.1f}M"
                elif volume >= 1_000:
                    volume_str = f"{volume/1_000:.1f}K"
                else:
                    volume_str = str(volume)
                time_str = latest_data.name.strftime("%d.%m")
        except Exception as e:
            logging.error(f"Stock parse error for {symbol}: {str(e)}")
        stock_data.append({
            'symbol': symbol,
            'company': stock['company'],
            'price': price,
            'change': change,
            'volume': volume_str,
            'time': time_str,
        })
    return render(request, 'home.html', {'stocks': stock_data})

def tavsiye_hisse(request):
    recommended_stocks = RecommendedStock.objects.filter(is_active=True)
    return render(request, 'tavsiye_hisse.html', {'recommended_stocks': recommended_stocks})

@csrf_exempt
def chatbot(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            user_id = request.META.get('REMOTE_ADDR', 'unknown')

            # Cache check
            cache_key = f"chat_response_{user_message}_{user_id}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return JsonResponse({'response': cached_response})

            # Process the message
            response = process_user_message(user_message, user_id)
            
            # Cache the response
            cache.set(cache_key, response, CACHE_TIMEOUTS['chat_history'])
            
            return JsonResponse({'response': response})

        except Exception as e:
            logger.error(f"Chatbot error: {str(e)}")
            return JsonResponse({
                'response': "Üzgünüm, bir hata oluştu. Lütfen tekrar dener misiniz? 🙏"
            })

    return JsonResponse({'error': 'Geçersiz istek metodu'}, status=400)

def process_user_message(message, user_id=None):
    """Process user message and generate appropriate response"""
    try:
        stock_data = get_stock_info(message)
        if stock_data:
            return generate_stock_analysis(message, stock_data)
        # Only apply rate limit for Gemini API/general conversation
        if user_id and not rate_limiter.is_allowed(user_id):
            return "Üzgünüm, çok fazla istek aldım. Lütfen biraz bekleyip tekrar deneyin! 😅"
        return generate_conversation_response(message)
    except Exception as e:
        logger.error(f"Message processing error: {str(e)}")
        return random.choice(GREETING_MESSAGES)

def get_stock_info(symbol):
    """Get comprehensive stock information"""
    try:
        session = curl_requests.Session(impersonate="chrome")
        stock = yf.Ticker(symbol, session=session)
        info = {
            'history': stock.history(period='1mo'),
            'info': stock.info,
            'recommendations': stock.recommendations,
            'major_holders': stock.major_holders,
            'institutional_holders': stock.institutional_holders,
            'news': stock.news
        }
        return info if not info['history'].empty else None
    except Exception as e:
        logger.error(f"Stock info error: {str(e)}")
        return None

def generate_stock_analysis(symbol, stock_data):
    """Generate detailed stock analysis"""
    try:
        history = stock_data['history']
        info = stock_data['info']
        
        # Calculate key metrics
        current_price = history['Close'][-1]
        price_change = current_price - history['Close'][0]
        price_change_pct = (price_change / history['Close'][0]) * 100
        
        technical_data = f"""
        🎯 Güncel Fiyat: {current_price:.2f} TL
        📊 Aylık Değişim: {price_change_pct:.2f}%
        📈 En Yüksek: {history['High'].max():.2f} TL
        📉 En Düşük: {history['Low'].min():.2f} TL
        """
        
        # Generate analysis prompt
        prompt = STOCK_ANALYSIS_TEMPLATE.format(
            symbol=symbol,
            technical_data=technical_data,
            performance_summary=generate_performance_summary(history),
            key_indicators=generate_key_indicators(info),
            analysis=generate_ai_analysis(symbol, stock_data)
        )
        
        return prompt
    
    except Exception as e:
        logger.error(f"Analysis generation error: {str(e)}")
        return "Üzgünüm, analiz oluştururken bir hata oluştu. Lütfen tekrar deneyin! 🔄"

def generate_ai_analysis(symbol, stock_data):
    """Generate AI-powered analysis using Gemini"""
    try:
        api_key = 'AIzaSyCpdN84xuqoi5wKKYBq9GRyhxIIq6RFtyc'
        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'
        history = stock_data['history']
        info = stock_data['info']
        current_price = history['Close'][-1]
        price_change = current_price - history['Close'][0]
        price_change_pct = (price_change / history['Close'][0]) * 100
        avg_volume = history['Volume'].mean()
        high = history['High'].max()
        low = history['Low'].min()
        target_price = info.get('targetMeanPrice', 'N/A')
        market_cap = info.get('marketCap', 'N/A')
        pe_ratio = info.get('trailingPE', 'N/A')
        prompt = f"""
Sen TDX AI Bot'sun. {symbol} hissesi için aşağıdaki YFINANCE verilerine dayanarak güncel, kısa ve maddeler halinde bilgi ver:

- Son fiyat: {current_price:.2f} TL
- Aylık değişim: {price_change_pct:.2f}%
- En yüksek: {high:.2f} TL
- En düşük: {low:.2f} TL
- Ortalama hacim: {avg_volume:,.0f}
- Hedef fiyat: {target_price}
- Piyasa değeri: {market_cap}
- F/K oranı: {pe_ratio}

Kullanıcıya kısa, samimi ve maddeler halinde bilgi ver. Yatırım tavsiyesi verme, sadece veri ve özet sun.
"""
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1024
                }
            }
        )
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        logger.error(f"AI analysis error: {str(e)}")
        return "Analiz oluşturulurken bir hata oluştu, ama elimdeki verilere göre dikkatli olmanızı öneririm! 🤔"

def generate_performance_summary(history):
    """Generate performance summary"""
    try:
        monthly_return = ((history['Close'][-1] / history['Close'][0]) - 1) * 100
        avg_volume = history['Volume'].mean()
        
        return f"""
        📊 Aylık Getiri: {monthly_return:.2f}%
        📈 Ortalama İşlem Hacmi: {avg_volume:,.0f}
        """
    except Exception as e:
        logger.error(f"Performance summary error: {str(e)}")
        return "Performans özeti hesaplanamadı"

def generate_key_indicators(info):
    """Generate key financial indicators"""
    try:
        return f"""
        🎯 Hedef Fiyat: {info.get('targetMeanPrice', 'N/A')} TL
        📊 Piyasa Değeri: {info.get('marketCap', 'N/A'):,} TL
        📈 F/K Oranı: {info.get('trailingPE', 'N/A')}
        """
    except Exception as e:
        logger.error(f"Key indicators error: {str(e)}")
        return "Göstergeler hesaplanamadı"

def generate_conversation_response(message):
    """Generate conversational response using Gemini"""
    try:
        api_key = 'AIzaSyBSJJob1ovfUYHgyV4pbKGF0uBuL5v7VxQ'
        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'
        
        prompt = f"""
        Sen TDX AI Bot'sun. Borsa ve finans konularında uzman, samimi ve yardımsever bir asistansın.
        Kullanıcı mesajı: {message}
        
        Lütfen:
        1. Samimi ve arkadaşça bir tonda yanıt ver
        2. Emoji kullan
        3. Borsa ve finans konularında yardımcı ol
        4. Gerektiğinde ek sorular sor
        """
        
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1024
                }
            }
        )
        
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    
    except Exception as e:
        logger.error(f"Conversation response error: {str(e)}")
        return random.choice(GREETING_MESSAGES)

@csrf_exempt
def get_stock_data(request):
    """Enhanced stock data endpoint"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            symbol = data.get('symbol', '')
            
            # Check cache
            cache_key = f"stock_data_{symbol}_1mo"
            cached_data = cache.get(cache_key)
            if cached_data:
                return JsonResponse(cached_data)
            
            # Get fresh data
            stock_info = get_stock_info(symbol)
            if not stock_info:
                return JsonResponse({
                    'error': 'Üzgünüm, bu hisse için veri bulamadım. Doğru yazdığınızdan emin misiniz? 🤔'
                }, status=404)
            
            # Prepare response
            response_data = {
                'data': stock_info['history'].to_dict(orient='records'),
                'info': stock_info['info'],
                'analysis': generate_stock_analysis(symbol, stock_info),
                'recommendations': stock_info['recommendations'].to_dict(orient='records') if stock_info['recommendations'] is not None else [],
                'major_holders': stock_info['major_holders'].to_dict(orient='records') if stock_info['major_holders'] is not None else [],
                'news': stock_info['news']
            }
            
            # Cache the response
            cache.set(cache_key, response_data, CACHE_TIMEOUTS['stock_data'])
            
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Stock data error: {str(e)}")
            return JsonResponse({
                'error': 'Veri çekilirken bir hata oluştu. Lütfen tekrar deneyin! 🔄'
            }, status=500)
            
    return JsonResponse({'error': 'Geçersiz istek metodu'}, status=400)

def demo_view(request):
    return render(request, 'demo.html')

def kayit_view(request):
    return render(request, 'kayıt.html')

# Configure Gemini API
genai.configure(api_key='AIzaSyAJYQvoAW4Rgy7p4qxR8-0L9BT-WYISJY4')
model = genai.GenerativeModel('gemini-1.5-flash')

async def text_to_speech(text, output_file):
    communicate = edge_tts.Communicate(text, "tr-TR-AhmetNeural")
    visemes = []
    async with aiofiles.open(output_file, "wb") as file:
        async for chunk in communicate.stream():
            print(f"Chunk type: {chunk['type']}")  # Debug için
            if chunk["type"] == "audio":
                await file.write(chunk["data"])
            elif chunk["type"] == "viseme":
                print(f"Viseme data: {chunk}")  # Debug için
                visemes.append({
                    "offset": chunk["offset"],
                    "duration": chunk["duration"],
                    "id": chunk["id"]
                })
    print(f"Total visemes collected: {len(visemes)}")  # Debug için
    return visemes

@csrf_exempt
def chat(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            # Add instruction for Turkish response
            prompt = (
                "Sen bir TDX AI Danışman Botusun. Türkiye'nin en gelişmiş Borsa İstanbul analiz platformu olan TDX bot'u temsil ediyorsun. "
                "Platform Tanıtımı: TDX bot, yapay zeka destekli Borsa İstanbul analiz platformudur. Gerçek zamanlı BIST verileri ile yatırım kararlarını destekler. Teknik analiz, haber yorumlama, önerilen hisseler, destek-direnç analizleri sunar. "
                "Kullanıcılara platform hakkında bilgi verir, özellikleri açıklar, ücretsiz ve ücretli abonelik farklarını anlatır, teknik analiz verilerini yorumlayabilir ve platform üzerinden yapılabilecek işlemler hakkında detaylı bilgilendirme sunarsın. "
                "Yatırım tavsiyesi vermezsin, yasal sınırlar dahilinde bilgi sağlarsın. "
                "TDX reklamı yapmaktan çekinme. "
                "Borsa ve hisse sorularında TDX AI Teknik Değerlendirme Sistemini açıkla: "
                "Teknik Görünüm: Trendin yönü ve fiyat ortalamaları. "
                "Hisse Gidişatı: Kısa ve uzun vadeli beklentiler. "
                "Karar Yönlendirmesi: Yatırım yapılabilirlik önerisi (ancak yatırım tavsiyesi değildir). "
                "Risk ve Fırsatlar: Mevcut destek/direnç seviyeleri ve senaryo analizi. "
                "Platform Özellikleri: Yapay zeka destekli hisse önerileri, teknik analizler (grafik çizimi, destek-direnç seviyeleri, indikatör analizi), gerçek zamanlı fiyat ve grafik görüntüleme, KAP haberlerini otomatik çekme ve analiz etme, risk seviyesi ve hedef fiyat gösterimi, anlık fiyat uyarıları, haftalık algoritmik analiz sonuçları, demo modda analiz denemeleri. "
                "Kullanıcıdan gelen soruya, yukarıdaki çerçevede, kısa ve net, tek cümlelik bir özetle ve noktalama işareti kullanmadan cevap ver. "
                f"Soru: {user_message}"
            )
            
            # Get response from Gemini
            response = model.generate_content(prompt)
            response_text = response.text
            
            # Create media directory if it doesn't exist
            media_dir = Path(settings.MEDIA_ROOT)
            media_dir.mkdir(exist_ok=True)
            
            # Save audio file
            audio_path = media_dir / 'response.mp3'
            
            # Convert text to speech using Edge TTS and get viseme data
            visemes = asyncio.run(text_to_speech(response_text, str(audio_path)))
            
            return JsonResponse({
                'text': response_text,
                'audio_url': f'/media/response.mp3',
                'visemes': visemes
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

def format_gemini_response(raw_response):
    # Başlıkları bul ve satır başına al
    text = re.sub(r'(\d+\. [^*]+)', r'\n\1\n', raw_response)
    # Hem ** hem de * ile başlayanları satır başına al
    text = re.sub(r'\*\*', r'\n* ', text)
    text = re.sub(r'\* ', r'\n* ', text)
    # Gereksiz boşlukları temizle
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    # Her maddeyi * ile başlat, başlıkları olduğu gibi bırak
    formatted = []
    for line in lines:
        if re.match(r'\d+\.', line):
            formatted.append(f'\n{line}\n')
        elif line.startswith('*'):
            formatted.append(f'{line}\n')
        else:
            formatted.append(f'* {line}\n')
    return ''.join(formatted) 