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
    data, full_data = get_yahoo_data(symbol)

    if not data:
        return f"❌ Üzgünüm, {symbol.upper()} için analiz verisine ulaşamadım. Sembol hatalı olabilir ya da son 30 gün içinde yeterli işlem yapılmamış."

    response = f"""
🧠 Merhaba! İşte {symbol.upper()} hissesiyle ilgili analizim:

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
        trend = "📉 Son günlerde fiyatlarda bir düşüş gözlemleniyor. Bu durum düzeltme hareketi ya da negatif haber etkisi olabilir."
        if full_data['Close'].iloc[-1] > full_data['Close'].iloc[-3]:
            trend = "📈 Hisse son birkaç gündür yukarı yönlü toparlanma işaretleri gösteriyor. Bu kısa vadeli momentumun güçlendiğini gösterebilir."

        support = round(full_data['Close'][-10:].min(), 2)
        resistance = round(full_data['Close'][-10:].max(), 2)
        current = data['price']

        konum = ""
        strateji = ""

        if current < support * 1.03:
            konum = f"📉 Fiyat destek seviyesine oldukça yakın ({support} TL civarı)."
            strateji = (
                "💡 Bu seviyeler, genellikle tepki alımlarının geldiği bölgelerdir.\n"
                "🔎 Destek kırılırsa düşüş hızlanabilir, bu nedenle zarar durdur seviyeleri belirlenmeli.\n"
                "📥 Alım düşünülüyorsa, hacim artışı ve fiyat tepkisi mutlaka takip edilmelidir."
            )
        elif current > resistance * 0.97:
            konum = f"📈 Fiyat direnç seviyesine yaklaşmış durumda ({resistance} TL civarı)."
            strateji = (
                "💡 Bu bölge genellikle kar satışlarının geldiği yerdir.\n"
                "📤 Elinde hisse olanlar için kademeli kar realizasyonu düşünülebilir.\n"
                "🚀 Ancak direnç yukarı kırılırsa, yeni bir yükseliş dalgası başlayabilir."
            )
        else:
            konum = "🔄 Fiyat destek ve direnç arasında dengeli seyrediyor."
            strateji = (
                "📊 Bu durum yön belirsizliğine işaret eder.\n"
                "🔄 Kırılım yönü netleşene kadar dikkatli olunmalı.\n"
                "🛑 Destek altı kapanış veya direnç üstü kırılım takip edilmelidir."
            )

        response += f"""

🔍 <strong>Detaylı Teknik Bakış</strong>:
{trend}

📊 <strong>Destek / Direnç Seviyeleri</strong>:
🟦 Destek: {support} TL  
🟥 Direnç: {resistance} TL  

📌 <strong>Fiyatın Teknik Konumu:</strong>
{konum}

🧭 <strong>Yatırımcı İçin Öneri:</strong>
{strateji}

📌 Bu seviyeler yatırımcı psikolojisini yansıtır ve çoğu zaman fiyat bu bölgelerde yön değiştirir.
"""

    response += "\n\n💬 Genel Değerlendirme: Bu sadece teknik verilere dayalı bir yorumdur. Piyasa duyarlılığı, haber akışı ve şirketin temelleri gibi etkenler de karar vermede önemlidir. 📬"

    return response
