import pandas as pd
import os

INPUT_FILE = os.path.join("data", "stock_data.csv")
OUTPUT_FILE = os.path.join("data", "processed_data.csv")

def calculate_indicators(df):
    # Hareketli ortalama (MA)
    df['ma_5'] = df['close'].rolling(window=5).mean()
    df['ma_10'] = df['close'].rolling(window=10).mean()
    
    # RSI hesapla
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    return df

def add_target(df):
    # 5 adım sonra fiyat daha yüksek mi?
    df['future_close'] = df['close'].shift(-5)
    df['target'] = (df['future_close'] > df['close']).astype(int)
    return df

def process_data():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Girdi dosyası bulunamadı: {INPUT_FILE}")
        return

    df = pd.read_csv(INPUT_FILE, index_col='timestamp')
    df = calculate_indicators(df)
    df = add_target(df)
    df.dropna(inplace=True)
    df.to_csv(OUTPUT_FILE)
    print(f"✅ Veriler analiz edildi ve kaydedildi: {OUTPUT_FILE}")

if __name__ == "__main__":
    print("📊 Teknik göstergeler hesaplanıyor...")
    process_data()
