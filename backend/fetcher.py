import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import asyncio
import json
import os
from typing import Dict, List
import schedule
import time
from threading import Thread
import sys
import feedparser
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import random
from app import app, db, Stock, save_stock_data, save_news_to_db

GEMINI_API_KEY = "AIzaSyAQXzOVG-BP5-EGZl2ts9d6kp_n-2pvM_U"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
]

class StockDataFetcher:
    def __init__(self, cache_dir: str = None):
        # Always use backend/cache as the default
        if cache_dir is None:
            cache_dir = CACHE_DIR
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
    async def fetch_stock_data(self, symbol: str, period: str = "1mo") -> Dict:
        """Fetch stock data and cache it"""
        cache_file = os.path.join(self.cache_dir, f"{symbol}.json")
        
        # Check if we have recent cached data (24 hours)
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                last_update = datetime.fromisoformat(cached_data['last_update'])
                if datetime.now() - last_update < timedelta(hours=24):
                    return cached_data['data']
        
        # Calculate dynamic delay based on symbol
        # More frequently traded stocks get longer delays
        if symbol in ["THYAO", "GARAN", "ASELS"]:  # High volume stocks
            delay = 5
        elif symbol in ["MIATK", "FROTO"]:  # Medium volume stocks
            delay = 4
        else:  # Other stocks
            delay = 3
            
        # Add delay between requests to avoid rate limiting
        await asyncio.sleep(delay)
        
        # Fetch new data
        try:
            # Add .IS suffix for Borsa Istanbul stocks
            stock = yf.Ticker(f"{symbol}.IS")
            hist = stock.history(period=period)
            
            if hist.empty:
                raise Exception(f"No data found for {symbol}")
            
            data = {
                'symbol': symbol,
                'prices': hist['Close'].tolist(),
                'dates': hist.index.strftime('%Y-%m-%d').tolist(),
                'last_update': datetime.now().isoformat()
            }
            
            # Always save the data to backend/cache
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'data': data, 'last_update': data['last_update']}, f, ensure_ascii=False, indent=2)
            
            return data
            
        except Exception as e:
            print(f"Error fetching data for {symbol}: {str(e)}")
            return None

    async def fetch_multiple_stocks(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch data for multiple stocks concurrently"""
        tasks = [self.fetch_stock_data(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        return {symbol: result for symbol, result in zip(symbols, results) if result is not None}

def run_scheduler():
    """Run the scheduler in a separate thread"""
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

def make_llm_prompt(symbol, prices, support, resistance, news=None):
    news_text = ""
    if news:
        news_text = "\nSon 1 ayda çıkan önemli haber başlıkları ve özetleri:\n"
        for item in news:
            news_text += f"- {item['title']}: {item['summary']}\n"
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

def save_analysis_to_json(symbol, analysis, out_dir="backend/cache"):
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{symbol}_analysis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "analysis": analysis,
            "last_update": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    print(f"Analiz {out_path} dosyasına kaydedildi.")

async def fetch_and_analyze_stock(symbol):
    """Fetch stock data, news and generate analysis"""
    fetcher = StockDataFetcher()
    
    # Fetch stock data
    stock_data = await fetcher.fetch_stock_data(symbol)
    if not stock_data:
        print(f"Error: Could not fetch data for {symbol}")
        return
    
    # Fetch news
    news_google = get_google_news(symbol)
    news_mynet = get_mynet_news(symbol)
    all_news = news_google + news_mynet
    save_news_to_json(symbol, all_news)
    
    # Generate analysis
    prompt = make_llm_prompt(
        symbol,
        stock_data["prices"],
        stock_data.get("support_levels", []),
        stock_data.get("resistance_levels", []),
        news=all_news
    )
    
    # Add delay to avoid rate limiting
    await asyncio.sleep(2)
    
    analysis = send_to_gemini(prompt, GEMINI_API_KEY)
    save_analysis_to_json(symbol, analysis)
    
    print(f"Completed analysis for {symbol}")

async def fetch_all_stocks():
    """Function to fetch all stocks data, news and analysis"""
    fetcher = StockDataFetcher()
    # Top 5 most traded BIST100 stocks
    symbols = ["THYAO", "GARAN", "ASELS", "MIATK", "FROTO"]
    
    # Fetch stock data for all symbols
    results = await fetcher.fetch_multiple_stocks(symbols)
    print(f"[{datetime.now()}] Fetched data for {len(results)} stocks")
    
    # Process each symbol sequentially to avoid rate limiting
    for symbol in symbols:
        await fetch_and_analyze_stock(symbol)
        # Add delay between symbols
        await asyncio.sleep(5)
    
    print(f"[{datetime.now()}] Completed all data fetching and analysis")

def main():
    # Schedule the job to run every day at 06:00 TR time
    schedule.every().day.at("06:00").do(lambda: asyncio.run(fetch_all_stocks()))
    
    # Start the scheduler in a separate thread
    scheduler_thread = Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    print("Stock data fetcher started. Will fetch data every day at 06:00 TR time.")
    print("Press Ctrl+C to exit.")
    
    try:
        # Run the initial fetch
        asyncio.run(fetch_all_stocks())
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")

def get_google_news(symbol, count=10):
    today = datetime.now().strftime("%Y-%m-%d")
    cache_path = os.path.join(CACHE_DIR, f"{symbol}_news.json")
    # 1. Cache dosyası var mı ve bugün mü?
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                news = json.load(f)
                # Her haberin içinde cache_date varsa ve bugünse, tekrar çekme
                if news and isinstance(news, list) and all(item.get("cache_date") == today for item in news if isinstance(item, dict)):
                    return news
        except Exception:
            pass  # Dosya bozuksa devam et
    # 2. Cache yoksa veya eskiyse yeni haber çek
    query = f'"{symbol}" hisse borsa'
    query_encoded = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={query_encoded}&hl=tr&gl=TR&ceid=TR:tr"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    for deneme in range(3):
        r = requests.get(url, headers=headers)
        if r.status_code == 429:
            print("Rate limit! 60 saniye bekleniyor...")
            time.sleep(60)
            continue
        elif r.status_code == 200:
            break
        else:
            time.sleep(5)
    soup = BeautifulSoup(r.text, "xml")
    news = []
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    for item in soup.find_all("item"):
        title = item.title.text if item.title else ""
        link = item.link.text if item.link else ""
        summary = item.description.text if item.description else ""
        pub_date_str = item.pubDate.text if item.pubDate else None
        if pub_date_str:
            try:
                pub_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
            except Exception:
                continue
            if pub_date < one_month_ago:
                continue
            news.append({
                "title": title,
                "link": link,
                "summary": summary,
                "published": pub_date.strftime("%Y-%m-%d %H:%M"),
                "cache_date": today
            })
            if len(news) >= count:
                break
    # Her istekten sonra 2-5 saniye bekle
    time.sleep(random.uniform(2, 5))
    # Cache'e kaydet
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False, indent=2)
    return news

def save_news_to_json(symbol, news, out_dir=None):
    if out_dir is None:
        out_dir = CACHE_DIR
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{symbol}_news.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False, indent=2)
    print(f"Haberler {out_path} dosyasına kaydedildi.")

def fetch_all_news():
    symbols = ["GARAN", "ASELS", "THYAO", "MIATK", "FROTO"]
    for symbol in symbols:
        news_google = get_google_news(symbol)
        # save_news_to_json fonksiyonu gereksiz, çünkü get_google_news zaten cache'e kaydediyor
        print(f"{symbol} için {len(news_google)} haber kaydedildi.")
    print("Seçili BIST şirketleri için Google News haberleri güncellendi.")

def fetch_stock_data(symbol):
    """Fetch stock data and save to database"""
    try:
        # Yahoo Finance'dan veri çek
        stock = yf.Ticker(symbol)
        hist = stock.history(period="1y")
        
        if hist.empty:
            print(f"Veri bulunamadı: {symbol}")
            return
            
        # Destek ve direnç seviyelerini hesapla
        prices = hist['Close'].tolist()
        dates = hist.index.strftime('%Y-%m-%d').tolist()
        support_levels = []
        resistance_levels = []
        
        for i in range(1, len(prices)-1):
            if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                support_levels.append(prices[i])
            elif prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                resistance_levels.append(prices[i])
        
        # Veritabanına kaydet
        save_stock_data(symbol, dates, prices, support_levels, resistance_levels)
        print(f"Veri kaydedildi: {symbol}")
        
    except Exception as e:
        print(f"Hata: {symbol} için veri çekilemedi: {e}")

def fetch_and_save_news(symbol):
    news = get_google_news(symbol)
    save_news_to_db(symbol, news)

def main():
    symbols = [
        "THYAO.IS", "GARAN.IS", "AKBNK.IS", "YKBNK.IS", "EREGL.IS",
        "ASELS.IS", "KCHOL.IS", "SAHOL.IS", "TUPRS.IS", "FROTO.IS"
    ]
    with app.app_context():
        for symbol in symbols:
            fetch_stock_data(symbol)  # Fiyatları kaydet
            fetch_and_save_news(symbol)  # Haberleri kaydet

if __name__ == "__main__":
    main() 