import sqlite3
import json
from datetime import datetime

DB_PATH = 'backend/stock_data.db'

def check_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT symbol, data, last_update FROM stock_data')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    print(f"Toplam kayıt sayısı: {len(rows)}")
    print("\nKayıtlar:")
    for row in rows:
        try:
            data = json.loads(row[1])
            print(f"\nSembol: {row[0]}")
            print(f"Son güncelleme: {row[2]}")
            print("Veri:")
            print(f"  - Fiyat sayısı: {len(data.get('prices', []))}")
            print(f"  - Tarih sayısı: {len(data.get('dates', []))}")
            print(f"  - İlk tarih: {data.get('dates', [''])[0]}")
            print(f"  - Son tarih: {data.get('dates', [''])[-1]}")
            print(f"  - İlk fiyat: {data.get('prices', [''])[0]}")
            print(f"  - Son fiyat: {data.get('prices', [''])[-1]}")
        except Exception as e:
            print(f"\nSembol: {row[0]}")
            print(f"Son güncelleme: {row[2]}")
            print(f"Veri: JSON parse hatası - {str(e)}")

if __name__ == "__main__":
    check_db() 