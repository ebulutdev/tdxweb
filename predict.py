import pandas as pd
import os
import requests
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import matplotlib.pyplot as plt

INPUT_FILE = os.path.join("data", "processed_data.csv")
MODEL_FILE = os.path.join("models", "model.pkl")

def train_model():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Veri dosyası bulunamadı: {INPUT_FILE}")
        return

    df = pd.read_csv(INPUT_FILE)
    X = df[["close", "ma_5", "ma_10", "rsi"]]
    y = df["target"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("📋 Model Performansı:\n", classification_report(y_test, y_pred))

    os.makedirs("models", exist_ok=True)
    joblib.dump(model, MODEL_FILE)
    print("✅ Model kaydedildi.")

def show_graph(df, prediction, symbol):
    plt.figure(figsize=(12, 6))
    plt.plot(df.index[-30:], df["close"].tail(30), label="Close", linewidth=2)
    plt.plot(df.index[-30:], df["ma_5"].tail(30), label="MA 5", linestyle="--")
    plt.plot(df.index[-30:], df["ma_10"].tail(30), label="MA 10", linestyle="--")
    plt.title(f"{symbol} Tahmini: {'YÜKSELİR' if prediction == 1 else 'DÜŞER'}", fontsize=14)
    plt.xlabel("Zaman")
    plt.ylabel("Fiyat")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def analyze_stock(df, prediction):
    current_price = df["close"].iloc[-1]
    ma5 = df["ma_5"].iloc[-1]
    ma10 = df["ma_10"].iloc[-1]
    rsi = df["rsi"].iloc[-1]

    support = round(df["close"].rolling(window=10).min().iloc[-1], 2)
    resistance = round(df["close"].rolling(window=10).max().iloc[-1], 2)

    risk = round(((current_price - support) / current_price) * 100, 2)
    reward = round(((resistance - current_price) / current_price) * 100, 2)

    print(f"\n📊 Mevcut Fiyat: ${current_price:.2f}")
    print(f"📈 MA5: {ma5:.2f}, MA10: {ma10:.2f}")
    print(f"📉 RSI: {rsi:.2f}")
    print(f"📌 Destek: {support}, Direnç: {resistance}")
    print(f"📈 Kar Potansiyeli: %{reward}, 📉 Zarar Riski: %{risk}")

    # Detaylı Senaryo
    yorum = []
    yorum.append(f"💡 Hisse şu anda {current_price}$ seviyesinde işlem görüyor.")

    if rsi < 30:
        yorum.append("🧠 RSI aşırı satımda, teknik olarak tepki alımı gelebilir.")
    elif rsi > 70:
        yorum.append("⚠️ RSI aşırı alımda, düzeltme riski var.")

    yorum.append(f"🔍 İlk destek {support} seviyesi. Fiyat buraya yaklaşırsa dikkat edilmeli.")
    yorum.append(f"Eğer bu seviye altına sarkarsa zarar riski artar. Stop-loss kullanılmalı (%{risk} risk).")
    yorum.append(f"Direnç noktası {resistance}. Bu seviye aşılırsa yukarı yönlü ivme artabilir (hedef: %{reward} kar).")

    if prediction == 1:
        yorum.append("📢 Tahmin: YÜKSELİŞ bekleniyor. Ancak destek-direnç dikkate alınmalı.")
    else:
        yorum.append("📢 Tahmin: DÜŞÜŞ bekleniyor. Kısa vadede temkinli olunmalı.")

    print("\n".join(yorum))

def predict_latest(symbol):
    API_KEY = "5NQ4E2WFDZKIPREV"
    INTERVAL = "1min"
    URL = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={INTERVAL}&apikey={API_KEY}&outputsize=compact"

    response = requests.get(URL)
    data = response.json()

    if "Time Series (1min)" not in data:
        print("❌ Veri alınamadı.")
        return

    df = pd.DataFrame(data["Time Series (1min)"]).T
    df.columns = ["open", "high", "low", "close", "volume"]
    df = df.astype(float).sort_index()

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

    analyze_stock(df, prediction)
    show_graph(df, prediction, symbol)

# Ana Program
if __name__ == "__main__":
    print("📥 Model eğitiliyor...")
    train_model()

    symbol = input("🔍 Hisse Sembolü (örn: AAPL, MSFT, TSLA): ").upper()
    print(f"\n📡 {symbol} analiz ediliyor...")
    predict_latest(symbol)
    print("\n✅ İşlem tamamlandı.")
