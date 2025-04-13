from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
from datetime import datetime
import logging
from typing import Dict, Any, Optional
from cachetools import TTLCache

# Loglama ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Önbellek oluştur (5 dakika TTL)
price_cache = TTLCache(maxsize=100, ttl=300)

app = FastAPI()

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def try_symbols(base_symbol: str, period: str) -> Optional[Dict[str, Any]]:
    """Farklı sembol formatlarını dene"""
    alternatives = [
        base_symbol,
        f"{base_symbol}.IS",
        f"{base_symbol}.IS.E",
        f"{base_symbol}.E"
    ]
    
    for symbol in alternatives:
        try:
            logger.info(f"Alternatif deneniyor: {symbol}")
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            
            if not df.empty:
                prices = df['Close'].tolist()
                timestamps = [int(t.timestamp() * 1000) for t in df.index]
                volumes = df['Volume'].tolist()
                
                if not prices or len(prices) < 2:
                    logger.warning(f"Yetersiz veri noktası: {symbol}")
                    continue
                    
                return {
                    "prices": prices,
                    "timestamps": timestamps,
                    "volume": sum(volumes),
                    "current": prices[-1],
                    "close": prices[0],
                    "change": round(((prices[-1] - prices[0]) / prices[0]) * 100, 2),
                    "last_updated": datetime.now().isoformat(),
                    "used_symbol": symbol  # Hangi sembolün çalıştığını bildir
                }
        except Exception as e:
            logger.warning(f"Sembol denemesi başarısız ({symbol}): {str(e)}")
            continue
            
    return None

@app.get("/stock-data")
def get_stock_data(
    symbol: str = Query(..., description="Hisse senedi sembolü"),
    period: str = Query("6mo", description="Zaman aralığı (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y)")
):
    try:
        # Cache key oluştur (temel sembol ile)
        cache_key = f"{symbol.upper()}:{period}"
        
        # Önbellekte veri var mı kontrol et
        if cache_key in price_cache:
            logger.info(f"Veri önbellekten alındı: {cache_key}")
            return price_cache[cache_key]

        # Farklı sembol formatlarını dene
        logger.info(f"Veri çekiliyor: {symbol}")
        data = try_symbols(symbol.upper(), period)
        
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Hisse senedi verisi bulunamadı: {symbol} (Tüm alternatifler denendi)"
            )
        
        # Veriyi önbelleğe kaydet
        price_cache[cache_key] = data
        
        logger.info(f"Veri başarıyla alındı: {data['used_symbol']}")
        return data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sunucu hatası: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "Hisse Senedi API'sine Hoş Geldiniz"}

if __name__ == "__main__":
    import uvicorn
    logger.info("API servisi başlatılıyor...")
    uvicorn.run(app, host="0.0.0.0", port=8000)