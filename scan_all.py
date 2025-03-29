import pandas as pd
from predict import predict_latest  # predict.py içinden fonksiyonu kullanıyoruz
from symbols_bist import symbols    # sembolleri ayrı bir dosyada tutacağız

def bulk_predict(symbols):
    results = []
    for symbol in symbols:
        print(f"🔍 {symbol} analiz ediliyor...")
        try:
            result = predict_latest(symbol, return_price=True)
            if result:
                prediction, price = result
                results.append({
                    "Hisse": symbol,
                    "Tahmin": "YÜKSELİR 📈" if prediction == 1 else "DÜŞER 📉",
                    "Fiyat": price
                })
        except Exception as e:
            print(f"⚠️ {symbol} için hata oluştu: {e}")
    return pd.DataFrame(results)

if __name__ == "__main__":
    from symbols_bist import symbols  # sembolleri al
    df = bulk_predict(symbols)
    df.to_csv("data/tum_tahminler.csv", index=False)
    print("\n✅ Tahminler 'data/tum_tahminler.csv' dosyasına kaydedildi.")
