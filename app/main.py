from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services.fetcher import fetch_stock_data
from app.services.predictor import run_prediction_analysis

app = FastAPI()

# CORS ayarlarını güncelle
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tüm kaynaklara izin ver
    allow_credentials=True,
    allow_methods=["*"],  # Tüm HTTP metodlarına izin ver (GET, POST, OPTIONS, vb.)
    allow_headers=["*"],  # Tüm headerlara izin ver
    expose_headers=["*"]  # Tüm headerları dışarıya aç
)

@app.get("/predict/{symbol}")
@app.post("/predict/{symbol}")
async def predict(symbol: str):
    data = fetch_stock_data(symbol)
    result = run_prediction_analysis(symbol)
    return result 