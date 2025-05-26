from datetime import datetime, timedelta
from urllib.parse import quote_plus
import feedparser
import json
import time
import random
import os
from pathlib import Path

# Cache configuration
CACHE_DIR = Path("cache")
CACHE_FILE = CACHE_DIR / "news_cache.json"
CACHE_DURATION = 600  # 10 minutes

# User-Agent list for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]

# BIST 100 symbols (current and non-repeating complete list)
bist100_symbols = [
    "AEFES", "AGHOL", "AKBNK", "AKSEN", "ALARK", "ALBRK", "ARCLK", "ASELS", "ASTOR", "ASUZU", "BIMAS", "BIOEN", "BRSAN", "BUCIM", "CCOLA", "CIMSA", "DOAS", "ECILC", "EGEEN", "EKGYO", "ENJSA", "ENKAI", "EREGL", "EUPWR", "FROTO", "GARAN", "GESAN", "GUBRF", "GWIND", "HALKB", "HEKTS", "ISCTR", "ISDMR", "KARSN", "KCHOL", "KMPUR", "KONTR", "KORDS", "KOZAA", "KOZAL", "KRDMD", "MAVI", "MGROS", "ODAS", "OTKAR", "OYAKC", "PENTA", "PETKM", "PGSUS", "QUAGR", "SAHOL", "SASA", "SELEC", "SISE", "SKBNK", "SMRTG", "SOKM", "TAVHL", "TCELL", "THYAO", "TKFEN", "TKNSA", "TOASO", "TRGYO", "TSKB", "TTKOM", "TTRAK", "TUPRS", "TURSG", "ULKER", "VAKBN", "VESTL", "YKBNK", "ZOREN", "BRISA", "CANTE", "CWENE", "DOHOL", "EKSUN", "ESEN", "EUHOL", "FENER", "FONET", "GLYHO", "GOODY", "GSDHO", "ICBC", "IPEKE", "ISGYO", "IZMDC", "KATMR", "KRVGD", "KZBGY", "LIDFA", "LINK", "LOGO", "MARTI", "OYYAT", "PARSN", "PETUN", "PRKME", "RYSAS", "SANEL", "SILVR", "TATGD", "TMSN", "TRILC", "TUKAS", "YEOTK"
]

def get_random_user_agent():
    """Return a random User-Agent from the list."""
    return random.choice(USER_AGENTS)

def get_cached_news(symbol):
    """Get cached news for a symbol if available and not expired."""
    if not CACHE_FILE.exists():
        return None
    
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        
        if symbol in cache:
            data = cache[symbol]
            if time.time() - data['timestamp'] < CACHE_DURATION:
                return data['news']
    except (json.JSONDecodeError, KeyError, FileNotFoundError):
        pass
    return None

def set_cached_news(symbol, news):
    """Cache news for a symbol with current timestamp."""
    CACHE_DIR.mkdir(exist_ok=True)
    
    cache = {}
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except json.JSONDecodeError:
            pass
    
    cache[symbol] = {
        'news': news,
        'timestamp': time.time()
    }
    
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def scrape_bist_news(symbol=None):
    """Scrape BIST news with rate limiting and caching."""
    all_news = []
    seen_links = set()
    one_week_ago = datetime.now() - timedelta(days=7)
    symbols = [symbol] if symbol else bist100_symbols
    
    for sym in symbols:
        # Check cache first
        cached_news = get_cached_news(sym)
        if cached_news:
            all_news.extend(cached_news)
            continue
        
        # Add random delay between requests
        time.sleep(random.uniform(1, 3))
        
        query = f'"{sym}" hisse'
        query_encoded = quote_plus(query)
        rss_url = f"https://news.google.com/rss/search?q={query_encoded}&hl=tr&gl=TR&ceid=TR:tr"
        
        # Set random User-Agent
        headers = {'User-Agent': get_random_user_agent()}
        feed = feedparser.parse(rss_url, request_headers=headers)
        
        symbol_news = []
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed') or entry.published_parsed is None:
                continue
                
            published_dt = datetime(*entry.published_parsed[:6])
            if published_dt < one_week_ago:
                continue
                
            title = entry.title
            link = entry.link
            source = entry.get('source', {}).get('title', 'Google News')
            published = entry.get('published', '')
            
            if link in seen_links:
                continue
                
            seen_links.add(link)
            news_item = {
                'title': title,
                'source': source,
                'time': published,
                'formatted_time': published,
                'link': link,
                'symbol': sym
            }
            symbol_news.append(news_item)
            all_news.append(news_item)
        
        # Cache the news for this symbol
        if symbol_news:
            set_cached_news(sym, symbol_news)
    
    return all_news

if __name__ == "__main__":
    symbol = input("Hisse sembolü girin (veya tümü için boş bırakın): ").strip().upper()
    news = scrape_bist_news(symbol if symbol else None)
    print(json.dumps(news, ensure_ascii=False, indent=2)) 