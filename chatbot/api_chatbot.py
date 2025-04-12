from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from .chatbot_yfinance import chatbot_response


app = FastAPI()

# CORS (Web'den erişim için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/chatbot")
def get_response(symbol: str = Query(...), detay: str = Query("false")):
    # Convert string "true"/"false" to boolean
    detay_bool = detay.lower() == "true"
    print(f"API isteği: symbol={symbol}, detay={detay_bool}")  # Debug için log ekle
    
    # Ensure symbol has .IS suffix
    if not symbol.upper().endswith(".IS"):
        symbol = symbol + ".IS"
        print(f"Sembol düzeltildi: {symbol}")
    
    return {"response": chatbot_response(symbol, detay_bool)}