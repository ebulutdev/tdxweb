from datetime import datetime
import yfinance as yf
import pandas as pd

def get_yahoo_data(symbol):
    stock = yf.Ticker(symbol)
    data = stock.history(period="30d", interval="1d")  # 30 günlük kapanış verisi

    if data.empty or len(data) < 10:
        return None, None

    data["SMA20"] = data["Close"].rolling(window=20).mean()
    data["RSI"] = compute_rsi(data["Close"])
    latest = data.iloc[-1]

    return {
        "price": round(latest["Close"], 2),
        "open": round(latest["Open"], 2),
        "high": round(latest["High"], 2),
        "low": round(latest["Low"], 2),
        "volume": int(latest["Volume"]),
        "sma20": round(latest["SMA20"], 2),
        "rsi": round(latest["RSI"], 2),
    }, data

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def chatbot_response(symbol, detay=False):
    print(f"Analiz isteği: {symbol}, Detay: {detay}")  # Debug için log ekle
    
    data, full_data = get_yahoo_data(symbol)

    if not data:
        print(f"Veri alınamadı: {symbol}")  # Debug için log ekle
        return f"❌ Üzgünüm, {symbol.upper()} için analiz verisine ulaşamadım. Sembol hatalı olabilir ya da son 30 gün içinde yeterli işlem yapılmamış."

    print(f"Veri alındı: {symbol}, Detay: {detay}")  # Debug için log ekle

    response = f"""
🧠 Merhaba! İşte {symbol.upper()} hissesiyle ilgili {'detaylı ' if detay else ''}analizim:

📊 Teknik Göstergeler:
🔸 Kapanış Fiyatı: {data['price']} TL
🔸 20 Günlük Hareketli Ortalama (SMA20): {data['sma20']} TL
🔸 RSI (Göreceli Güç Endeksi): {data['rsi']}
🔸 Günlük Hacim: {data['volume']} lot
🕒 Analiz Zamanı: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
"""

    if data['price'] > data['sma20']:
        response += "\n📈 Hisse, 20 günlük ortalamanın ÜZERİNDE işlem görüyor. Bu, teknik olarak yukarı yönlü bir ivmenin işareti olabilir. Trend pozitif görünüyor."
    else:
        response += "\n📉 Hisse, 20 günlük ortalamanın ALTINDA. Bu, yatırımcıların daha temkinli davrandığını veya düşüş trendinin devam ettiğini gösterebilir."

    if data['rsi'] > 70:
        response += "\n⚠️ RSI değeri 70'in üzerinde. Bu, hissenin aşırı alım bölgesine girmiş olabileceğini gösterir. Dikkatli olunmalı."
    elif data['rsi'] < 30:
        response += "\n📢 RSI değeri 30'un altında. Bu durum, hissenin aşırı satım bölgesinde olduğunu ve tepki alımı gelebileceğini gösterir."
    else:
        response += "\n✅ RSI değeri normal aralıkta. Ne aşırı alım ne de aşırı satım sinyali var. Nötr bölgede dengeli bir görünüm var."

    if detay:
        print("Detaylı analiz yapılıyor...")  # Debug için log ekle
        
        # Son 5 günlük trend analizi
        last_5_days = full_data.tail(5)
        price_change = ((last_5_days['Close'].iloc[-1] - last_5_days['Close'].iloc[0]) / last_5_days['Close'].iloc[0]) * 100
        volume_change = ((last_5_days['Volume'].iloc[-1] - last_5_days['Volume'].iloc[0]) / last_5_days['Volume'].iloc[0]) * 100

        trend = "📉 Son 5 günde fiyatlarda düşüş gözlemleniyor."
        if price_change > 0:
            trend = "📈 Son 5 günde fiyatlarda yükseliş gözlemleniyor."

        # Destek ve direnç seviyeleri
        support = round(full_data['Close'][-10:].min(), 2)
        resistance = round(full_data['Close'][-10:].max(), 2)
        current = data['price']

        # Fiyatın teknik konumu
        price_position = ""
        if current < support * 1.03:
            price_position = f"📉 Fiyat destek seviyesine yakın ({support} TL)"
        elif current > resistance * 0.97:
            price_position = f"📈 Fiyat direnç seviyesine yakın ({resistance} TL)"
        else:
            price_position = "🔄 Fiyat destek ve direnç arasında dengeli seyrediyor"

        # Hacim analizi
        volume_analysis = ""
        if volume_change > 20:
            volume_analysis = "📊 Hacimde önemli artış var, bu hareketin güçlü olduğunu gösterir."
        elif volume_change < -20:
            volume_analysis = "📉 Hacimde düşüş var, hareketin zayıf olabileceğini gösterir."
        else:
            volume_analysis = "📊 Hacim normal seviyelerde seyrediyor."

        response += f"""

🔍 <strong>Detaylı Teknik Analiz</strong>:

{trend}
{price_position}
{volume_analysis}

📊 <strong>Son 5 Günlük Değişim</strong>:
🔸 Fiyat Değişimi: %{round(price_change, 2)}
🔸 Hacim Değişimi: %{round(volume_change, 2)}

📌 <strong>Teknik Seviyeler</strong>:
🟦 Destek: {support} TL
🟥 Direnç: {resistance} TL

💡 <strong>Yatırımcı İçin Öneriler</strong>:
• Destek seviyesi: {support} TL - Bu seviye altına düşülürse dikkatli olunmalı
• Direnç seviyesi: {resistance} TL - Bu seviye üzerine çıkılırsa yeni hedefler belirlenebilir
• RSI: {data['rsi']} - {'Aşırı alım bölgesinde, dikkatli olunmalı' if data['rsi'] > 70 else 'Aşırı satım bölgesinde, fırsat olabilir' if data['rsi'] < 30 else 'Normal seviyelerde'}
• Hacim: {'Yükselen hacim trendi güçlendiriyor' if volume_change > 0 else 'Düşen hacim trendi zayıflatıyor'}

⚠️ <strong>Önemli Not</strong>:
Bu analiz sadece teknik verilere dayanmaktadır. Piyasa duyarlılığı, haber akışı ve şirketin temel göstergeleri gibi faktörler de değerlendirilmelidir.
"""
    else:
        print("Normal analiz yapılıyor...")  # Debug için log ekle

    response += "\n\n💬 Genel Değerlendirme: Bu sadece teknik verilere dayalı bir yorumdur. Piyasa duyarlılığı, haber akışı ve şirketin temelleri gibi etkenler de karar vermede önemlidir. 📬"

    return response
