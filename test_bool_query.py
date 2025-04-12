from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/test")
def test_bool_param(symbol: str = Query(...), detay: str = Query("false")):
    detay_flag = detay.lower() == "true"
    return JSONResponse({
        "symbol": symbol,
        "detay_param_gelen": detay,
        "detay_bool_olarak": detay_flag
    })
