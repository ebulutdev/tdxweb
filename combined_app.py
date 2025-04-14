from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import yfinance as yf
from datetime import datetime
import logging
from typing import Dict, Any, Optional
from cachetools import TTLCache
import os
import sys

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

# CORS configuration - update with your Render.com domain when deployed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your actual domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files from root directory
app.mount("/static", StaticFiles(directory="."), name="static")

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
    """Try different symbol formats"""
    alternatives = [
        base_symbol,
        f"{base_symbol}.IS",
        f"{base_symbol}.IS.E",
        f"{base_symbol}.E"
    ]
    
    for symbol in alternatives:
        try:
            logger.info(f"Trying alternative: {symbol}")
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            
            if not df.empty:
                prices = df['Close'].tolist()
                timestamps = [int(t.timestamp() * 1000) for t in df.index]
                volumes = df['Volume'].tolist()
                
                if not prices or len(prices) < 2:
                    logger.warning(f"Insufficient data points: {symbol}")
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
            logger.warning(f"Symbol attempt failed ({symbol}): {str(e)}")
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
                    "detail": f"Stock data not found: {symbol} (All alternatives tried)"
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
                "detail": f"Server error: {str(e)}"
            }
        )

# Chatbot endpoint
@app.get("/chatbot")
def get_chatbot_response(symbol: str = Query(...), detay: str = Query("false")):
    try:
        detay_bool = detay.lower() == "true"
        logger.info(f"Chatbot request received: symbol={symbol}, detay={detay_bool}")
        
        if not symbol.upper().endswith(".IS"):
            symbol = symbol + ".IS"
            logger.info(f"Symbol corrected to: {symbol}")
        
        logger.info("Calling chatbot_response function...")
        response = chatbot_response(symbol, detay_bool)
        logger.info(f"Chatbot response received: {response[:100]}...")  # Log first 100 chars
        
        if not response:
            logger.error("Empty response from chatbot")
            raise HTTPException(status_code=500, detail="Chatbot yanıt vermedi")
            
        return {"response": response}
        
    except Exception as e:
        logger.error(f"Error in chatbot endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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