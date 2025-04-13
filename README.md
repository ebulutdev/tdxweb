# TDX Borsa Danışman Botu

Yapay zeka destekli borsa danışmanlığı ve gerçek zamanlı hisse senedi analizi sunan web uygulaması.

## Özellikler

- Gerçek zamanlı hisse senedi grafikleri
- Yapay zeka destekli analizler
- Kullanıcı dostu arayüz
- Mobil uyumlu tasarım

## Kurulum

### Backend (FastAPI)

1. Gerekli paketleri yükleyin:
   ```
   pip install -r requirements.txt
   ```

2. Backend servisini başlatın:
   ```
   python main.py
   ```
   veya
   ```
   uvicorn main:app --reload --port 8000
   ```

3. Backend servisi http://localhost:8000 adresinde çalışacaktır.

### Frontend

Frontend için herhangi bir kurulum gerekmez. `index.html` dosyasını bir web tarayıcısında açarak uygulamayı kullanabilirsiniz.

## Kullanım

1. Ana sayfada "TDX - The Beast Chart" bölümünde bir hisse senedi kodu girin (örn: THYAO)
2. Arama butonuna tıklayın veya Enter tuşuna basın
3. Grafik otomatik olarak güncellenecek ve hisse senedi verilerini gösterecektir
4. Farklı zaman aralıkları için timeframe butonlarını kullanabilirsiniz

## API Endpoint

- `/stock-data?symbol=SYMBOL`: Belirtilen hisse senedi için veri döndürür
  - Örnek: `http://localhost:8000/stock-data?symbol=THYAO`

## Geliştirme

Projeyi geliştirmek için:

1. Backend kodunu `main.py` dosyasında düzenleyin
2. Frontend kodunu `index.html`, `style.css` ve `script.js` dosyalarında düzenleyin
3. Değişiklikleri test edin

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır. 