from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yfinance as yf
from datetime import datetime
import logging
from typing import Dict, Any, Optional
from cachetools import TTLCache
import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import chatbot function
from chatbot.chatbot_yfinance import chatbot_response

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache configuration (5 minutes TTL)
price_cache = TTLCache(maxsize=100, ttl=300)

app = FastAPI()

# CORS configuration for Render.com
origins = [
    "https://tdx-combined-service.onrender.com",
    "http://tdx-combined-service.onrender.com",
    "http://localhost:8001",
    "http://127.0.0.1:8001"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the current directory
current_dir = Path(__file__).parent.absolute()

# Serve static files
app.mount("/static", StaticFiles(directory=str(current_dir)), name="static")

# Error handling middleware
@app.middleware("http")
async def catch_exceptions_middleware(request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Request processing error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Server error occurred",
                "message": str(e)
            }
        )

def try_symbols(base_symbol: str, period: str) -> Optional[Dict[str, Any]]:
    """Try different symbol formats with proper error handling"""
    # Remove .IS suffix if present for Turkish stocks
    base_symbol = base_symbol.replace('.IS', '')
    
    # For Turkish stocks, try these variations
    alternatives = [
        base_symbol,  # Try without any suffix first
        f"{base_symbol}.IS",
        base_symbol.upper(),  # Try uppercase version
        f"{base_symbol.upper()}.IS",
        f"{base_symbol}.IS.E",  # Try with .IS.E suffix (sometimes used for Turkish stocks)
        f"{base_symbol}.E"  # Try with .E suffix
    ]
    
    for symbol in alternatives:
        try:
            logger.info(f"Trying symbol format: {symbol}")
            ticker = yf.Ticker(symbol)
            
            # Try to get historical data directly without checking info first
            df = ticker.history(period=period)
            
            if df.empty:
                logger.warning(f"Empty data frame for {symbol}")
                continue
                
            prices = df['Close'].tolist()
            timestamps = [int(t.timestamp() * 1000) for t in df.index]
            volumes = df['Volume'].tolist()
            
            if not prices or len(prices) < 2:
                logger.warning(f"Insufficient data points for {symbol}")
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
            logger.error(f"Error fetching data for {symbol}: {str(e)}")
            continue
            
    return None

# Stock data endpoint
@app.get("/stock-data")
async def get_stock_data(
    symbol: str = Query(..., description="Stock symbol"),
    period: str = Query("6mo", description="Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y)")
):
    try:
        cache_key = f"{symbol.upper()}:{period}"
        
        if cache_key in price_cache:
            logger.info(f"Data retrieved from cache: {cache_key}")
            return JSONResponse(content=price_cache[cache_key])

        logger.info(f"Fetching data: {symbol}")
        data = try_symbols(symbol.upper(), period)
        
        if not data:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "detail": f"Veri alınamadı: {symbol} (Tüm alternatifler denendi)"
                }
            )
        
        price_cache[cache_key] = data
        
        logger.info(f"Data successfully retrieved: {data['used_symbol']}")
        return JSONResponse(content=data)
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "detail": f"Sunucu hatası: {str(e)}"
            }
        )

# Chatbot endpoint
@app.get("/chatbot")
def get_chatbot_response(symbol: str = Query(...), detay: str = Query("false")):
    try:
        detay_bool = detay.lower() == "true"
        logger.info(f"Chatbot request received: symbol={symbol}, detay={detay_bool}")
        
        # Remove .IS suffix if present and normalize
        symbol = symbol.replace('.IS', '').upper()
        logger.info(f"Normalized symbol: {symbol}")
        
        # Try to get stock data first to validate the symbol
        stock_data = try_symbols(symbol, "30d")
        if not stock_data:
            logger.warning(f"No data found for symbol: {symbol}")
            return {"response": f"❌ Üzgünüm, {symbol} için analiz verisine ulaşamadım. Sembol hatalı olabilir ya da son 30 gün içinde işlem görmemiş olabilir."}
        
        logger.info("Calling chatbot_response function...")
        response = chatbot_response(symbol, detay_bool)
        logger.info(f"Chatbot response received: {response[:100]}...")
        
        if not response:
            logger.error("Empty response from chatbot")
            raise HTTPException(status_code=500, detail="Chatbot yanıt vermedi")
            
        return {"response": response}
        
    except Exception as e:
        logger.error(f"Error in chatbot endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chatbot hatası: {str(e)}")

# Root endpoint - serve the combined interface
@app.get("/")
async def read_root():
    return FileResponse("combined_interface.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    host = "0.0.0.0"  # Required for Render.com
    logger.info(f"Starting combined API service on {host}:{port}...")
    uvicorn.run(app, host=host, port=port) 