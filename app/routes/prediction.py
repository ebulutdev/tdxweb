from fastapi import APIRouter
from app.services.fetcher import fetch_stock_data
from app.services.predictor import run_prediction_analysis

router = APIRouter()

@router.get("/predict/{symbol}")
async def predict(symbol: str):
    data = fetch_stock_data(symbol)
    result = run_prediction_analysis(symbol)
    return result
