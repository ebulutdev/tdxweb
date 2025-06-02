import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

KEYWORDS = {
    "jeopolitik": ["savaş", "çatışma", "darbe", "yaptırım", "gerilim", "işgal", "füze", "ambargo"],
    "kriz": ["kriz", "çöküş", "iflas", "resesyon", "tarihî düşüş", "panik", "likidite krizi"],
    "merkez_bankası": ["faiz kararı", "artırımı", "indirimi", "TCMB", "Fed", "şahin", "güvercin", "PPK"],
    "veri": ["enflasyon", "TÜFE", "işsizlik", "PMI", "beklentinin üzerinde", "daralma", "büyüme"],
    "afet": ["deprem", "şiddetinde", "felaket", "salgın", "pandemi", "karantina", "can kaybı"]
}

EFFECTS = {
    "jeopolitik": "📉 Borsalar ↓, 📈 Dolar/Altın ↑",
    "kriz": "📉 Borsalar ↓, 📈 Dolar/Faiz ↑",
    "merkez_bankası": "Faiz artışı: 📉 BIST, 📈 TL ve Faiz; Faiz indirimi: 📈 BIST, 📉 TL ve Faiz",
    "veri": "Pozitif: 📈 BIST, 📉 USD/TRY; Negatif: 📉 BIST, 📈 USD/TRY",
    "afet": "📉 Borsalar ↓, 📈 Dolar/Altın/Faiz ↑"
}

# Haber öncelik puanları
PRIORITY_SCORES = {
    "jeopolitik": 5,  # En yüksek öncelik
    "kriz": 5,
    "merkez_bankası": 4,
    "veri": 3,
    "afet": 4
}

def classify_news(text):
    for category, words in KEYWORDS.items():
        for word in words:
            if re.search(rf"\b{word}\b", text, re.IGNORECASE):
                return category
    return None

def calculate_priority(news_item):
    base_score = PRIORITY_SCORES.get(news_item["category"], 0)
    
    # Başlık uzunluğuna göre ek puan (daha detaylı haberler genelde daha önemlidir)
    title_length = len(news_item["title"])
    if title_length > 100:
        base_score += 1
    
    # Özel kelimelere göre ek puan
    critical_words = ["acil", "önemli", "kritik", "tarihi", "ilk", "son"]
    for word in critical_words:
        if word in news_item["title"].lower():
            base_score += 1
    
    return base_score

def scrape_and_analyze():
    url = "https://www.bloomberght.com/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    news_list = []
    
    for item in soup.select(".widget-news-list__headline a"):
        title = item.get_text(strip=True)
        link = item["href"]
        category = classify_news(title)
        
        if category:
            news_item = {
                "title": title,
                "link": link,
                "category": category,
                "effect": EFFECTS[category],
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            news_item["priority"] = calculate_priority(news_item)
            news_list.append(news_item)
    
    # Öncelik puanına göre sırala ve en yüksek puanlı haberi döndür
    if news_list:
        news_list.sort(key=lambda x: x["priority"], reverse=True)
        return [news_list[0]]  # Sadece en önemli haberi döndür
    return []

if __name__ == "__main__":
    analyzer = NewsAnalyzer()
    top_news = analyzer.scrape_and_analyze()
    for news in top_news:
        print(f"Title: {news['title']}")
        print(f"Category: {news['classification']['category']}")
        print(f"Priority Score: {news['priority']:.2f}")
        print(f"Market Effects: {news['effects']['description']}")
        print("---") 