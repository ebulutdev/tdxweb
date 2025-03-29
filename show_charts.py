import pandas as pd
from predict import predict_latest

# CSV'den tahminleri oku
df = pd.read_csv("data/tum_tahminler.csv")

# Sadece YÜKSELİR 📈 tahmini yapılan hisseleri filtrele
rising_stocks = df[df["Tahmin"].str.contains("YÜKSELİR")]

# Her hisse için grafik çiz
for symbol in rising_stocks["Hisse"]:
    print(f"\n📊 Grafik çiziliyor: {symbol}")
    predict_latest(symbol, return_price=False)
