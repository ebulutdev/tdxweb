from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

# CORS ayarları - daha detaylı
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:3000",
    "capacitor://localhost",
    "http://localhost:8100",
    "http://localhost:8101",
    "http://192.168.1.*",
    "*"  # Geliştirme aşamasında tüm originlere izin ver
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Hata yakalama middleware'i
@app.middleware("http")
async def catch_exceptions_middleware(request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"İstek işlenirken hata oluştu: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Sunucu hatası oluştu",
                "message": str(e)
            }
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
                    "success": True,
                    "prices": prices,
                    "timestamps": timestamps,
                    "volume": sum(volumes),
                    "current": prices[-1],
                    "close": prices[0],
                    "change": round(((prices[-1] - prices[0]) / prices[0]) * 100, 2),
                    "last_updated": datetime.now().isoformat(),
                    "used_symbol": symbol
                }
        except Exception as e:
            logger.warning(f"Sembol denemesi başarısız ({symbol}): {str(e)}")
            continue
            
    return None

@app.get("/stock-data")
async def get_stock_data(
    symbol: str = Query(..., description="Hisse senedi sembolü"),
    period: str = Query("6mo", description="Zaman aralığı (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y)")
):
    try:
        # Cache key oluştur (temel sembol ile)
        cache_key = f"{symbol.upper()}:{period}"
        
        # Önbellekte veri var mı kontrol et
        if cache_key in price_cache:
            logger.info(f"Veri önbellekten alındı: {cache_key}")
            return JSONResponse(content=price_cache[cache_key])

        # Farklı sembol formatlarını dene
        logger.info(f"Veri çekiliyor: {symbol}")
        data = try_symbols(symbol.upper(), period)
        
        if not data:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "detail": f"Hisse senedi verisi bulunamadı: {symbol} (Tüm alternatifler denendi)"
                }
            )
        
        # Veriyi önbelleğe kaydet
        price_cache[cache_key] = data
        
        logger.info(f"Veri başarıyla alındı: {data['used_symbol']}")
        return JSONResponse(content=data)
        
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "detail": f"Sunucu hatası: {str(e)}"
            }
        )

@app.get("/")
async def read_root():
    return {"message": "Hisse Senedi API'sine Hoş Geldiniz", "status": "active"}

if __name__ == "__main__":
    import uvicorn
    logger.info("API servisi başlatılıyor...")
    uvicorn.run(app, host="0.0.0.0", port=8000)