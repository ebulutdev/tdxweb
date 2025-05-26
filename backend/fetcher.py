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
from pathlib import Path

GEMINI_API_KEY = "AIzaSyAQXzOVG-BP5-EGZl2ts9d6kp_n-2pvM_U"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = Path(BASE_DIR) / "cache"
CACHE_DURATION = 600  # 10 minutes for news cache
STOCK_CACHE_DURATION = 3600  # 1 hour for stock data cache

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
]

class RateLimiter:
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    async def acquire(self):
        now = time.time()
        # Remove old requests
        self.requests = [req_time for req_time in self.requests if now - req_time < self.time_window]
        
        if len(self.requests) >= self.max_requests:
            # Wait until we can make another request
            wait_time = self.requests[0] + self.time_window - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        self.requests.append(now)

class StockDataFetcher:
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)
        self.rate_limiter = RateLimiter(max_requests=5, time_window=60)  # 5 requests per minute
        
    def _get_cache_path(self, symbol: str) -> Path:
        return self.cache_dir / f"{symbol}.json"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        if not cache_path.exists():
            return False
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                last_update = datetime.fromisoformat(cached_data['last_update'])
                return datetime.now() - last_update < timedelta(seconds=STOCK_CACHE_DURATION)
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            return False
    
    def _save_to_cache(self, symbol: str, data: Dict):
        cache_path = self._get_cache_path(symbol)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump({
                'data': data,
                'last_update': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    async def fetch_stock_data(self, symbol: str, period: str = "1mo") -> Dict:
        """Fetch stock data with rate limiting and caching"""
        cache_path = self._get_cache_path(symbol)
        
        # Check cache first
        if self._is_cache_valid(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)['data']
        
        # Apply rate limiting
        await self.rate_limiter.acquire()
        
        # Add random delay between requests (1-3 seconds)
        await asyncio.sleep(random.uniform(1, 3))
        
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
            
            # Save to cache
            self._save_to_cache(symbol, data)
            
            return data
            
        except Exception as e:
            print(f"Error fetching data for {symbol}: {str(e)}")
            # If we have stale cache data, return it
            if cache_path.exists():
                try:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        return json.load(f)['data']
                except:
                    pass
            return None

    async def fetch_multiple_stocks(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch data for multiple stocks with rate limiting"""
        results = {}
        for symbol in symbols:
            # Add delay between different stocks
            if results:  # Skip delay for first stock
                await asyncio.sleep(random.uniform(2, 4))
            result = await self.fetch_stock_data(symbol)
            if result:
                results[symbol] = result
        return results

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
    """Fetch news with rate limiting and caching"""
    cache_path = CACHE_DIR / f"{symbol}_news.json"
    
    # Check cache first
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                if time.time() - cached_data['timestamp'] < CACHE_DURATION:
                    return cached_data['news']
        except (json.JSONDecodeError, KeyError):
            pass
    
    # Add random delay
    time.sleep(random.uniform(1, 3))
    
    query = f'"{symbol}" hisse borsa'
    query_encoded = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={query_encoded}&hl=tr&gl=TR&ceid=TR:tr"
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 429:  # Rate limit
                wait_time = 60 * (attempt + 1)  # Exponential backoff
                print(f"Rate limit hit! Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            elif response.status_code == 200:
                feed = feedparser.parse(response.text)
                news = []
                for entry in feed.entries[:count]:
                    news.append({
                        'title': entry.title,
                        'link': entry.link,
                        'published': entry.get('published', ''),
                        'source': entry.get('source', {}).get('title', 'Google News'),
                        'cache_date': datetime.now().strftime("%Y-%m-%d")
                    })
                
                # Save to cache
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'news': news,
                        'timestamp': time.time()
                    }, f, ensure_ascii=False, indent=2)
                
                return news
        except Exception as e:
            print(f"Error fetching news for {symbol}: {str(e)}")
            if attempt < 2:  # Don't wait on last attempt
                time.sleep(5)
    
    return []

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

if __name__ == "__main__":
    symbols = ["GARAN", "ASELS", "THYAO", "MIATK", "FROTO"]

    # Eğer hiç parametre verilmezse hem fiyat hem haber çek
    if len(sys.argv) == 1:
        # Fiyat verilerini çek
        fetcher = StockDataFetcher()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(fetcher.fetch_multiple_stocks(symbols))
        # Haber verilerini çek (sadece 3 hisse)
        fetch_all_news()
        print("Tüm fiyat ve haber verileri güncellendi.")
    elif len(sys.argv) >= 2:
        mode = sys.argv[1]
        if mode == "haber":
            if len(sys.argv) == 3 and sys.argv[2].lower() == "toplu":
                fetch_all_news()
            elif len(sys.argv) == 3:
                symbol = sys.argv[2]
                news = get_google_news(symbol)
                save_news_to_json(symbol, news)
            else:
                print("Kullanım: python fetcher.py haber [SYMBOL] veya python fetcher.py haber toplu")
        elif mode == "fiyat":
            if len(sys.argv) == 3 and sys.argv[2].lower() == "toplu":
                fetcher = StockDataFetcher()
                loop = asyncio.get_event_loop()
                loop.run_until_complete(fetcher.fetch_multiple_stocks(symbols))
            elif len(sys.argv) == 3:
                symbol = sys.argv[2]
                fetcher = StockDataFetcher()
                loop = asyncio.get_event_loop()
                loop.run_until_complete(fetcher.fetch_stock_data(symbol))
            else:
                print("Kullanım: python fetcher.py fiyat [SYMBOL] veya python fetcher.py fiyat toplu")
        else:
            print("Bilinmeyen mod:", mode) 