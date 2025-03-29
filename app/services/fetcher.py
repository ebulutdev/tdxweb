import os
import requests
import pandas as pd
from pandas import DataFrame

API_KEY = "5NQ4E2WFDZKIPREV"  # Alpha Vantage key'in
INTERVAL = "1min"

def fetch_stock_data(symbol: str) -> pd.DataFrame:
    url = (
        f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY"
        f"&symbol={symbol}&interval={INTERVAL}&apikey={API_KEY}&outputsize=compact"
    )
    response = requests.get(url)
    data = response.json()

    if "Time Series (1min)" not in data:
        print("❌ Veri alınamadı. API limiti dolmuş olabilir.")
        return pd.DataFrame()

    df = pd.DataFrame(data["Time Series (1min)"]).T
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index.name = "timestamp"
    df = df.astype(float)
    df = df.sort_index()

    # CSV olarak kaydet
    os.makedirs("data", exist_ok=True)
    output_file = os.path.join("data", f"{symbol.lower()}_data.csv")
    df.to_csv(output_file)

    print(f"✅ {symbol.upper()} verisi çekildi ve '{output_file}' dosyasına kaydedildi.")

    return df
