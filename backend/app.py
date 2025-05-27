import matplotlib
matplotlib.use('Agg')

from flask import Flask, render_template_string, request, render_template, send_from_directory, url_for, jsonify, redirect
import os
import json
import matplotlib.pyplot as plt
import io
import base64
import requests
import re
import feedparser
import importlib.util
import sys
import subprocess
import plotly.graph_objs as go
from plotly.offline import plot
import markdown
import time
import hashlib
import random
from bs4 import BeautifulSoup
from datetime import datetime
import urllib.parse
import numpy as np
import cv2
import asyncio
try:
    from chart_analysis import analyze_chart
except ImportError:
    from backend.chart_analysis import analyze_chart
try:
    from appbot import analyze_sentiment, check_reminders, calculate_from_message, extract_stock_symbol, get_stock_data, generate_response, check_faq, find_similar_faq, answer_question, FAQ_ANSWERS, GREETINGS, THANKS
except ImportError:
    from backend.appbot import analyze_sentiment, check_reminders, calculate_from_message, extract_stock_symbol, get_stock_data, generate_response, check_faq, find_similar_faq, answer_question, FAQ_ANSWERS, GREETINGS, THANKS

app = Flask(__name__)
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# --- CACHE DOSYALARI YOKSA fetcher.py'yi OTOMATİK ÇALIŞTIR ---
def run_fetcher_if_needed():
    # Kontrol edilecek dosyalar
    cache_files = [
        os.path.join(CACHE_DIR, f"{symbol}.json")
        for symbol in ["asels", "garan", "thyao", "miatk", "froto"]
    ]
    if not all(os.path.exists(f) for f in cache_files):
        try:
            spec = importlib.util.spec_from_file_location("fetcher", os.path.join(os.path.dirname(__file__), "fetcher.py"))
            fetcher = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fetcher)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(fetcher.fetch_all_stocks())
        except Exception as e:
            print(f"fetcher.py otomatik çalıştırılamadı: {e}")

run_fetcher_if_needed()
# --- --- ---

GEMINI_API_KEY = "AIzaSyAQXzOVG-BP5-EGZl2ts9d6kp_n-2pvM_U"

GEMINI_CACHE_DIR = os.path.join(CACHE_DIR, "gemini_cache")
os.makedirs(GEMINI_CACHE_DIR, exist_ok=True)

TEMPLATE = """
<!DOCTYPE html>
<html lang=\"tr\">
<head>
    <meta charset=\"UTF-8\">
    <title>BIST100 Hisse Fiyatları Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #fff;
            color: #1a2636;
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        h2 {
            text-align: center;
            font-size: 2.1rem;
            font-weight: 700;
            margin-top: 36px;
            margin-bottom: 36px;
            letter-spacing: 0.01em;
        }
        .chart-container {
            width: 900px;
            margin: 0 auto 48px auto;
            background: #fafbfc;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(44,62,80,0.06);
            padding: 28px 32px 18px 32px;
        }
        h3 {
            text-align: center;
            font-size: 1.35rem;
            font-weight: 600;
            margin-bottom: 18px;
            margin-top: 0;
            letter-spacing: 0.01em;
        }
        .analyze-link {
            margin-top: 10px;
            display: block;
            text-align: center;
            font-size: 1.08rem;
            color: #2a5db0;
            text-decoration: none;
            font-weight: 500;
        }
        .analyze-link:hover {
            text-decoration: underline;
        }
        .news-box {
            background: #f9f9f9;
            border: 1px solid #e0e0e0;
            padding: 10px;
            margin-top: 10px;
            border-radius: 6px;
            font-size: 1.01rem;
        }
        ul { padding-left: 18px; }
        li { margin-bottom: 4px; }
    </style>
</head>
<body>
    <div style=\"width:100%;display:flex;flex-direction:column;justify-content:center;align-items:center;\">
        <h2>BIST100 En Çok Tercih Edilen Hisse Fiyatları (Fiyat, Destek, Direnç)</h2>
        {% for stock in stocks %}
        <div class=\"chart-container\"> 
            <h3>{{ stock.symbol }} Fiyat, Destek ve Direnç Grafiği</h3>
            <img src=\"data:image/png;base64,{{ stock.img_data }}\" alt=\"{{ stock.symbol }} grafiği\" style=\"display:block; margin:0 auto;\">
            <!-- Prompt kutusu gizlendi -->
            <a class=\"analyze-link\" href=\"/analyze/{{ stock.symbol }}\" target=\"_blank\">TDX ile Senaryo Analizi</a>
            {% if stock.news %}
            <div class=\"news-box\">
                <b>Son Haberler:</b>
                <ul>
                {% for item in stock.news %}
                    <li><a href=\"{{ item.link }}\" target=\"_blank\">{{ item.title }}</a></li>
                {% endfor %}
                </ul>
            </div>
            {% endif %}
        </div>
        {% endfor %}
        {% if not stocks %}
        <p style=\"text-align:center; font-size:1.1rem;\">Hiç veri bulunamadı. Lütfen cache klasöründe JSON dosyalarını kontrol edin.</p>
        {% endif %}
    </div>
</body>
</html>
"""

ANALYZE_TEMPLATE = """
<!DOCTYPE html>
<html lang='tr'>
<head>
    <meta charset='UTF-8'>
    <title>{{ symbol }} TDX Senaryo Analizi</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        html, body {
            height: 100%;
        }
        body {
            font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
            background: #181c20;
            color: #eaf6ff;
            margin: 0;
            padding: 0;
            min-height: 100vh;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            position: sticky;
            top: 0;
            width: 100%;
            background: rgba(44, 62, 80, 0.92);
            padding: 0 0;
            margin-bottom: 0;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 70px;
            z-index: 10;
            box-shadow: 0 2px 12px rgba(44,62,80,0.10);
        }
        .navbar-title {
            font-size: 2.3rem;
            font-weight: 700;
            color: #eaf6ff;
            margin-left: 40px;
            letter-spacing: 0.01em;
        }
        .navbar-menu {
            display: flex;
            gap: 36px;
            margin-right: 40px;
        }
        .navbar-link {
            color: #eaf6ff;
            text-decoration: none;
            font-size: 1.18rem;
            font-weight: 500;
            padding: 10px 20px;
            border-radius: 8px;
            transition: background 0.2s, color 0.2s;
        }
        .navbar-link:hover, .navbar-link.active {
            background: #1e2a38;
            color: #4fc3f7;
        }
        .container {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            align-items: center;
            min-height: 80vh;
            color: #eaf6ff;
            margin-top: 40px;
            width: 100%;
            max-width: 1200px;
            margin-left: auto;
            margin-right: auto;
        }
        h2 {
            text-align: center;
            font-size: 2.7rem;
            font-weight: 800;
            margin-top: 36px;
            margin-bottom: 36px;
            letter-spacing: 0.01em;
            color: #4fc3f7;
        }
        h3 {
            text-align: center;
            font-size: 1.7rem;
            font-weight: 700;
            margin-bottom: 24px;
            margin-top: 0;
            letter-spacing: 0.01em;
            color: #4fc3f7;
        }
        .tdx-answer {
            background: #23272b;
            border: 1px solid #3a3f47;
            border-radius: 14px;
            padding: 32px 38px;
            margin-bottom: 38px;
            font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
            font-size: 1.25rem;
            color: #eaf6ff;
            line-height: 1.8;
            box-shadow: 0 2px 12px rgba(44, 62, 80, 0.10);
        }
        .tdx-answer p {
            margin: 16px 0 16px 0;
            font-size: 1.18rem;
        }
        .tdx-answer ul {
            margin: 14px 0 14px 28px;
            padding-left: 22px;
        }
        .tdx-answer li {
            margin-bottom: 10px;
            font-size: 1.18rem;
        }
        .tdx-answer strong, .tdx-answer h1, .tdx-answer h2, .tdx-answer h3 {
            font-size: 1.35rem;
            font-weight: bold;
            color: #4fc3f7;
            margin-top: 22px;
            margin-bottom: 12px;
            display: block;
        }
        .tdx-answer strong {
            font-weight: bold;
            color: #4fc3f7;
            font-size: 1.22rem;
        }
        .news-box {
            background: #23272b;
            border: 1px solid #3a3f47;
            padding: 18px;
            margin-top: 18px;
            border-radius: 10px;
            font-size: 1.13rem;
            color: #eaf6ff;
        }
        ul { padding-left: 22px; }
        li { margin-bottom: 8px; }
        a { color: #4fc3f7; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .bist-button {
            display: block;
            width: 280px;
            margin: 40px auto 0 auto;
            padding: 22px 0;
            background: linear-gradient(90deg, #1565c0 0%, #00bcd4 100%);
            color: #fff;
            border: none;
            border-radius: 12px;
            font-size: 1.35rem;
            cursor: pointer;
            transition: background 0.3s, color 0.3s, transform 0.2s;
            text-align: center;
            text-decoration: none;
            font-weight: 600;
            letter-spacing: 0.02em;
            box-shadow: 0 2px 12px rgba(21,101,192,0.10);
        }
        .bist-button:hover {
            background: linear-gradient(90deg, #00bcd4 0%, #1565c0 100%);
            color: #eaf6ff;
            transform: scale(1.05);
        }
        .chart-container {
            width: 100%;
            max-width: 1100px;
            min-height: 700px;
            margin: 0 auto 48px auto;
            background: rgba(30, 32, 34, 0.95);
            border-radius: 20px;
            box-shadow: 0 2px 16px rgba(44,62,80,0.13);
            padding: 48px 48px 38px 48px;
        }
        @media (max-width: 900px) {
            .container, .chart-container { max-width: 98vw; padding: 10px; }
            .tdx-answer { padding: 18px 8px; font-size: 1.05rem; }
            h2 { font-size: 2rem; }
            h3 { font-size: 1.2rem; }
            .bist-button { width: 98vw; font-size: 1.1rem; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="navbar-title">BIST100 Analiz Platformu</div>
        <nav class="navbar-menu">
            <a href="/" class="navbar-link">Anasayfa</a>
            <a href="/analyze-bist" class="navbar-link">Toplu Analiz</a>
            <a href="#" class="navbar-link">Hakkında</a>
            <a href="#" class="navbar-link">İletişim</a>
        </nav>
    </div>
    <div class="container">
        <h2>{{ symbol }} için TDX API ile Senaryo Analizi</h2>
        <h3>TDX Yanıtı:</h3>
        <div class="tdx-answer">{{ analysis|safe }}</div>
        <div class="chart-container">
            <h3>{{ symbol }} Fiyat ve Olası Senaryolar Grafiği</h3>
            {{ plotly_div|safe }}
        </div>
        {% if news %}
        <div class="news-box">
            <b>Son Haberler:</b>
            <ul>
            {% for item in news %}
                <li><a href="{{ item.link }}" target="_blank">{{ item.title }}</a></li>
            {% endfor %}
            </ul>
        </div>
        {% endif %}
        <a href="/" class="bist-button">&larr; Anasayfaya Dön</a>
    </div>
</body>
</html>
"""

def make_llm_prompt(symbol, prices, support, resistance, news=None):
    news_text = ""
    if news:
        news_text = "\nSon 1 ayda çıkan önemli haber başlıkları ve özetleri:\n"
        for item in news:
            if isinstance(item, dict) and isinstance(item.get('title', None), str):
                title = item.get('title', '')
                summary = item.get('summary', '') if isinstance(item.get('summary', ''), str) else ''
                news_text += f"- {title}: {summary}\n"
            elif isinstance(item, str):
                news_text += f"- {item}\n"
            # Diğer tipler atlanır
        news_text += "\nEğer haberler pozitifse yükseliş ihtimalini daha yüksek değerlendir."
    return f"""
Aşağıda {symbol} hissesinin son fiyat kapanışları, destek ve direnç seviyeleri verilmiştir:

Fiyatlar: {prices}
Destek seviyeleri: {support}
Direnç seviyeleri: {resistance}
{news_text}

Lütfen teknik analiz bakış açısıyla:
- Fiyatın genel trendini yorumla.
- Olası 3 farklı senaryo üret (ör: yükseliş, yatay, düşüş).
- Her senaryo için önümüzdeki 5 günün tahmini kapanış fiyatlarını [fiyat1, fiyat2, ...] şeklinde, sadece sayısal değerlerle ve sıralı olarak ver.
- Senaryoları kısa başlıklarla açıkla.
- Sonuç olarak, hangi senaryonun olma ihtimalini daha yüksek buluyorsan, bunu açıkla ve nedenini belirt. Ayrıca yatırımcıya kısa bir öneri ver.

Cevabını sade ve anlaşılır bir şekilde, teknik analiz terimleriyle ver. Her bir bölümü **kalın ve büyük başlıklarla**, alt alta ve madde madde, açık ve net şekilde yaz. Her başlık ve altındaki açıklama arasında boşluk bırak. Senaryoları ve sonuç kısmını numaralı veya noktalı madde olarak belirt.
"""

def parse_stock_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        if "data" in data:
            stock_data = data["data"]
        else:
            stock_data = data
        prices = stock_data.get("prices", [])
        dates = stock_data.get("dates", [])
        support_levels = []
        resistance_levels = []
        for i in range(1, len(prices)-1):
            if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                support_levels.append(prices[i])
            elif prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                resistance_levels.append(prices[i])
        return {
            "symbol": stock_data.get("symbol", os.path.basename(path).replace(".json", "")),
            "dates": dates,
            "prices": prices,
            "support_levels": support_levels,
            "resistance_levels": resistance_levels
        }

def plot_to_base64(dates, prices, support_levels, resistance_levels, symbol, scenario_lists=None):
    import matplotlib.dates as mdates
    plt.figure(figsize=(14, 6))
    x = list(range(len(dates)))
    # Silik TDX AI yazısı arka plana
    plt.text(
        0.5, 0.5, 'TDX AI',
        fontsize=90, color='gray', alpha=0.13,
        ha='center', va='center', rotation=15,
        transform=plt.gca().transAxes, zorder=0
    )
    plt.plot(x, prices, label="Fiyat", color="blue", linewidth=2)
    # Destek çizgileri: kalın, yeşil, grafik boyunca uzatılmış ve etiketli
    for idx, s in enumerate(support_levels):
        plt.axhline(s, color="green", linestyle="--", linewidth=2, alpha=0.7, label="Destek" if idx == 0 else None)
    # Direnç çizgileri: kalın, kırmızı, grafik boyunca uzatılmış ve etiketli
    for idx, r in enumerate(resistance_levels):
        plt.axhline(r, color="red", linestyle="--", linewidth=2, alpha=0.7, label="Direnç" if idx == 0 else None)
    # Senaryoları çiz
    if scenario_lists:
        colors = ["orange", "purple", "brown"]
        for i, scenario in enumerate(scenario_lists):
            if len(scenario) > 0:
                future_x = list(range(len(dates), len(dates) + len(scenario)))
                plt.plot(
                    future_x, scenario,
                    label=f"Senaryo {i+1}",
                    color=colors[i % len(colors)],
                    linestyle='-', linewidth=2, marker='o', alpha=0.9
                )
                plt.scatter(future_x, scenario, color=colors[i % len(colors)], s=40)
                # Her senaryo fiyatı için yatay çizgi ekle
                for price in scenario:
                    plt.axhline(price, color=colors[i % len(colors)], linestyle='--', linewidth=1, alpha=0.3)
                # TP ve SL noktalarını bul
                tp = max(scenario)
                sl = min(scenario)
                entry = scenario[0]
                kar_yuzde = (tp - entry) / entry * 100
                zarar_yuzde = (sl - entry) / entry * 100
                # TP çizgisi ve metni
                plt.axhline(tp, color=colors[i % len(colors)], linestyle='-', linewidth=2, alpha=0.7)
                plt.text(len(dates) + len(scenario) - 0.5, tp, f"TP: %{kar_yuzde:.1f}", color=colors[i % len(colors)], fontsize=10, va='bottom', ha='right', fontweight='bold')
                # SL çizgisi ve metni
                plt.axhline(sl, color=colors[i % len(colors)], linestyle='-', linewidth=2, alpha=0.7)
                plt.text(len(dates) + len(scenario) - 0.5, sl, f"SL: %{zarar_yuzde:.1f}", color=colors[i % len(colors)], fontsize=10, va='top', ha='right', fontweight='bold')
    # X ekseni: tarihleri ve gelecek noktaları göster
    all_x = x + list(range(len(dates), len(dates) + (len(scenario_lists[0]) if scenario_lists else 0)))
    all_dates = dates + [f"Gelecek {i+1}" for i in range(len(all_x) - len(dates))]
    plt.xticks(all_x, all_dates, rotation=45, fontsize=9)
    plt.xlabel("Tarih")
    plt.ylabel("Fiyat (TRY)")
    plt.title(f"{symbol} Fiyat, Destek, Direnç ve Senaryo Simülasyonu")
    plt.legend()
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    img_data = base64.b64encode(buf.read()).decode("utf-8")
    return img_data

def get_prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

def gemini_cached(prompt, api_key):
    prompt_hash = get_prompt_hash(prompt)
    cache_path = os.path.join(GEMINI_CACHE_DIR, f"{prompt_hash}.json")
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)["result"]
    # Yoksa API'ye sor
    result = send_to_gemini(prompt, api_key)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"result": result}, f, ensure_ascii=False, indent=2)
    return result

def send_to_gemini(prompt, api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return "Yanıt çözümlenemedi."
    else:
        return f"API Hatası: {response.status_code} - {response.text}"

def extract_scenarios_from_gemini_response(response_text):
    scenario_pattern = re.compile(r'\[(.*?)\]')
    scenarios = scenario_pattern.findall(response_text)
    scenario_lists = []
    for s in scenarios:
        try:
            prices = [float(x.strip()) for x in s.split(',') if x.strip()]
            if len(prices) > 0:
                scenario_lists.append(prices)
        except Exception:
            continue
    return scenario_lists

def parse_turkish_time(time_str):
    """Convert Turkish time strings like '5 saat önce' to a datetime object"""
    now = datetime.now()
    
    if 'saat önce' in time_str:
        hours = int(time_str.split()[0])
        return now.replace(hour=now.hour - hours, minute=0, second=0).strftime("%Y-%m-%d %H:%M")
    elif 'dakika önce' in time_str:
        minutes = int(time_str.split()[0])
        return now.replace(minute=now.minute - minutes, second=0).strftime("%Y-%m-%d %H:%M")
    elif 'gün önce' in time_str:
        days = int(time_str.split()[0])
        return now.replace(day=now.day - days, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M")
    else:
        # If format is unknown, return as is
        return time_str



def scrape_bist_news(symbol=None, count=10):
    import feedparser
    import urllib.parse
    import re
    if symbol:
        query = f"{symbol} BIST"
    else:
        query = "BIST Borsa İstanbul"
    query_encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={query_encoded}&hl=tr&gl=TR&ceid=TR:tr"
    feed = feedparser.parse(url)
    news_data = []
    for entry in feed.entries[:count]:
        # Kaynak bilgisini bul
        source = ''
        if 'source' in entry and entry.source and hasattr(entry.source, 'title'):
            source = entry.source.title
        elif 'summary' in entry and entry.summary:
            # Örneğin: '... - Rota Borsa' gibi bir ifade varsa summary'nin sonunda
            match = re.search(r'-\s*([\wÇçĞğİıÖöŞşÜü\s]+)$', entry.summary)
            if match:
                source = match.group(1).strip()
        elif 'title' in entry and entry.title:
            match = re.search(r'-\s*([\wÇçĞğİıÖöŞşÜü\s]+)$', entry.title)
            if match:
                source = match.group(1).strip()
        news_data.append({
            'title': entry.title,
            'link': entry.link,
            'summary': entry.summary if 'summary' in entry else "",
            'published': entry.published if 'published' in entry else "",
            'source': source
        })
    return news_data

def get_yahoo_news(symbol, count=5):
    """Get news for a specific symbol from Google News"""
    try:
        # Use the general BIST news scraper
        news_data = scrape_bist_news()
        
        # Filter news that might be related to the specific symbol
        symbol_news = []
        for news in news_data:
            if symbol.lower() in news['title'].lower():
                symbol_news.append(news)
                if len(symbol_news) >= count:
                    break
        
        return symbol_news
    except Exception as e:
        print(f"Error getting news for {symbol}: {e}")
        return []

def save_news_to_json(symbol, news, out_dir=CACHE_DIR):
    """Save news data to a JSON file"""
    try:
        symbol = symbol.lower()
        news_file = os.path.join(out_dir, f"{symbol}_news.json")
        with open(news_file, 'w', encoding='utf-8') as f:
            json.dump({
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "news": news
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving news for {symbol}: {e}")

# fetcher.py'den get_google_news ve save_news_to_json fonksiyonlarını dinamik olarak yükle
fetcher_path = os.path.join(os.path.dirname(__file__), 'fetcher.py')
spec = importlib.util.spec_from_file_location("fetcher", fetcher_path)
fetcher = importlib.util.module_from_spec(spec)
sys.modules["fetcher"] = fetcher
spec.loader.exec_module(fetcher)

@app.route("/")
def index():
    return render_template('base.html')

@app.route("/analyze-bist")
def analyze_bist():
    stocks = []
    for filename in os.listdir(CACHE_DIR):
        if filename.endswith(".json") and not filename.endswith("_news.json"):
            file_path = os.path.join(CACHE_DIR, filename)
            try:
                stock = parse_stock_json(file_path)
                stock["img_data"] = plot_to_base64(
                    stock["dates"], stock["prices"], stock["support_levels"], stock["resistance_levels"], stock["symbol"]
                )
                stock["llm_prompt"] = make_llm_prompt(
                    stock["symbol"], stock["prices"], stock["support_levels"], stock["resistance_levels"]
                )
                # Her yüklemede güncel haberleri çek ve kaydet
                news = get_yahoo_news(stock["symbol"])
                save_news_to_json(stock["symbol"], news)
                stock["news"] = news
                # Gemini API çağrısı ve gecikme
                prompt = make_llm_prompt(
                    stock["symbol"], stock["prices"], stock["support_levels"], stock["resistance_levels"], news=news
                )
                stock["gemini_analysis"] = gemini_cached(prompt, GEMINI_API_KEY)
                time.sleep(1.5)  # Her istekten sonra 1.5 saniye bekle
                stocks.append(stock)
            except Exception as e:
                print(f"Hata: {filename} dosyası okunamadı: {e}")
    return render_template_string(TEMPLATE, stocks=stocks)

def plot_scenarios_interactive(dates, prices, support_levels, resistance_levels, symbol, scenario_lists=None, news=None):
    fig = go.Figure()
    x = list(range(len(dates)))
    # Silik TDX AI yazısı arka plana annotation olarak ekle
    fig.add_annotation(
        text="TDX AI",
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=80, color="rgba(120,120,120,0.13)"),
        opacity=0.13,
        xanchor="center", yanchor="middle"
    )
    fig.add_trace(go.Scatter(x=x, y=prices, mode='lines+markers', name='Fiyat', line=dict(color='blue')))
    # Destek ve direnç çizgileri
    for s in support_levels:
        fig.add_hline(y=s, line=dict(color='green', dash='dash'), name='Destek')
    for r in resistance_levels:
        fig.add_hline(y=r, line=dict(color='red', dash='dash'), name='Direnç')
    # Senaryolar
    colors = ["orange", "purple", "brown"]
    if scenario_lists:
        for i, scenario in enumerate(scenario_lists):
            if len(scenario) > 0:
                future_x = list(range(len(dates), len(dates) + len(scenario)))
                entry = scenario[0]
                tp = max(scenario)
                sl = min(scenario)
                kar_yuzde = (tp - entry) / entry * 100
                zarar_yuzde = (sl - entry) / entry * 100
                hovertext = [
                    f"Senaryo {i+1}<br>Fiyat: {fiyat:.2f}<br>TP: {tp:.2f} (%{kar_yuzde:.1f})<br>SL: {sl:.2f} (%{zarar_yuzde:.1f})"
                    for fiyat in scenario
                ]
                fig.add_trace(go.Scatter(
                    x=future_x, y=scenario, mode='lines+markers',
                    name=f"Senaryo {i+1}",
                    line=dict(color=colors[i % len(colors)]),
                    marker=dict(size=10),
                    hoverinfo='text',
                    hovertext=hovertext
                ))
                for fiyat in scenario:
                    fig.add_hline(y=fiyat, line=dict(color=colors[i % len(colors)], dash='dot'), opacity=0.25)
    # Haber markerları
    if news:
        news_x = []
        news_y = []
        news_hover = []
        for item in news:
            if 'published' in item:
                pub_date = item['published'][:10]
                if pub_date in dates:
                    idx = dates.index(pub_date)
                    news_x.append(idx)
                    news_y.append(prices[idx])
                    news_hover.append(f"<b>Haber:</b> {item['title']}<br><b>Özet:</b> {item['summary']}")
        if news_x:
            fig.add_trace(go.Scatter(
                x=news_x, y=news_y, mode='markers',
                name='Haber',
                marker=dict(symbol='diamond', size=16, color='red'),
                hoverinfo='text',
                hovertext=news_hover,
                showlegend=True
            ))
    fig.update_layout(
        title=f"{symbol} Fiyat, Destek, Direnç ve Senaryo Simülasyonu",
        xaxis_title="Tarih",
        yaxis_title="Fiyat (TRY)",
        legend_title="Açıklama",
        template="plotly_white",
        height=650
    )
    return plot(fig, output_type='div')

@app.route("/analyze/<symbol>")
def analyze(symbol):
    symbol = symbol.lower()
    file_path = os.path.join(CACHE_DIR, f"{symbol}.json")
    news_path = os.path.join(CACHE_DIR, f"{symbol}_news.json")
    if not os.path.exists(file_path):
        return "Veri bulunamadı.", 404
    stock = parse_stock_json(file_path)
    # Haberleri oku
    news = []
    if os.path.exists(news_path):
        with open(news_path, "r", encoding="utf-8") as f:
            news = json.load(f)
    prompt = make_llm_prompt(
        stock["symbol"], stock["prices"], stock["support_levels"], stock["resistance_levels"], news=news
    )
    analysis = gemini_cached(prompt, GEMINI_API_KEY)
    scenario_lists = extract_scenarios_from_gemini_response(analysis)
    plotly_div = plot_scenarios_interactive(
        stock["dates"], stock["prices"], stock["support_levels"], stock["resistance_levels"], stock["symbol"], scenario_lists=scenario_lists, news=news
    )
    analysis_html = markdown.markdown(analysis)
    return render_template_string(ANALYZE_TEMPLATE, symbol=symbol, prompt=prompt, analysis=analysis_html, plotly_div=plotly_div, news=news)

@app.route("/analyze-asels")
def analyze_asels():
    return analyze('asels')

@app.route("/analyze-froto")
def analyze_froto():
    return analyze('froto')

@app.route("/analyze-garan")
def analyze_garan():
    return analyze('garan')

@app.route("/analyze-mia")
def analyze_mia():
    return analyze('miatk')

@app.route("/analyze-thyao")
def analyze_thyao():
    return analyze('thyao')

@app.route('/videos-bg')
def videos_bg():
    video_folder = os.path.join(app.static_folder)
    video_files = [f for f in os.listdir(video_folder) if f.lower().endswith(('.mp4', '.webm', '.ogg'))]
    video_urls = [url_for('static', filename=filename) for filename in video_files]
    return render_template('videos_bg.html', video_urls=video_urls)

@app.route('/hisse', methods=['GET', 'POST'])
def hisse_fiyat_hesapla():
    results = None
    yorumlar = {}
    error = None
    form_values = {}
    if request.method == 'POST':
        try:
            hisse_adi = request.form['hisse_adi'].strip()
            hisse_fiyati = request.form['hisse_fiyati']
            odenmis_sermaye = request.form['odenmis_sermaye']
            net_kar = request.form['net_kar']
            ozsermaye = request.form['ozsermaye']
            piyasa_degeri = request.form['piyasa_degeri']
            fk_orani = request.form['fk_orani']
            pddd_orani = request.form['pddd_orani']
            sektor_fk = request.form.get('sektor_fk')
            sektor_pddd = request.form.get('sektor_pddd')
            analiz_tipi = request.form.get('analiz_tipi', 'hisse_basi')

            # Form değerlerini tekrar göstermek için sakla
            form_values = {
                'hisse_adi': hisse_adi,
                'hisse_fiyati': hisse_fiyati,
                'odenmis_sermaye': odenmis_sermaye,
                'net_kar': net_kar,
                'ozsermaye': ozsermaye,
                'piyasa_degeri': piyasa_degeri,
                'fk_orani': fk_orani,
                'pddd_orani': pddd_orani,
                'sektor_fk': sektor_fk,
                'sektor_pddd': sektor_pddd,
                'analiz_tipi': analiz_tipi
            }

            # Noktalı binlik ayraç ve virgüllü ondalık destekle
            def temizle_sayi_girdisi(deger):
                if deger is None:
                    return None
                return deger.replace('.', '').replace(',', '.')

            def tam_sayi_kontrol(deger, alan_adi):
                try:
                    deger_float = float(temizle_sayi_girdisi(deger))
                    if not deger_float.is_integer():
                        raise ValueError
                    return int(deger_float)
                except:
                    raise ValueError(f"{alan_adi} alanı tam sayı olmalıdır (örn: 10000000 veya 5.249.000.000). Ondalık girmeyiniz.")

            hisse_fiyati = float(temizle_sayi_girdisi(hisse_fiyati))
            odenmis_sermaye = tam_sayi_kontrol(odenmis_sermaye, 'Ödenmiş Sermaye')
            net_kar = tam_sayi_kontrol(net_kar, 'Net Kar')
            ozsermaye = tam_sayi_kontrol(ozsermaye, 'Özsermaye')
            piyasa_degeri = tam_sayi_kontrol(piyasa_degeri, 'Piyasa Değeri')
            fk_orani = float(temizle_sayi_girdisi(fk_orani))
            pddd_orani = float(temizle_sayi_girdisi(pddd_orani))
            sektor_fk = float(temizle_sayi_girdisi(sektor_fk)) if sektor_fk else None
            sektor_pddd = float(temizle_sayi_girdisi(sektor_pddd)) if sektor_pddd else None

            # Negatif ve sıfır değer kontrolü
            if any(x <= 0 for x in [hisse_fiyati, odenmis_sermaye, ozsermaye, piyasa_degeri, fk_orani, pddd_orani]):
                raise ValueError('Sayısal alanlar sıfırdan büyük olmalıdır.')

            # F/K ve PD/DD analizleri
            fk, fk_yorum = fk_degerleme(hisse_fiyati, net_kar, odenmis_sermaye, sektor_fk)
            pddd, pddd_yorum = pddd_degerleme(hisse_fiyati, ozsermaye, odenmis_sermaye, sektor_pddd)

            if analiz_tipi == 'hisse_basi':
                eps = net_kar / odenmis_sermaye if odenmis_sermaye else 0
                bvps = ozsermaye / odenmis_sermaye if odenmis_sermaye else 0
                fiyat_fk = eps * fk_orani
                fiyat_future_fk = eps * fk_orani * 1.27
                fiyat_pddd = bvps * pddd_orani
                fiyat_sermaye = piyasa_degeri / odenmis_sermaye if odenmis_sermaye else 0
                fiyat_potansiyel = (piyasa_degeri * 1.1) / odenmis_sermaye if odenmis_sermaye else 0
                fiyat_ozsermaye_kar = (eps * 2) * fk_orani
                analiz_tipi_aciklama = 'Hisse başı fiyat (EPS/BVPS bazlı)'
            else:
                fiyat_fk = (net_kar * fk_orani) / odenmis_sermaye if odenmis_sermaye else 0
                fiyat_future_fk = (net_kar * fk_orani * 1.27) / odenmis_sermaye if odenmis_sermaye else 0
                fiyat_pddd = (ozsermaye * pddd_orani) / odenmis_sermaye if odenmis_sermaye else 0
                fiyat_sermaye = piyasa_degeri / odenmis_sermaye if odenmis_sermaye else 0
                fiyat_potansiyel = (piyasa_degeri * 1.1) / odenmis_sermaye if odenmis_sermaye else 0
                fiyat_ozsermaye_kar = (net_kar * 2) / odenmis_sermaye if odenmis_sermaye else 0
                analiz_tipi_aciklama = 'Toplam şirket değeri bazlı (diğer bot mantığı)'

            fiyatlar = [
                fiyat_fk,
                fiyat_future_fk,
                fiyat_pddd,
                fiyat_sermaye,
                fiyat_potansiyel,
                fiyat_ozsermaye_kar
            ]
            ortalama_fiyat = sum(fiyatlar) / len(fiyatlar)
            prim_potansiyeli = ((ortalama_fiyat - hisse_fiyati) / hisse_fiyati) * 100

            yorumlar['fk'] = fk_yorum
            yorumlar['pddd'] = pddd_yorum
            results = {
                'hisse_adi': hisse_adi,
                'ortalama_fiyat': ortalama_fiyat,
                'prim_potansiyeli': prim_potansiyeli,
                'fiyatlar': fiyatlar,
                'analiz_tipi_aciklama': analiz_tipi_aciklama
            }

            # Gemini promptu hazırla ve analiz al
            gemini_prompt = f"""
Aşağıda {hisse_adi} hissesinin temel finansal verileri ve değerleme sonuçları verilmiştir:

- Hisse Fiyatı: {hisse_fiyati}
- Ödenmiş Sermaye: {odenmis_sermaye}
- Net Kar: {net_kar}
- Özsermaye: {ozsermaye}
- Piyasa Değeri: {piyasa_degeri}
- F/K Oranı: {fk_orani}
- PD/DD Oranı: {pddd_orani}
- Ortalama Eder Fiyatı: {ortalama_fiyat:.2f}
- Prim Potansiyeli: {prim_potansiyeli:.2f}%
- Hesaplanan Fiyatlar: {', '.join([str(round(f,2)) for f in fiyatlar])}
- Analiz Tipi: {analiz_tipi_aciklama}

Lütfen aşağıdaki şekilde analiz yap:
- Bu veriler ışığında hissenin mevcut fiyatı ile ortalama eder fiyatı arasındaki farkı ve prim potansiyelini değerlendir.
- F/K ve PD/DD oranlarını sektör ortalaması ile karşılaştır (varsa) ve yorumla.
- Hissenin ucuz mu, pahalı mı olduğunu, yatırımcı için risk ve fırsatları teknik ve temel analiz bakış açısıyla özetle.
- Son olarak kısa bir yatırımcı yorumu ve önerisi ver.
Cevabını maddeler halinde, sade ve anlaşılır şekilde yaz.
"""
            gemini_analiz = gemini_cached(gemini_prompt, GEMINI_API_KEY)
        except Exception as e:
            error = str(e)
            gemini_analiz = None
    else:
        gemini_analiz = None
    return render_template('hisse.html', results=results, yorumlar=yorumlar, error=error, form_values=form_values, gemini_analiz=gemini_analiz)

# Yardımcı fonksiyonlar (örnek, basit versiyon)
def fk_degerleme(hisse_fiyati, net_kar, odenmis_sermaye, sektor_fk=None):
    eps = net_kar / odenmis_sermaye if odenmis_sermaye else 0
    fk = hisse_fiyati / eps if eps else 0
    yorum = ''
    if sektor_fk:
        if fk < sektor_fk:
            yorum = 'F/K oranı sektör ortalamasının altında, iskontolu.'
        elif fk > sektor_fk:
            yorum = 'F/K oranı sektör ortalamasının üzerinde, pahalı.'
        else:
            yorum = 'F/K oranı sektör ortalamasına yakın.'
    return fk, yorum

def pddd_degerleme(hisse_fiyati, ozsermaye, odenmis_sermaye, sektor_pddd=None):
    bvps = ozsermaye / odenmis_sermaye if odenmis_sermaye else 0
    pddd = hisse_fiyati / bvps if bvps else 0
    yorum = ''
    if sektor_pddd:
        if pddd < sektor_pddd:
            yorum = 'PD/DD oranı sektör ortalamasının altında, iskontolu.'
        elif pddd > sektor_pddd:
            yorum = 'PD/DD oranı sektör ortalamasının üzerinde, pahalı.'
        else:
            yorum = 'PD/DD oranı sektör ortalamasına yakın.'
    return pddd, yorum

@app.route('/news')
def news_page():
    news = scrape_bist_news(count=12)
    return render_template_string('''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Son BIST Haberleri</title>
    <style>
    body {
      background: #181c23;
      color: #e6e6e6;
      font-family: 'Inter', Arial, sans-serif;
      margin: 0;
      padding: 0;
    }
    .container {
      max-width: 1200px;
      margin: 32px auto;
      padding: 0 10px;
    }
    .row.g-4 {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 16px;
    }
    .news-card {
      background: rgba(33, 150, 243, 0.13); /* Açık, şeffaf mavi */
      border: none;
      border-radius: 10px;
      transition: transform 0.13s, box-shadow 0.13s, border 0.13s, background 0.13s;
      min-height: 80px;
      max-width: 210px;
      flex: 1 1 160px;
      display: flex;
      flex-direction: column;
      margin-bottom: 10px;
      padding: 10px 8px 8px 8px;
      position: relative;
    }
    .news-card:hover {
      background: rgba(33, 150, 243, 0.22); /* Hover'da biraz daha belirgin mavi */
      transform: translateY(-2px) scale(1.01);
      box-shadow: 0 4px 12px rgba(0,0,0,0.16);
      border: 2px solid #4ea1f7;
    }
    .card-title.news-link {
      color: #4ea1f7 !important;
      transition: color 0.13s;
      font-size: 0.97rem;
      text-decoration: none;
      font-weight: bold;
      margin-bottom: 4px;
      display: block;
      line-height: 1.18;
    }
    .card-title.news-link:hover {
      color: #00bcd4 !important;
      text-decoration: underline;
    }
    .news-source-badge {
      background: linear-gradient(90deg, #4ea1f7, #1e5fa3) !important;
      font-size: 0.7em;
      position: absolute;
      top: 7px;
      right: 7px;
      padding: 3px 7px;
      border-radius: 6px;
    }
    .read-more {
      color: #4ea1f7;
      font-size: 0.85em;
      margin-left: 3px;
      text-decoration: none;
    }
    .read-more:hover {
      text-decoration: underline;
    }
    .news-meta {
      color: #a0a0a0;
      font-size: 0.81em;
      margin-bottom: 3px;
      margin-top: 1px;
    }
    .card-text {
      font-size: 0.85em;
      color: #a0a0a0;
      margin-bottom: 2px;
      line-height: 1.22;
    }
    @media (max-width: 900px) {
      .row.g-4 { flex-direction: column; gap: 0; }
      .news-card { max-width: 100%; }
    }
    </style>
</head>
<body>
<div class="container py-4">
  <h2 class="text-center mb-2" style="font-weight:700; letter-spacing:0.01em; color:#4fc3f7; font-size:1.3rem;">
    Son BIST Haberleri
  </h2>
  {% if news|length == 0 %}
    <div class="text-center mt-4">
      <p class="mt-2" style="font-size:1.05rem; color:#4ea1f7;">Şu anda gösterilecek haber bulunamadı.</p>
    </div>
  {% else %}
  <div class="row g-4">
    {% for article in news %}
    <div class="news-card">
      <a href="{{ article.url or article.link }}" target="_blank" class="card-title news-link">
        {{ article.title[:60] }}{% if article.title|length > 60 %}...{% endif %}
      </a>
      <div class="news-meta">
        {{ article.date or article.published }}
      </div>
      <div class="card-text">
        {{ article.summary[:50]|safe }}{% if article.summary|length > 50 %}...{% endif %}
        <a href="{{ article.url or article.link }}" target="_blank" class="read-more">Devamını oku</a>
      </div>
      <span class="badge bg-primary news-source-badge">{{ article.source or 'Kaynak' }}</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}
  <a href="/" class="btn btn-lg btn-primary mt-3" style="background:linear-gradient(90deg,#1565c0,#00bcd4); border:none; font-weight:600; font-size:1rem;">&larr; Anasayfaya Dön</a>
</div>
</body>
</html>
''', news=news)

def load_cached_news(symbol):
    try:
        symbol = symbol.lower()
        with open(f'backend/cache/{symbol}_news.json', 'r', encoding='utf-8') as f:
            news = json.load(f)
            if isinstance(news, dict):  # Eski/boş dosya
                return []
            return news
    except Exception:
        return []

@app.route('/api/news')
def api_news():
    symbol = request.args.get('symbol')
    if not symbol:
        return jsonify({"news": []})
    news = load_cached_news(symbol)
    return jsonify({"news": news})

@app.route('/tavsiye/')
def flask_tavsiye():
    return redirect("http://127.0.0.1:8000/api/tavsiye/", code=302)

@app.route('/analyze/', methods=['GET', 'POST'])
def analyze_chart_route():
    zones_result = []
    encoded_img_data = None

    if request.method == 'POST':
        file = request.files['file']
        if file:
            # --- Görseli RAM üzerinden oku ---
            file_bytes = np.frombuffer(file.read(), np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

            zones_result, encoded_img_data = analyze_chart(img)

    return render_template('chart_analysis.html', zones=zones_result, img_data=encoded_img_data)

@app.route('/chat')
def chat_page():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'response': random.choice(GREETINGS)})
    
    # Duygu analizi
    sentiment = analyze_sentiment(user_message)
    if sentiment:
        return jsonify({'response': sentiment})
    # Hatırlatıcılar
    reminder = check_reminders(user_message)
    if reminder:
        return jsonify({'response': reminder})
    # Hesaplama
    calc = calculate_from_message(user_message)
    if calc:
        return jsonify({'response': calc})
    # Selamlama veya teşekkür ise insansı cevap ver
    if any(word in user_message.lower() for word in ['merhaba', 'selam', 'hey']):
        return jsonify({'response': random.choice(GREETINGS)})
    if any(word in user_message.lower() for word in ['teşekkür', 'sağol', 'eyvallah']):
        return jsonify({'response': random.choice(THANKS)})

    try:
        symbol = extract_stock_symbol(user_message)
        if symbol:
            try:
                stock_data = get_stock_data(symbol)
            except Exception as e:
                if 'çok sık sorgu' in str(e).lower():
                    return jsonify({'response': 'Bu hisseye çok sık sorgu yaptınız. Lütfen birkaç saniye sonra tekrar deneyin.'})
                raise
            if stock_data['price'] is None:
                return jsonify({'response': 'Üzgünüm, bu hisse kodu için veri bulunamadı. Lütfen kodu kontrol edin veya başka bir hisse deneyin.'})
            response = generate_response(symbol, stock_data)
        else:
            # Önce tam/kısmi eşleşme
            faq_answer = check_faq(user_message)
            if faq_answer:
                return jsonify({'response': faq_answer})
            # Soru cevaplama
            question_answer = answer_question(user_message)
            if question_answer:
                return jsonify({'response': question_answer})
            # Sonra benzerlik
            similar = find_similar_faq(user_message)
            if similar:
                suggestion = f'Bunu mu demek istediniz: <b>{similar[0]}</b>?<br><br>{FAQ_ANSWERS[similar[0]]}'
                return jsonify({'response': suggestion})
            response = "Lütfen bir hisse kodu girin (örn: THYAO.IS) veya bir soru sorun :)"
        return jsonify({'response': response})
    except Exception as e:
        if '404' in str(e):
            return jsonify({'response': 'Üzgünüm, bu hisse kodu için veri bulunamadı. Lütfen kodu kontrol edin veya başka bir hisse deneyin.'})
        return jsonify({'response': f'❌ Üzgünüm, bir hata oluştu: {str(e)}'})

if __name__ == "__main__":
    # Flask başlatılmadan önce fetcher.py'yi bir defa çalıştır
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "fetcher.py")])
    app.run(port=5000, debug=True)