from datetime import datetime
import requests

FINNHUB_API_KEY = "cvt79bhr01qhup0umsv0cvt79bhr01qhup0umsvg"

def get_finnhub_data(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    response = requests.get(url)
    return response.json()

def chatbot_response(symbol):
    data = get_finnhub_data(symbol)

    if "c" not in data or data["c"] == 0:
        return "❌ Veri alınamadı. Sembol yanlış veya veri yok."

    response = f"""
📊 {symbol.upper()} Hisse Analizi:
🔹 Anlık Fiyat: {data['c']} TL
🔹 Açılış: {data['o']} TL
🔹 En Yüksek: {data['h']} TL
🔹 En Düşük: {data['l']} TL
🔹 Önceki Kapanış: {data['pc']} TL
🕒 {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
"""

    if data["c"] > data["pc"]:
        response += "🟢 Hisse yükseliyor."
    elif data["c"] < data["pc"]:
        response += "🔻 Hisse düşüşte."
    else:
        response += "⚖️ Hisse sabit."

    return response
