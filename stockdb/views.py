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
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser
import pandas as pd

CACHE_DIR = "cache"

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
    # Sembol-şirket adı eşleştirmesi (örnek, genişletebilirsiniz)
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
        # Rate limiting check
        if cache.get(f"ratelimit_{ip}"):
            return JsonResponse({
                'status': 'error',
                'message': 'Lütfen 10 saniye bekleyip tekrar deneyiniz.',
                'code': 'RATE_LIMIT_EXCEEDED'
            }, status=429)
        cache.set(f"ratelimit_{ip}", True, timeout=10)
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
Lütfen {symbol} hissesi için aşağıdaki verilere dayalı, kutular ve başlıklarla bölümlenmiş, profesyonel ve okunaklı bir analiz raporu hazırla.
Raporu HTML formatında üret:
- Her ana başlık için <div class='analysis-section'><h3>Başlık</h3>...</div> kullan.
- Önemli noktaları <ul><li> ile vurgula.
- Sonuç ve uyarı bölümlerini <strong> ve <em> ile öne çıkar.
- Paragrafları <p> ile yaz.
- Gerekiyorsa <span style='color:#ffd600'>renkli</span> vurgular ekle.

Aşağıda, son 1 ayın tarih ve kapanış fiyatları ile, ilgili günlerde çıkan haberler tablo halinde verilmiştir. Teknik analizini bu fiyat serisine ve haberlerin fiyat üzerindeki olası etkisine göre yap. Özellikle haberlerin fiyat hareketleriyle ilişkisini analiz et.

FİYAT TABLOSU:
{price_table}

HABER TABLOSU:
{news_table}

PIYASA VERILERI:
- Son Kapanış: {last_price:.2f} TL
- Değişim: {price_change:.2f} TL (%{price_change_pct:.2f})
- 30 Günlük Ortalama: {avg_price:.2f} TL
- Analiz Periyodu: {dates[0]} - {dates[-1]}

GÜNCEL HABERLER:
{news_text}

Aşağıdaki başlıklar altında analiz yap:
1. Teknik Görünüm (Yalnızca yukarıdaki fiyat serisine ve trende göre)
2. Hisse Gidişatı nasıl olacak?
3. <strong>Bana Göre hangisi daha iyi?</strong>: Analizlerini oku ve ortaya bir kendince olabilecek senaryoyu nedeniyle açıkla.
4. Hissenin Son Fiyat Verilerine Göre Riskler ve Fırsatlar
5. Destek ve Direnç seviyelerine göre fiyat hedefleri ve Senaryoları

Notlar:
- Teknik analizde sadece yukarıdaki fiyat serisini ve trendi kullan.
- Haberleri ve fiyat serisini birlikte analiz et, haberlerin fiyat üzerindeki etkisini yorumla.
- Hiçbir başlıkta 'veri yok', 'analiz yapılamaz' veya benzeri bir ifade kullanma.
- Gerekirse genel piyasa bilgisini ve tipik hisse senedi analiz yöntemlerini kullanarak açıklama üret.
- Her başlık için, elindeki tüm verileri ve genel piyasa bilgisini kullanarak açıklama ve analiz üret.
"""
            # Make API call to Gemini
            api_key = 'AIzaSyBSJJob1ovfUYHgyV4pbKGF0uBuL5v7VxQ'
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
            raw_analysis = result['candidates'][0]['content']['parts'][0]['text']
            # Format the analysis response
            formatted_analysis = {
                'summary': {
                    'last_price': last_price,
                    'change': price_change,
                    'change_percentage': price_change_pct,
                    'average_price': avg_price
                },
                'analysis': raw_analysis,
                'generated_at': datetime.now().isoformat(),
                'news_count': len(news)
            }
            # Cache the formatted result
            cache.set(cache_key, formatted_analysis, timeout=60*60)  # 1 saat cache
            return JsonResponse({
                'status': 'success',
                'data': formatted_analysis,
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

def home(request):
    top10 = [
        'THYAO.IS', 'GARAN.IS', 'AKBNK.IS', 'SISE.IS', 'YKBNK.IS',
        'KCHOL.IS', 'EREGL.IS', 'SASA.IS', 'TUPRS.IS', 'ISCTR.IS'
    ]
    return render(request, 'home.html', {'top10': top10}) 