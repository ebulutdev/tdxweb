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
def get_response(symbol: str = Query(...), detay: bool = False):
    return {"response": chatbot_response(symbol, detay=detay)}
