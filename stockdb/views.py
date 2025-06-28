import logging
import json
from datetime import datetime, timedelta, timezone
import base64
import requests
import urllib.parse
import re
import time
import hashlib
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.shortcuts import render, redirect, get_object_or_404
from django.core.cache import cache
from django.urls import reverse
from bs4 import BeautifulSoup
import feedparser
from dateutil import parser as dateparser
from .models import Stock, RecommendedStock, QuestionAnswer, StockImage
from .utils import get_stock_data
from yfinance.data import YFRateLimitError
from curl_cffi import requests as curl_requests
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
import random
import yfinance as yf
import google.generativeai as genai

# PIL import'unu koşullu hale getir
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("PIL (Pillow) modülü bulunamadı. Görsel analizi özelliği devre dışı.")

from django.contrib.auth.decorators import login_required, permission_required

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache settings
CACHE_DIR = "cache"
CACHE_TIMEOUTS = {
    'stock_data': 5 * 60,  # 5 minutes
    'analysis': 60 * 60,   # 1 hour
    'news': 30 * 60,      # 30 minutes
    'chat_history': 30 * 60,  # 30 minutes
}

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
    import plotly.graph_objs as go
    import plotly.io as pio
    import pandas as pd
    import yfinance as yf
    
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
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    cache_key = f"yf_{symbol}_{start_date.date()}_{end_date.date()}"
    hist = cache.get(cache_key)
    if hist is None:
        try:
            stock = yf.Ticker(symbol)
            hist_df = stock.history(start=start_date, end=end_date)
            hist = {
                'index': [str(d.date()) for d in hist_df.index],
                'close': [float(c) for c in hist_df['Close']]
            }
            cache.set(cache_key, hist, timeout=60*60)
        except YFRateLimitError:
            return render(request, 'stock_plot.html', {
                'plotly_html': '',
                'dates': '[]',
                'closes': '[]',
                'news': [],
                'symbol': symbol,
                'error': 'Çok fazla istek gönderdiniz. Lütfen birkaç dakika sonra tekrar deneyin.'
            })
        except Exception as e:
            return render(request, 'stock_plot.html', {
                'plotly_html': '',
                'dates': '[]',
                'closes': '[]',
                'news': [],
                'symbol': symbol,
                'error': f'Hata: {str(e)}'
            })
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

def get_important_news(days=2):
    """Piyasayı etkileyecek önemli haberleri kategorilere göre çeker (cache'li)"""
    cache_key = f"important_news_{days}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    categories = {
        'Merkez Bankası': [
            'tcmb faiz kararı', 'politika faizi', 'faiz artışı', 'faiz indirimi',
            'tcmb başkanı', 'tcmb toplantısı', 'faiz kararı', 'faiz beklentisi',
            'swap', 'rezerv', 'döviz müdahalesi', 'piyasa likiditesi'
        ],
        'Ekonomik Veriler': [
            'enflasyon verisi', 'işsizlik verisi', 'büyüme verisi', 'gsyh',
            'cari açık', 'dış ticaret açığı', 'bütçe açığı', 'merkez bankası rezerv',
            'döviz rezervi', 'altın rezervi', 'sanayi üretimi', 'perakende satış',
            'konut satışları', 'tüketici güven endeksi', 'reel sektör güven endeksi'
        ],
        'Kurumsal Haberler': [
            'hisse senedi', 'temettü', 'bedelsiz', 'bedelli', 'halka arz',
            'yatırım kararı', 'yatırım planı', 'fabrika yatırımı', 'ihracat anlaşması',
            'stratejik ortaklık', 'birleşme', 'satın alma', 'borçlanma', 'kredi',
            'finansman', 'sermaye artırımı', 'özel durum açıklaması'
        ],
        'Sektörel Gelişmeler': [
            'enerji fiyatları', 'petrol fiyatı', 'doğalgaz fiyatı', 'elektrik fiyatı',
            'çelik fiyatı', 'demir fiyatı', 'bakır fiyatı', 'altın fiyatı',
            'tarım ürünleri', 'gıda fiyatları', 'emlak fiyatları', 'kiralar',
            'inşaat maliyetleri', 'hammadde fiyatları', 'lojistik maliyetleri'
        ],
        'Piyasa Analizleri': [
            'piyasa analizi', 'teknik analiz', 'yatırım tavsiyesi', 'portföy yönetimi',
            'risk analizi', 'piyasa beklentisi', 'piyasa görünümü', 'sektör raporu',
            'ekonomi raporu', 'piyasa değerlendirmesi', 'yatırımcı görüşü',
            'analist görüşü', 'piyasa yorumu'
        ]
    }
    queries = [
        "BIST borsa istanbul önemli gelişme",
        "TCMB faiz kararı politika faizi",
        "ekonomik veri açıklaması enflasyon büyüme",
        "hisse senedi temettü bedelsiz halka arz",
        "piyasa analizi yatırım tavsiyesi",
        "enerji fiyatları petrol doğalgaz elektrik",
        "çelik demir bakır altın fiyatları",
        "döviz kuru analizi piyasa yorumu",
        "özel durum açıklaması sermaye artırımı",
        "yatırım kararı fabrika yatırımı"
    ]
    news_data = []
    seen_links = set()
    now = datetime.now(timezone.utc)
    min_date = now - timedelta(days=days)
    for query in queries:
        query_encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={query_encoded}&hl=tr&gl=TR&ceid=TR:tr"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if entry.link in seen_links:
                continue
            seen_links.add(entry.link)
            title_lower = entry.title.lower()
            summary_lower = (entry.summary if 'summary' in entry else '').lower()
            category = 'Diğer'
            for cat, keywords in categories.items():
                if any(keyword in title_lower or keyword in summary_lower for keyword in keywords):
                    category = cat
                    break
            if category == 'Diğer':
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
            if published_dt is None or published_dt < min_date or published_dt > now + timedelta(days=1):
                continue
            news_item = {
                'title': entry.title,
                'summary': entry.summary if 'summary' in entry else '',
                'link': entry.link,
                'source': source,
                'published_dt': published_dt,
                'category': category
            }
            news_data.append(news_item)
    news_data.sort(key=lambda x: x['published_dt'], reverse=True)
    cache.set(cache_key, news_data, 60*10)  # 10 dakika cache
    return news_data

def home(request):
    # Önemli haberleri çek
    important_news = get_important_news(days=2)
    
    # Popüler hisseleri çek
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
    
    return render(request, 'home.html', {
        'stocks': stocks,
        'important_news': important_news
    })

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
        # Otomatik BIST hisse kodu algılama (başında $ olsa da)
        match = re.search(r'\b\$?([A-Z]{3,5}\.IS)\b', message.upper())
        symbol = match.group(1) if match else None
        if symbol:
            symbol = symbol.upper().strip().replace('$', '')  # Tamamen temizle
            stock_data = get_stock_info(symbol)
            if stock_data:
                return generate_stock_analysis(symbol, stock_data)
        # Only apply rate limit for Gemini API/general conversation
        if user_id and not rate_limiter.is_allowed(user_id):
            return "Üzgünüm, çok fazla istek aldım. Lütfen birkaç dakika sonra tekrar deneyin! 😅"
        return generate_conversation_response(message)
    except Exception as e:
        logger.error(f"Message processing error: {str(e)}")
        return random.choice(GREETING_MESSAGES)

def get_stock_info(symbol):
    symbol = symbol.upper().strip().replace('$', '')  # Tamamen temizle
    cache_key = f"stock_info_{symbol}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    try:
        stock = yf.Ticker(symbol)
        info = {
            'history': stock.history(period='1mo'),
            'info': stock.info,
            'recommendations': stock.recommendations,
            'major_holders': stock.major_holders,
            'institutional_holders': stock.institutional_holders,
            'news': stock.news
        }
        if not info['history'].empty:
            cache.set(cache_key, info, 60*30)  # 30 dakika cache
            return info
        return None  # Veri yoksa None dön
    except Exception as e:
        if 'rate limit' in str(e).lower() or 'too many requests' in str(e).lower():
            return {'error': 'Çok sık sorgu yapıldı, lütfen birkaç dakika sonra tekrar deneyin.'}
        logger.error(f"Stock info error: {str(e)}")
        return None  # Hata olursa da None dön

def generate_stock_analysis(symbol, stock_data):
    """Kısa ve sohbet için uygun hisse özeti döndürür."""
    try:
        history = stock_data['history']
        info = stock_data['info']
        current_price = history['Close'][-1]
        price_change = current_price - history['Close'][0]
        price_change_pct = (price_change / history['Close'][0]) * 100
        target_price = info.get('targetMeanPrice', 'N/A')
        market_cap = info.get('marketCap', 'N/A')
        pe_ratio = info.get('trailingPE', 'N/A')
        company = info.get('shortName', symbol)
        return (
            f"{company} ({symbol}) Hisse Özeti:\n"
            f"- Güncel Fiyat: {current_price:.2f} TL\n"
            f"- Hedef Fiyat: {target_price} TL\n"
            f"- Piyasa Değeri: {market_cap:,} TL\n"
            f"- F/K Oranı: {pe_ratio}\n"
            f"- Son 1 Aylık Değişim: {price_change_pct:+.2f}%"
        )
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
        4. soru sorma kısa ve özlü yanıt ver.
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
def get_stock_data_view(request):
    """Enhanced stock data endpoint"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            symbol = data.get('symbol', '')
            # Check cache
            cache_key = f"stock_data_{symbol}"
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

@csrf_protect
def kayit_view(request):
    if request.method == 'POST':
        if 'email_code' in request.POST:
            # Kod doğrulama aşaması
            input_code = request.POST.get('email_code')
            session_code = request.session.get('email_code')
            name = request.session.get('reg_name')
            email = request.session.get('reg_email')
            password = request.session.get('reg_password')
            if input_code == session_code:
                # Kullanıcıyı oluştur
                if ' ' in name:
                    first_name, last_name = name.split(' ', 1)
                else:
                    first_name, last_name = name, ''
                user = User.objects.create_user(username=email, email=email, password=password, first_name=first_name, last_name=last_name)
                user.save()
                login(request, user)
                # Temizle
                for key in ['email_code', 'reg_name', 'reg_email', 'reg_password']:
                    if key in request.session:
                        del request.session[key]
                return redirect('home')
            else:
                messages.error(request, 'Kod yanlış!')
                return render(request, 'email_code.html')
        else:
            # İlk kayıt formu aşaması
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email')
            password = request.POST.get('password')
            password_confirm = request.POST.get('password_confirm')
            if password != password_confirm:
                messages.error(request, 'Şifreler eşleşmiyor.')
                return render(request, 'kayıt.html')
            if User.objects.filter(username=email).exists():
                messages.error(request, 'Bu e-posta ile zaten bir hesap var.')
                return render(request, 'kayıt.html')
            # Kod üret ve gönder
            code = str(random.randint(100000, 999999))
            request.session['email_code'] = code
            request.session['reg_name'] = name
            request.session['reg_email'] = email
            request.session['reg_password'] = password
            send_mail(
                'TDXBOT E-posta Doğrulama Kodu',
                f'Kayıt işlemini tamamlamak için doğrulama kodunuz: {code}',
                None,
                [email],
                fail_silently=False,
            )
            return render(request, 'email_code.html')
    return render(request, 'kayıt.html')

@csrf_protect
def giris_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'E-posta veya şifre hatalı.')
            return render(request, 'login.html')
    return render(request, 'login.html')

def cikis_view(request):
    logout(request)
    return redirect('home')

def stock_card(request):
    symbol = request.GET.get('symbol')
    user_ip = request.META.get('REMOTE_ADDR', 'unknown')
    stock = get_stock_data(symbol, user_ip=user_ip)
    return render(request, "partials/stock_card.html", {"stock": stock})

@csrf_exempt
def get_analysis(request):
    """Grafik verilerinden destek/direnç ve kapanış fiyatları ile Gemini API'den açıklayıcı, senaryolu ve HTML formatında analiz alır."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Geçersiz istek.'}, status=400)
    try:
        data = json.loads(request.body)
        closes = data.get('closes', [])
        dates = data.get('dates', [])
        symbol = request.GET.get('symbol', '')
        if not closes or not dates or not symbol:
            return JsonResponse({'status': 'error', 'error': 'Veri eksik.'}, status=400)
        # Destek/direnç hesapla
        support_levels, resistance_levels = find_support_resistance(closes)
        # Daha açıklayıcı, senaryolu ve HTML formatında analiz için prompt
        prompt = f"""
Sen bir borsa teknik analiz asistanısın. Kullanıcı sana {symbol} hissesinin son 1 aylık kapanış fiyatlarını, destek ve direnç seviyelerini verdi.
Kapanış fiyatları: {closes}
Tarihler: {dates}
Destek seviyeleri: {support_levels}
Direnç seviyeleri: {resistance_levels}

Lütfen aşağıdaki gibi detaylı ve HTML formatında teknik analiz hazırla:
- <h2>{symbol} Hisse Senedi Teknik Analizi (Son 1 Ay)</h2>
- <b>Fiyat Hareketi</b> başlığı altında kısa ve açıklayıcı bir özet ver.
- <b>Destek Seviyeleri</b> ve <b>Direnç Seviyeleri</b> başlıkları ile seviyeleri <ul><li>maddeler halinde</li></ul> belirt.
- <b>Olası Senaryolar</b> başlığı altında en az 3 farklı teknik senaryo üret:
    <ul>
      <li><b>Destek Kırılırsa:</b> ...</li>
      <li><b>Direnç Aşılırsa:</b> ...</li>
      <li><b>Yatayda Kalırsa:</b> ...</li>
      <li><b>Ekstra Senaryo:</b> (hacim artışı, haber etkisi, vb. gibi hisseye özel bir durum)</li>
    </ul>
- Her senaryoda fiyatın hangi seviyelere gidebileceğini, yatırımcıların nelere dikkat etmesi gerektiğini ve teknik göstergelerin ne anlama geldiğini kısa kısa açıkla.
- Sonucu <b>şık ve okunaklı HTML</b> ile, başlıklar, <ul> listeler, <span style='color:...'> gibi vurgularla sun.
- Yatırım tavsiyesi verme, sadece teknik veriye dayalı özet sun.
"""
        api_key = 'AIzaSyCpdN84xuqoi5wKKYBq9GRyhxIIq6RFtyc'
        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'
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
        analysis = result['candidates'][0]['content']['parts'][0]['text'] if 'candidates' in result else 'Analiz alınamadı.'
        cache_key_raw = f"analysis_{symbol}_{str(closes)}_{str(dates)}"
        cache_key = 'analysis_' + hashlib.sha256(cache_key_raw.encode('utf-8')).hexdigest()
        cache.set(cache_key, analysis, 60*60)  # 1 saat cache
        return JsonResponse({'status': 'success', 'data': {'analysis': analysis, 'cached': False}})
    except Exception as e:
        logger.error(f"get_analysis error: {str(e)}")
        return JsonResponse({'status': 'error', 'error': 'Analiz alınırken hata oluştu.'}, status=500) 

@require_GET
def important_news_api(request):
    days = int(request.GET.get('days', 2))
    news = get_important_news(days=days)
    # Sadece gerekli alanları döndür
    news_data = [
        {
            'title': n['title'],
            'summary': n['summary'],
            'link': n['link'],
            'source': n['source'],
            'published_dt': n['published_dt'].strftime('%d.%m.%Y %H:%M') if n['published_dt'] else '',
            'category': n['category']
        }
        for n in news
    ]
    return JsonResponse({'important_news': news_data}) 

def analyze_stock_image_with_gemini(image_path):
    if not PIL_AVAILABLE:
        return "PIL (Pillow) modülü bulunamadı. Görsel analizi özelliği devre dışı."
    
    try:
        GEMINI_API_KEY = 'AIzaSyBSJJob1ovfUYHgyV4pbKGF0uBuL5v7VxQ'
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')

        image = Image.open(image_path)
        image = image.convert('RGB')

        prompt = """
        Aşağıdaki görselde bir tablo var. Lütfen:
        - Tablodaki tüm başlıkları ve satırları eksiksiz olarak oku.
        - Tabloyu, başlıkları ve satırlarıyla birlikte, sadece HTML <table> etiketiyle döndür.
        - Tabloyu profesyonel ve okunaklı yap: <table> etiketine border, başlık satırına <thead>, zebra (alternatif satır rengi) ve okunabilirlik için stil ekle.
        - Tablo başlığını <caption> etiketiyle ekle (varsa).
        - Sadece tabloyu döndür, başka açıklama veya yorum ekleme.
        """

        response = model.generate_content([prompt, image])
        return response.text

    except Exception as e:
        logging.error(f"Gemini API error: {str(e)}")
        return f"Analiz sırasında hata oluştu: {str(e)}"

def stock_image_analysis_view(request):
    """Hisse görsel analizi sayfası (yetkili kullanıcı yükleyebilir, diğerleri sadece görebilir)"""
    can_upload = request.user.has_perm('stockdb.can_upload_stock_image')
    if can_upload and request.method == 'POST':
        if not PIL_AVAILABLE:
            messages.error(request, 'PIL (Pillow) modülü bulunamadı. Görsel analizi özelliği devre dışı.')
            return redirect('stock_image_analysis')
            
        title = request.POST.get('title')
        description = request.POST.get('description')
        image = request.FILES.get('image')
        if title and image:
            stock_image = StockImage.objects.create(
                title=title,
                description=description,
                image=image
            )
            image_path = stock_image.image.path
            analysis = analyze_stock_image_with_gemini(image_path)
            stock_image.gemini_analysis = analysis
            stock_image.is_analyzed = True
            stock_image.save()
            messages.success(request, 'Görsel başarıyla yüklendi ve analiz edildi!')
            return redirect('stock_image_analysis')
    stock_images = StockImage.objects.all().order_by('-created_at')
    return render(request, 'stock_image_analysis.html', {
        'stock_images': stock_images,
        'can_upload': can_upload,
        'pil_available': PIL_AVAILABLE
    })

@login_required
def delete_stock_image(request, image_id):
    if not request.user.has_perm('stockdb.can_upload_stock_image'):
        return HttpResponse('Yetkiniz yok.', status=403)
    stock_image = get_object_or_404(StockImage, id=image_id)
    stock_image.delete()
    messages.success(request, 'Görsel başarıyla silindi!')
    return redirect('stock_image_analysis') 