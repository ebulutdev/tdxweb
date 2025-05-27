from flask import Flask, jsonify
import os
import json

app = Flask(__name__)
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

@app.route("/api/prices")
def get_prices():
    symbols = ["THYAO", "GARAN", "ASELS"]
    result = []
    for symbol in symbols:
        file_path = os.path.join(CACHE_DIR, f"{symbol}.json")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Otomatik olarak doğru veri formatını bul
                if "data" in data:
                    stock_data = data["data"]
                else:
                    stock_data = data
                prices = stock_data.get("prices", [])
                dates = stock_data.get("dates", [])
                # Calculate support and resistance levels
                support_levels = []
                resistance_levels = []
                for i in range(1, len(prices)-1):
                    if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                        support_levels.append(prices[i])
                    elif prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                        resistance_levels.append(prices[i])
                result.append({
                    "symbol": symbol,
                    "dates": dates,
                    "prices": prices,
                    "support_levels": support_levels,
                    "resistance_levels": resistance_levels
                })
    return jsonify(result)

if __name__ == "__main__":
    app.run(port=5000, debug=True) 