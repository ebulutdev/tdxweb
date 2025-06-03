import yfinance as yf
import datetime
from django.core.cache import cache
from yfinance.data import YFRateLimitError
from curl_cffi import requests

# Gelişmiş cache ve rate limit mekanizması:
# - Aynı hisseye kısa sürede tekrar istek gelirse cache'den döner
# - Aynı kullanıcıdan çok sık istek gelirse uyarı döner
# - Rate limit riski azaltılır

session = requests.Session(impersonate="chrome")
MIN_FETCH_INTERVAL = 120  # 2 dakika

def get_stock_data(symbol, user_ip=None):
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
        'FROTO.IS': 'Ford Otosan',
    }
    cache_key = f"stock_data_{symbol}"
    time_key = f"stock_data_time_{symbol}"
    user_key = f"user_req_count_{user_ip}" if user_ip else None

    # Kullanıcı bazlı rate limit (1 dakikada 5 istekten fazla olmasın)
    if user_ip:
        req_count = cache.get(user_key, 0)
        if req_count >= 5:
            return {
                'symbol': symbol,
                'company': symbol_to_company.get(symbol, ''),
                'price': '-',
                'change': '-',
                'volume': '-',
                'time': '-',
                'error': 'Çok sık istek gönderdiniz. Lütfen biraz bekleyin.'
            }
        cache.set(user_key, req_count + 1, timeout=60)

    # Son çekim zamanı kontrolü
    last_fetch = cache.get(time_key)
    now = datetime.datetime.now().timestamp()
    if last_fetch and now - last_fetch < MIN_FETCH_INTERVAL:
        data = cache.get(cache_key)
        if data:
            return data

    try:
        stock = yf.Ticker(symbol, session=session)
        hist = stock.history(period="5d")
        if hist.empty:
            return {
                'symbol': symbol,
                'company': symbol_to_company.get(symbol, ''),
                'price': 0,
                'change': 0,
                'volume': '-',
                'time': '-',
                'error': 'Veri bulunamadı.'
            }
        latest = hist.iloc[-1]
        price = float(latest['Close'])
        prev_close = float(hist.iloc[-2]['Close']) if len(hist) > 1 else price
        change = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
        volume = latest['Volume']
        volume_str = f"{volume/1_000_000:.1f}M" if volume >= 1_000_000 else f"{volume/1_000:.1f}K" if volume >= 1_000 else str(volume)
        time_str = latest.name.strftime("%d.%m")
        data = {
            'symbol': symbol,
            'company': symbol_to_company.get(symbol, ''),
            'price': price,
            'change': change,
            'volume': volume_str,
            'time': time_str,
        }
        cache.set(cache_key, data, 300)
        cache.set(time_key, now, 300)
        return data
    except YFRateLimitError:
        return {
            'symbol': symbol,
            'company': symbol_to_company.get(symbol, ''),
            'price': '-',
            'change': '-',
            'volume': '-',
            'time': '-',
            'error': 'Çok fazla istek gönderdiniz. Lütfen birkaç dakika sonra tekrar deneyin.'
        }
    except Exception as e:
        return {
            'symbol': symbol,
            'company': symbol_to_company.get(symbol, ''),
            'price': '-',
            'change': '-',
            'volume': '-',
            'time': '-',
            'error': f'Hata: {str(e)}'
        } 