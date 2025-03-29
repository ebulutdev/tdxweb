import pandas as pd
import os
import joblib
import matplotlib.pyplot as plt

MODEL_FILE = os.path.join("models", "model.pkl")

def run_prediction_analysis(symbol: str):
    path = os.path.join("data", f"{symbol}_data.csv")
    if not os.path.exists(path):
        return {"error": f"{symbol} için veri dosyası bulunamadı."}

    df = pd.read_csv(path, index_col="timestamp")
    df["ma_5"] = df["close"].rolling(window=5).mean()
    df["ma_10"] = df["close"].rolling(window=10).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    df.dropna(inplace=True)
    latest = df[["close", "ma_5", "ma_10", "rsi"]].iloc[-1].values.reshape(1, -1)

    model = joblib.load(MODEL_FILE)
    prediction = model.predict(latest)[0]

    current_price = df["close"].iloc[-1]
    ma5 = df["ma_5"].iloc[-1]
    ma10 = df["ma_10"].iloc[-1]
    rsi = df["rsi"].iloc[-1]

    support = df["close"].rolling(window=10).min().iloc[-1]
    resistance = df["close"].rolling(window=10).max().iloc[-1]

    risk = ((current_price - support) / current_price) * 100
    reward = ((resistance - current_price) / current_price) * 100

    # Grafik kaydet
    fig_path = os.path.join("data", f"{symbol}_chart.png")
    plt.figure(figsize=(10, 5))
    plt.plot(df["close"].tail(30), label="Close", linewidth=2)
    plt.plot(df["ma_5"].tail(30), label="MA5", linestyle="--")
    plt.plot(df["ma_10"].tail(30), label="MA10", linestyle="--")
    plt.title(f"{symbol} Tahmini: {'📈 YÜKSELİR' if prediction == 1 else '📉 DÜŞER'}")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(fig_path)
    plt.close()

    return {
        "symbol": symbol,
        "mevcut_fiyat": round(current_price, 2),
        "ma_5": round(ma5, 2),
        "ma_10": round(ma10, 2),
        "rsi": round(rsi, 2),
        "destek": round(support, 2),
        "direnc": round(resistance, 2),
        "risk_orani": f"%{risk:.6f}",
        "kar_orani": f"%{reward:.6f}",
        "tahmin": "📈 YÜKSELİR" if prediction == 1 else "📉 DÜŞER",
        "grafik": f"/data/{symbol}_chart.png"
    }
