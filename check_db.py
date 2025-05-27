import sqlite3
import json

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
            print(f"Veri: {data}")
        except:
            print(f"\nSembol: {row[0]}")
            print(f"Son güncelleme: {row[2]}")
            print("Veri: JSON parse hatası")

if __name__ == "__main__":
    check_db() 