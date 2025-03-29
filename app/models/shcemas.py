from pydantic import BaseModel

class PredictionRequest(BaseModel):
    symbol: str

class PredictionResponse(BaseModel):
    symbol: str
    current_price: float
    ma5: float
    ma10: float
    rsi: float
    support: float
    resistance: float
    prediction: str
    risk: float
    reward: float
    advice: str
