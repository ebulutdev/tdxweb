from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from config import Config
from models import db, User
from flask_migrate import Migrate
import requests
import yfinance as yf
import os
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
import scipy.ndimage
import time
from functools import lru_cache
import threading

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Rate limiting için global değişkenler
last_request_time = 0
request_lock = threading.Lock()
MIN_REQUEST_INTERVAL = 2  # saniye

def rate_limited_request():
    global last_request_time
    with request_lock:
        current_time = time.time()
        time_since_last_request = current_time - last_request_time
        
        if time_since_last_request < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - time_since_last_request
            time.sleep(sleep_time)
        
        last_request_time = time.time()

@lru_cache(maxsize=100)
def get_cached_stock_data(symbol):
    """
    Hisse senedi verilerini önbelleğe alır ve rate limiting uygular
    """
    try:
        rate_limited_request()
        stock = yf.Ticker(symbol)
        info = stock.info
        return info
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            raise Exception("Çok fazla istek gönderildi. Lütfen birkaç saniye bekleyin.")
        raise e
    except Exception as e:
        raise Exception(f"Veri alınamadı: {str(e)}")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class RegistrationForm(FlaskForm):
    username = StringField('Kullanıcı Adı', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Şifre', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Şifreyi Onayla', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Kayıt Ol')

class LoginForm(FlaskForm):
    username = StringField('Kullanıcı Adı', validators=[DataRequired()])
    password = PasswordField('Şifre', validators=[DataRequired()])
    submit = SubmitField('Giriş Yap')

@app.route('/')
def home():
    login_form = LoginForm()
    register_form = RegistrationForm()
    return render_template('home.html', login_form=login_form, register_form=register_form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter(
            (User.username == form.username.data) | (User.email == form.email.data)
        ).first()
        if existing_user:
            flash('Bu kullanıcı adı veya e-posta zaten kayıtlı.', 'danger')
            return redirect(url_for('home'))
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success')
        return redirect(url_for('home'))
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Başarıyla giriş yaptınız!', 'success')
            return redirect(url_for('home'))
        flash('Kullanıcı adı veya şifre hatalı!', 'danger')
    return redirect(url_for('home'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/grafik-analizi')
def grafik_analizi():
    return render_template('grafik_analizi.html')

# --- Gelişmiş Hisse Değerleme Fonksiyonları ---
def fk_degerleme(hisse_fiyati, net_kar, hisse_adedi, sektor_fk=None):
    eps = net_kar / hisse_adedi if hisse_adedi else 0
    fk = hisse_fiyati / eps if eps > 0 else None
    yorum = ""
    if fk is not None:
        if sektor_fk:
            fark = fk - sektor_fk
            if fk < sektor_fk:
                yorum = (
                    f"F/K oranı ({fk:.2f}), sektör ortalamasının ({sektor_fk}) altında. "
                    "Bu, hissenin görece ucuz olabileceğine işaret eder. "
                    "Ancak, düşük F/K her zaman alım fırsatı anlamına gelmez; şirketin büyüme potansiyeli, kârlılık sürdürülebilirliği ve geçmiş F/K trendi de dikkate alınmalıdır. "
                    f"Sektör ortalamasına göre {abs(fark):.2f} puan daha düşük. "
                    "Eğer şirketin kârı istikrarlı ve büyüme potansiyeli yüksekse, bu durum uzun vadeli yatırımcılar için cazip olabilir."
                )
            else:
                yorum = (
                    f"F/K oranı ({fk:.2f}), sektör ortalamasının ({sektor_fk}) üstünde. "
                    "Bu, hissenin görece pahalı olabileceğine işaret eder. "
                    "Yüksek F/K, piyasanın şirketin gelecekteki büyüme potansiyeline inandığını gösterebilir. "
                    f"Sektör ortalamasına göre {abs(fark):.2f} puan daha yüksek. "
                    "Ancak, şirketin kârlılığı ve büyüme beklentileri sektörün üzerinde ise bu durum makul olabilir. "
                    "Yatırım kararı verirken şirketin geçmiş F/K trendi ve sektör dinamikleri de göz önünde bulundurulmalıdır."
                )
        else:
            yorum = (
                f"F/K oranı {fk:.2f}. Sektör ortalaması ile karşılaştırmak gerekir. "
                "Düşük F/K genellikle ucuzluk, yüksek F/K ise pahalı olma sinyali verir; ancak tek başına yeterli değildir. "
                "Şirketin büyüme potansiyeli, kârlılık sürdürülebilirliği ve sektör trendleri de analiz edilmelidir."
            )
    else:
        yorum = "F/K oranı hesaplanamıyor (EPS negatif veya sıfır). Zarar eden şirketlerde F/K oranı anlamlı değildir."
    return fk, yorum

def pddd_degerleme(hisse_fiyati, ozkaynak, hisse_adedi, sektor_pddd=None):
    defter_degeri = ozkaynak / hisse_adedi if hisse_adedi else 0
    pddd = hisse_fiyati / defter_degeri if defter_degeri > 0 else None
    yorum = ""
    if pddd is not None:
        if sektor_pddd:
            fark = pddd - sektor_pddd
            if pddd < sektor_pddd:
                yorum = (
                    f"PD/DD oranı ({pddd:.2f}), sektör ortalamasının ({sektor_pddd}) altında. "
                    "Bu, hissenin defter değerine göre görece ucuz olduğunu gösterebilir. "
                    f"Sektör ortalamasına göre {abs(fark):.2f} puan daha düşük. "
                    "Ancak, düşük PD/DD her zaman alım fırsatı değildir; şirketin varlık kalitesi, kârlılık sürdürülebilirliği ve sektörün genel durumu da dikkate alınmalıdır. "
                    "Özellikle özsermaye kârlılığı (ROE) yüksek olan şirketlerde düşük PD/DD daha anlamlıdır."
                )
            else:
                yorum = (
                    f"PD/DD oranı ({pddd:.2f}), sektör ortalamasının ({sektor_pddd}) üstünde. "
                    "Bu, hissenin defter değerine göre görece pahalı olduğunu gösterebilir. "
                    f"Sektör ortalamasına göre {abs(fark):.2f} puan daha yüksek. "
                    "Yüksek PD/DD, piyasanın şirketin varlıklarını etkin kullandığına veya büyüme potansiyeline inandığını gösterebilir. "
                    "Ancak, şirketin özsermaye kârlılığı düşükse bu durum riskli olabilir. "
                    "Yatırım kararı verirken şirketin ROE'si ve sektör dinamikleri de göz önünde bulundurulmalıdır."
                )
        else:
            yorum = (
                f"PD/DD oranı {pddd:.2f}. Sektör ortalaması ile karşılaştırmak gerekir. "
                "Düşük PD/DD genellikle ucuzluk, yüksek PD/DD ise pahalı olma sinyali verir; ancak tek başına yeterli değildir. "
                "Şirketin varlık kalitesi, kârlılık sürdürülebilirliği ve sektör trendleri de analiz edilmelidir."
            )
    else:
        yorum = "PD/DD oranı hesaplanamıyor (defter değeri negatif veya sıfır)."
    return pddd, yorum

def dcf_degerleme(cash_flows, r, g, net_borc, hisse_adedi):
    NPV = sum(cf / ((1 + r) ** t) for t, cf in enumerate(cash_flows, start=1))
    terminal_value = cash_flows[-1] * (1 + g) / (r - g)
    PV_terminal = terminal_value / ((1 + r) ** len(cash_flows))
    toplam_firma_degeri = NPV + PV_terminal
    ozsermaye_degeri = toplam_firma_degeri - net_borc
    hisse_basi_deger = ozsermaye_degeri / hisse_adedi if hisse_adedi else 0
    return hisse_basi_deger

def roe_degerleme(net_kar, ozsermaye):
    return net_kar / ozsermaye if ozsermaye > 0 else None

@app.route('/hisse', methods=['GET', 'POST'])
@login_required
def hisse_fiyat_hesapla():
    results = None
    yorumlar = {}
    if request.method == 'POST':
        hisse_adi = request.form['hisse_adi']
        hisse_fiyati = float(request.form['hisse_fiyati'])
        odenmis_sermaye = float(request.form['odenmis_sermaye'])
        net_kar = float(request.form['net_kar'])
        ozsermaye = float(request.form['ozsermaye'])
        piyasa_degeri = float(request.form['piyasa_degeri'])
        fk_orani = float(request.form['fk_orani'])
        pddd_orani = float(request.form['pddd_orani'])
        sektor_fk = request.form.get('sektor_fk')
        sektor_pddd = request.form.get('sektor_pddd')
        sektor_fk = float(sektor_fk) if sektor_fk else None
        sektor_pddd = float(sektor_pddd) if sektor_pddd else None
        analiz_tipi = request.form.get('analiz_tipi', 'hisse_basi')

        # F/K ve PD/DD analizleri
        fk, fk_yorum = fk_degerleme(hisse_fiyati, net_kar, odenmis_sermaye, sektor_fk)
        pddd, pddd_yorum = pddd_degerleme(hisse_fiyati, ozsermaye, odenmis_sermaye, sektor_pddd)

        if analiz_tipi == 'hisse_basi':
            eps = net_kar / odenmis_sermaye if odenmis_sermaye else 0
            bvps = ozsermaye / odenmis_sermaye if odenmis_sermaye else 0
            fiyat_fk = eps * fk_orani
            fiyat_future_fk = eps * fk_orani * 1.27
            fiyat_pddd = bvps * pddd_orani
            fiyat_sermaye = piyasa_degeri / odenmis_sermaye if odenmis_sermaye else 0
            fiyat_potansiyel = (piyasa_degeri * 1.1) / odenmis_sermaye if odenmis_sermaye else 0
            fiyat_ozsermaye_kar = (eps * 2) * fk_orani
            analiz_tipi_aciklama = 'Hisse başı fiyat (EPS/BVPS bazlı)' 
        else:
            # Toplam şirket değeri bazlı hesaplama (örnek: diğer botun mantığı)
            fiyat_fk = (net_kar * fk_orani) / odenmis_sermaye if odenmis_sermaye else 0
            fiyat_future_fk = (net_kar * fk_orani * 1.27) / odenmis_sermaye if odenmis_sermaye else 0
            fiyat_pddd = (ozsermaye * pddd_orani) / odenmis_sermaye if odenmis_sermaye else 0
            fiyat_sermaye = piyasa_degeri / odenmis_sermaye if odenmis_sermaye else 0
            fiyat_potansiyel = (piyasa_degeri * 1.1) / odenmis_sermaye if odenmis_sermaye else 0
            fiyat_ozsermaye_kar = (net_kar * 2) / odenmis_sermaye if odenmis_sermaye else 0
            analiz_tipi_aciklama = 'Toplam şirket değeri bazlı (diğer bot mantığı)'

        fiyatlar = [
            fiyat_fk,
            fiyat_future_fk,
            fiyat_pddd,
            fiyat_sermaye,
            fiyat_potansiyel,
            fiyat_ozsermaye_kar
        ]
        ortalama_fiyat = sum(fiyatlar) / len(fiyatlar)
        prim_potansiyeli = ((ortalama_fiyat - hisse_fiyati) / hisse_fiyati) * 100

        yorumlar['fk'] = fk_yorum
        yorumlar['pddd'] = pddd_yorum

        # Koşullu profesyonel analiz ve yatırımcıya rehber açıklamalar
        negatif_yontemler = []
        cok_dusuk_yontemler = []
        yontem_etiketleri = [
            ('Cari F/K Oranına Göre', fiyat_fk),
            ("Future's F/K Oranına Göre", fiyat_future_fk),
            ('PD/DD Oranına Göre', fiyat_pddd),
            ('Ödenmiş Sermayeye Göre', fiyat_sermaye),
            ('Potansiyel Piyasa Değerine Göre', fiyat_potansiyel),
            ('Yıl Sonu Tahmini Özsermaye Karlılığına Göre', fiyat_ozsermaye_kar)
        ]
        for etiket, deger in yontem_etiketleri:
            if deger < 0:
                negatif_yontemler.append(etiket)
            elif deger < (0.2 * hisse_fiyati):
                cok_dusuk_yontemler.append(etiket)

        if net_kar < 0:
            yorumlar['Negatif ve Düşük Fiyatlar Neden Oluştu?'] = f'''
Net kârınız negatif olduğu için (ör. {net_kar:,.0f} TL), F/K oranına dayalı hesaplamalarda hisse başı fiyat negatif veya anlamlı olmayan bir değer alır. Bu nedenle "Cari F/K" ve "Future's F/K" gibi yöntemlerde negatif sonuçlar oluşur. Yıl Sonu Tahmini Özsermaye Karlılığına Göre hesaplamada da net kâr negatif olduğu için sonuç anlamlı değildir. PD/DD, Ödenmiş Sermaye ve Potansiyel Piyasa Değeri gibi yöntemler ise pozitif büyüklüklerle hesaplandığından pozitif değerler üretir. Bu durum, şirketin son dönemde zarar açıklamasının değerleme modellerini doğrudan etkilediğini gösterir.'''
        if negatif_yontemler or cok_dusuk_yontemler:
            aciklama = 'Ortalama fiyatın düşük çıkmasının ana nedeni: '
            if negatif_yontemler:
                aciklama += f"{', '.join(negatif_yontemler)} yöntem(ler)inde negatif değerler oluştu. "
            if cok_dusuk_yontemler:
                aciklama += f"{', '.join(cok_dusuk_yontemler)} yöntem(ler)inde ise fiyat, güncel fiyatın %20'sinden daha düşük hesaplandı. "
            aciklama += 'Bu tür yöntemler ortalamayı ciddi şekilde aşağıya çeker. Lütfen sonuçları değerlendirirken bu yöntemlerin etkisini göz önünde bulundurun.'
            yorumlar['Ortalama Fiyatın Çok Düşük Olmasının Sebebi'] = aciklama

        # Dinamik özet-sonuç
        anahtar_yorumlar = []
        if 'Negatif ve Düşük Fiyatlar Neden Oluştu?' in yorumlar:
            anahtar_yorumlar.append('Şirketin son dönemde zarar açıklaması, bazı değerleme yöntemlerinde negatif veya düşük fiyatlar oluşmasına neden olmuştur.')
        if 'Ortalama Fiyatın Çok Düşük Olmasının Sebebi' in yorumlar:
            anahtar_yorumlar.append('Ortalama fiyatın düşük çıkmasının ana nedenleri yukarıda açıklanmıştır. Bu tür yöntemlerin ortalamayı ciddi şekilde aşağıya çektiğini unutmayın.')
        anahtar_yorumlar.append('Yatırım kararı verirken, finansal oranların yanında şirketin iş modeli, yönetim kalitesi, sektörel konumu ve geleceğe yönelik stratejileri de mutlaka dikkate alınmalıdır. Analiz sonuçları, tek başına kesin yatırım tavsiyesi değildir; genel bir değerlendirme sunar.')
        yorumlar['Bu Sonuçlar Ne Anlama Geliyor?'] = ' '.join(anahtar_yorumlar)

        results = {
            'hisse_adi': hisse_adi,
            'fiyat_fk': f'{fiyat_fk:.2f}',
            'fiyat_future_fk': f'{fiyat_future_fk:.2f}',
            'fiyat_pddd': f'{fiyat_pddd:.2f}',
            'fiyat_sermaye': f'{fiyat_sermaye:.2f}',
            'fiyat_potansiyel': f'{fiyat_potansiyel:.2f}',
            'fiyat_ozsermaye_kar': f'{fiyat_ozsermaye_kar:.2f}',
            'ortalama_fiyat': f'{ortalama_fiyat:.2f}',
            'prim_potansiyeli': f'{prim_potansiyeli:.2f}',
            'analiz_tipi_aciklama': analiz_tipi_aciklama
        }
    return render_template('index.html', results=results, yorumlar=yorumlar)

@app.route('/api/hisse_bilgi_yf')
def hisse_bilgi_yf():
    kod = request.args.get('kod')
    if not kod:
        return jsonify({'error': 'Kod gerekli'}), 400
    
    try:
        # Kod formatını düzelt
        if not kod.endswith('.IS'):
            kod = kod + '.IS'
        
        # Önbellekten veri al
        info = get_cached_stock_data(kod)
        
        if not info:
            return jsonify({'error': 'Hisse senedi verisi bulunamadı'}), 404
        
        # Verileri güvenli bir şekilde al
        fiyat = info.get('regularMarketPrice')
        piyasa_degeri = info.get('marketCap')
        fk_orani = info.get('trailingPE')
        pddd_orani = info.get('priceToBook')
        odenmis_sermaye = info.get('sharesOutstanding')
        ozsermaye_hisse_basi = info.get('bookValue')
        net_kar = info.get('netIncomeToCommon')
        
        # Özsermaye hesaplaması
        ozsermaye = None
        if ozsermaye_hisse_basi is not None and odenmis_sermaye is not None:
            ozsermaye = ozsermaye_hisse_basi * odenmis_sermaye
        
        # Eksik verileri kontrol et
        if fiyat is None:
            return jsonify({'error': 'Hisse fiyatı alınamadı'}), 404
        
        # Yanıt verilerini hazırla
        response_data = {
            'fiyat': fiyat,
            'net_kar': net_kar,
            'ozsermaye': ozsermaye,
            'odenmis_sermaye': odenmis_sermaye,
            'fk_orani': fk_orani,
            'pddd_orani': pddd_orani,
            'piyasa_degeri': piyasa_degeri,
            'kullanilan_kod': kod
        }
        
        # None değerleri temizle
        response_data = {k: v for k, v in response_data.items() if v is not None}
        
        return jsonify(response_data)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            return jsonify({
                'error': 'Çok fazla istek gönderildi',
                'detail': 'Lütfen birkaç saniye bekleyip tekrar deneyin',
                'retry_after': MIN_REQUEST_INTERVAL
            }), 429
        return jsonify({'error': 'Veri alınamadı: HTTP hatası', 'detail': str(e)}), e.response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Veri alınamadı: Ağ hatası', 'detail': str(e)}), 503
    except Exception as e:
        return jsonify({'error': 'Veri işlenemedi', 'detail': str(e)}), 500

def draw_last_candle_center(img, coords):
    """
    Son mumun gövdesinin ortasını tespit eder ve daire ile işaretler.
    :param img: OpenCV görüntüsü
    :param coords: Mum koordinatları (y, x)
    :return: img, son_x, son_y (daire merkez koordinatları)
    """
    import numpy as np
    import cv2

    coords_array = np.array(coords)

    # En sağdaki mumun x koordinatını bul
    max_x = np.max(coords_array[:, 1])

    # Bu muma ait tüm piksel koordinatlarını al (gövde)
    rightmost_candle = coords_array[np.abs(coords_array[:, 1] - max_x) < 5]

    # Eğer mumu bulamadıysa fallback
    if len(rightmost_candle) == 0:
        return img, img.shape[1] - 120, img.shape[0] // 2

    # Gövde ortasının koordinatlarını hesapla
    son_x = int(np.mean(rightmost_candle[:, 1]))
    son_y = int(np.mean(rightmost_candle[:, 0]))

    # Dış kırmızı daire
    cv2.circle(img, (son_x, son_y), 18, (0, 0, 255), 3)

    # İç beyaz dolgu
    cv2.circle(img, (son_x, son_y), 10, (255, 255, 255), -1)

    return img, son_x, son_y

def draw_ghost_scenario(image_bytes, son_fiyat, destek, direnç, bolgeler, coords=None):
    import cv2
    import numpy as np

    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    center_x = w // 2
    center_y = h // 2
    # Kırmızı daire tam ortada
    cv2.circle(img, (center_x, center_y), 18, (0, 0, 255), 3)
    cv2.circle(img, (center_x, center_y), 10, (255, 255, 255), -1)

    if bolgeler:
        sorted_boxes = sorted(bolgeler, key=lambda b: b['y1'])
        max_strength = max(b['strength'] for b in bolgeler)
        for box in bolgeler:
            box['relative_strength'] = box['strength'] / max_strength

        # 1. Durum: Siyah zigzag (dirençten desteğe, sade)
        points1 = [[center_x, center_y]]
        x_step = 60
        for box in sorted_boxes:
            points1.append([points1[-1][0] + x_step, box['y1']])
            points1.append([points1[-1][0] + x_step, box['y2']])
        points1.append([points1[-1][0] + x_step, box['y2'] + 60])
        cv2.polylines(img, [np.array(points1, np.int32)], False, (0,0,0), 3)
        cv2.putText(img, '1. Durum', (center_x, center_y - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,0), 2)

        # 2. Durum: Sarı kutular direnç, çizgi sadece altlarına kadar inip en alt kırmızı desteğe kadar satıcılı iner
        points2 = [[center_x, center_y]]
        yellow_boxes = [b for b in sorted_boxes if 'Zayif' in b.get('label','') or 'Bolge' in b.get('label','')]
        if yellow_boxes:
            for box in yellow_boxes:
                # Sadece sarı kutunun altına in (direnç)
                points2.append([points2[-1][0] + x_step, box['y2']])
            # Son sarı kutunun altından en alt kırmızı desteğe in
            points2.append([points2[-1][0] + x_step, destek])
        else:
            # Sarı kutu yoksa klasik zigzag
            for box in sorted_boxes:
                points2.append([points2[-1][0] + x_step, box['y2']])
                points2.append([points2[-1][0] + x_step, box['y1']])
            points2.append([points2[-1][0] + x_step, box['y1'] - 60])
        cv2.polylines(img, [np.array(points2, np.int32)], False, (0,128,0), 3)
        cv2.putText(img, '2. Durum', (center_x, center_y - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,128,0), 2)

        # 3. Durum: Kırmızı çizgi (güçlü bölgede kırılım)
        points3 = [[center_x, center_y]]
        for box in sorted_boxes:
            if box['relative_strength'] > 0.7:
                points3.append([points3[-1][0] + x_step, box['y1']])
                points3.append([points3[-1][0] + x_step, box['y2']])
                points3.append([points3[-1][0] + x_step, box['y2'] + 80])
                break
        cv2.polylines(img, [np.array(points3, np.int32)], False, (0,0,255), 3)
        cv2.putText(img, '3. Durum', (center_x, center_y - 65), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,255), 2)

        # 4. Durum: Sarı kutularda zigzagdan sonra yukarı kırılım (tepeye dokunan yeşil çizgi)
        points4 = [[center_x, center_y]]
        for box in sorted_boxes:
            points4.append([points4[-1][0] + x_step, box['y2']])
            points4.append([points4[-1][0] + x_step, box['y1']])
        # Son noktayı direnç parametresine veya grafiğin üstüne uzat
        if direnç is not None:
            top_y = int(direnç)
        else:
            top_y = 30
        final_x4 = points4[-1][0] + x_step
        points4.append([final_x4, top_y])
        cv2.polylines(img, [np.array(points4, np.int32)], False, (0,200,0), 3)
        cv2.putText(img, '4. Durum', (center_x, center_y - 85), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,200,0), 2)
    else:
        zigzag_points = np.array([
            [center_x, center_y],
            [center_x+30, center_y-20],
            [center_x+60, center_y+20],
            [center_x+90, center_y-20],
            [center_x+120, center_y]
        ], np.int32)
        cv2.polylines(img, [zigzag_points], False, (0,0,0), 3)
        cv2.arrowedLine(img, tuple(zigzag_points[-2]), tuple(zigzag_points[-1]), (0,0,0), 3, tipLength=0.4)

    # Senaryo metinleri
    base_x = int(w * 0.68)
    base_y = int(h * 0.06)
    line_spacing = int(h * 0.045)
    # Statik başlıkları tamamen kaldırdım, hiçbir şey yazılmayacak.

    _, buffer = cv2.imencode('.png', img)
    return buffer.tobytes()

def improved_mum_graph_analysis(image_bytes):
    # Görseli byte dizisinden OpenCV formatına çevir
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    # Grafik bölgesini kırp (üst, alt, sol, sağ boşlukları çıkar)
    crop_top = int(h * 0.18)
    crop_bottom = int(h * 0.92)
    crop_left = int(w * 0.08)
    crop_right = int(w * 0.97)
    cropped_img = img[crop_top:crop_bottom, crop_left:crop_right]

    # Mumları tespit etmek için renk maskeleri oluştur (kırmızı ve yeşil mumlar)
    hsv = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2HSV)
    red1 = cv2.inRange(hsv, (0, 70, 50), (10, 255, 255))
    red2 = cv2.inRange(hsv, (170, 70, 50), (180, 255, 255))
    green = cv2.inRange(hsv, (36, 50, 50), (89, 255, 255))
    mask = red1 | red2 | green

    # Maskeleme sonucunda mum piksel koordinatlarını al
    coords = np.column_stack(np.where(mask > 0))
    if coords.shape[0] == 0:
        return "Mum çubukları tespit edilemedi."

    # En yüksek ve en düşük mum pikselini bul (y koordinatına göre)
    top = tuple(coords[coords[:, 0].argmin()][::-1])
    bottom = tuple(coords[coords[:, 0].argmax()][::-1])
    top_global = (top[0] + crop_left, top[1] + crop_top)
    bottom_global = (bottom[0] + crop_left, bottom[1] + crop_top)

    # En yüksek ve en düşük seviyeye yatay çizgi çiz
    cv2.line(img, (0, top_global[1]), (w, top_global[1]), (0, 255, 0), 2)  # yeşil = direnç
    cv2.putText(img, 'Direnç', (10, top_global[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.line(img, (0, bottom_global[1]), (w, bottom_global[1]), (0, 0, 255), 2)  # kırmızı = destek
    cv2.putText(img, 'Destek', (10, bottom_global[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    # Sık dokunulan seviye analizleri için dokunma sayısı haritası oluştur
    touch_counts = {}
    y_tolerance = 3  # yakın seviyeler gruplanır
    for y in coords[:, 0]:
        found = False
        for key in list(touch_counts.keys()):
            if abs(y - key) <= y_tolerance:
                touch_counts[key] += 1
                found = True
                break
        if not found:
            touch_counts[y] = 1

    # En çok temas edilen ilk 4 yatay seviye → SeviyeX sayısı olarak yazılır
    most_touched = sorted(touch_counts.items(), key=lambda x: x[1], reverse=True)[:4]
    most_touched_levels = []
    for y_local, count in most_touched:
        y_global = int(y_local + crop_top)
        color = (255, 0, 255) if y_global > h // 2 else (255, 165, 0)
        cv2.line(img, (0, y_global), (w, y_global), color, 1)
        
        # Etiket pozisyonlarını dönüşümlü olarak değiştir
        text_positions = [
            (w - 160, y_global - 5),      # sağ üst
            (w - 160, y_global + 15),     # sağ alt
            (10, y_global - 5),           # sol üst
            (10, y_global + 15)           # sol alt
        ]
        text_pos = text_positions[len(most_touched_levels) % len(text_positions)]
        
        cv2.putText(img, f'Seviyex{count}', text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
        most_touched_levels.append({
            'y': int(y_global),
            'count': int(count)
        })

    # Yoğunluk analizi için dikey (y ekseni) yoğunluk haritası oluştur
    density_map = np.zeros((cropped_img.shape[0],), dtype=int)
    for y in coords[:, 0]:
        density_map[y] += 1

    # Sadece üst %25 yoğunlukta olan seviyeleri kümeye al
    threshold = np.percentile(density_map, 75)
    clusters = []
    in_cluster = False
    cluster_start = 0
    for y in range(len(density_map)):
        if density_map[y] >= threshold and not in_cluster:
            in_cluster = True
            cluster_start = y
        elif density_map[y] < threshold and in_cluster:
            in_cluster = False
            cluster_end = y
            density_sum = np.sum(density_map[cluster_start:cluster_end])
            clusters.append((cluster_start, cluster_end, density_sum))

    # Kümeler içinde en yoğunu referans alarak göreceli yoğunluk renklerini ayarla
    cluster_results = []
    if clusters:
        max_density = max([c[2] for c in clusters])

    for i, (start, end, strength) in enumerate(clusters):
        y1 = start + crop_top
        y2 = end + crop_top
        norm_strength = strength / max_density if clusters else 0

        # Göreceli yoğunluğa göre renk ve etiket seçimi
        if norm_strength > 0.75:
            label = "Bolge 1"
        elif norm_strength > 0.5:
            label = "Bolge 2"
        elif norm_strength > 0.3:
            label = "Bolge 3"
        else:
            label = "Zayif"

        # Etiket pozisyonunu döngüsel olarak değiştir
        text_positions = [
            (crop_left + 5, y1 - 6),           # sol üst
            (crop_left + 5, y2 + 15),          # sol alt
            (w - 150, y1 - 6),                 # sağ üst
            (w - 150, y2 + 15)                 # sağ alt
        ]
        text_pos = text_positions[i % len(text_positions)]

        # Kümeyi grafik üzerinde kutu olarak çiz ve üzerine etiket yaz
        cv2.rectangle(img, (crop_left, y1), (crop_right, y2), (0, 255, 255), 2)
        cv2.putText(img, f"{label} ({strength})", text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        cluster_results.append({
            'y1': int(y1),
            'y2': int(y2),
            'strength': int(strength),
            'label': label
        })

    # Sonuç görüntüyü PIL Image olarak PNG byte'ına çevir ve döndür
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    buffer = BytesIO()
    pil_img.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()

    # X ekseni: Gerçek mum sayısı
    num_mum = len(coords)
    trend_labels = [str(i+1) for i in range(num_mum)]

    # Y ekseni: crop_top + y_raw (fiyat gibi) -> TERSLE!
    y_raw = coords[:, 0]
    y_fiyat = h - (crop_top + y_raw)

    # Outlier temizliği
    low, high = np.percentile(y_fiyat, [2, 98])
    y_filtered = np.clip(y_fiyat, low, high)

    # Hareketli ortalama
    window = 10
    y_smooth = scipy.ndimage.uniform_filter1d(y_filtered, size=window, mode='nearest')

    # Çizgi seviyelerini al
    direnc_y = int(top_global[1])
    destek_y = int(bottom_global[1])
    mor_y = [lvl['y'] for lvl in most_touched_levels]
    sari_y = []
    for c in cluster_results:
        sari_y.append(c['y1'])
        sari_y.append(c['y2'])

    # Her pencere için ortalama y (veya y_smooth)
    window = 30
    y_values = coords[:, 0]
    pencere_ort = []
    for i in range(0, len(y_values), max(1, len(y_values)//window)):
        window_y = y_values[i:i+max(1, len(y_values)//window)]
        if len(window_y) > 0:
            pencere_ort.append(np.mean(window_y) + crop_top)

    # Her pencere için uzaklıkları hesapla
    uzaklik_direnc = [abs(y - direnc_y) for y in pencere_ort]
    uzaklik_destek = [abs(y - destek_y) for y in pencere_ort]
    uzaklik_mor = [min([abs(y - m) for m in mor_y]) if mor_y else 0 for y in pencere_ort]
    uzaklik_sari = [min([abs(y - s) for s in sari_y]) if sari_y else 0 for y in pencere_ort]

    # Trend yönü ve gücü hesapla (dinamik: son pencere hareketine göre)
    if len(pencere_ort) >= 2:
        short_trend_delta = pencere_ort[-1] - pencere_ort[-2]
        if abs(short_trend_delta) < 2:
            trend_yon = "Yatay"
        elif short_trend_delta < 0:
            trend_yon = "Yukarı"
        else:
            trend_yon = "Aşağı"
        short_abs_delta = abs(short_trend_delta)
        if short_abs_delta < 5:
            trend_guc = "Zayıf"
        elif short_abs_delta < 20:
            trend_guc = "Orta"
        else:
            trend_guc = "Güçlü"
    else:
        trend_yon = ""
        trend_guc = ""

    trend_data = {
        "labels": [str(i) for i in range(len(pencere_ort))],
        "uzaklik_direnc": uzaklik_direnc,
        "uzaklik_destek": uzaklik_destek,
        "uzaklik_mor": uzaklik_mor,
        "uzaklik_sari": uzaklik_sari,
        "yon": trend_yon,
        "guc": trend_guc
    }

    # Son fiyatı belirle (sağdan 3. mumun kapanış fiyatı)
    son_fiyat = None
    if len(coords) >= 3:
        son_3_mum = sorted(coords, key=lambda x: x[1])[-3:]
        son_fiyat = np.mean([mum[0] for mum in son_3_mum]) + crop_top
    
    # Analiz sonuçlarını hazırla
    result = {
        'image_bytes': image_bytes,
        'direnc_y': int(top_global[1]),
        'destek_y': int(bottom_global[1]),
        'son_fiyat': int(son_fiyat) if son_fiyat else None,
        'most_touched_levels': [
            {'y': lvl['y'], 'dokunma_sayisi': lvl.get('count', None), 'type': 'sarı kutu'} for lvl in most_touched_levels
        ],
        'clusters': cluster_results,
        'trend_data': trend_data
    }
    # Destek ve direnç seviyelerini de önemli seviyelere ekle
    result['most_touched_levels'].append({'y': int(top_global[1]), 'dokunma_sayisi': None, 'type': 'direnç'})
    result['most_touched_levels'].append({'y': int(bottom_global[1]), 'dokunma_sayisi': None, 'type': 'destek'})
    
    # Hayalet senaryoları çiz
    if son_fiyat:
        ghost_image = draw_ghost_scenario(
            image_bytes,
            son_fiyat,
            result['destek_y'],
            result['direnc_y'],
            result['clusters'],
            coords=coords
        )
        result['ghost_image_bytes'] = ghost_image
    
    # --- Senaryo Açıklamaları ---
    scenario_comments = []
    yellow_boxes = [b for b in result['clusters'] if 'Zayif' in b.get('label','') or 'Bolge' in b.get('label','')]
    yellow_levels = [b['y1'] for b in yellow_boxes]
    yellow_levels_str = ', '.join(str(y) for y in yellow_levels) if yellow_levels else 'yok'
    destek = result.get('destek_y')
    direnc = result.get('direnc_y')
    # 1. Durum (Siyah çizgi)
    if yellow_levels:
        scenario_comments.append(
            f"1. Durum: Fiyat, {yellow_levels[0]} seviyesindeki ilk sarı direnç kutusundan aşağı kırılırsa, satıcılı bir seyir izlenebilir ve {destek} destek seviyesini test etmesi muhtemeldir."
        )
    else:
        scenario_comments.append(
            "1. Durum: Fiyat, ilk dirençten aşağı kırılırsa, alt destek seviyeleri test edilebilir."
        )
    # 2. Durum (Yeşil çizgi)
    if yellow_levels:
        scenario_comments.append(
            f"2. Durum: Fiyat, {yellow_levels_str} dirençlerini aşarak yukarı yönlü hareket ederse, {direnc} seviyesine kadar yükseliş potansiyeli oluşur."
        )
    else:
        scenario_comments.append(
            "2. Durum: Fiyat, dirençleri aşarsa üst seviyelere kadar yükseliş potansiyeli oluşur."
        )
    # 3. Durum (Kırmızı çizgi)
    guclu_bolge = next((b for b in yellow_boxes if 'Bolge' in b.get('label','')), None)
    if guclu_bolge:
        scenario_comments.append(
            f"3. Durum: Güçlü direnç bölgesi ({guclu_bolge['y1']}) civarında sert bir kırılım yaşanırsa, fiyat hızla {destek} seviyesine çekilebilir."
        )
    else:
        scenario_comments.append(
            "3. Durum: Güçlü direnç bölgesinde kırılım olursa, fiyat alt desteklere çekilebilir."
        )
    # 4. Durum (Zigzag sonrası yukarı kırılım)
    if yellow_levels:
        scenario_comments.append(
            f"4. Durum: Fiyat, {yellow_levels_str} dirençlerinde yatay hareket ettikten sonra yukarı kırılırsa, {direnc} seviyesine kadar ivmelenebilir."
        )
    else:
        scenario_comments.append(
            "4. Durum: Fiyat, dirençlerde yatay hareket sonrası yukarı kırılırsa üst seviyelere ivmelenebilir."
        )
    # Ek uyarıcı ve rehber metinler
    if yellow_levels:
        scenario_comments.append(
            "Sarı direnç kutularında uzun süre yatay hareket eden fiyatlarda, yukarı kırılım gelmediği sürece güçlü bir yükseliş beklenmemelidir. Bu seviyelerdeki sıkışma sonrası aşağı kırılım, satış baskısını artırabilir."
        )
        scenario_comments.append(
            f"Fiyat, sarı direnç ({yellow_levels_str}) altında kaldığı sürece, mumlar satıcılı seyir izleyebilir ve {destek} destek seviyeleri test edilebilir."
        )
        scenario_comments.append(
            f"Sarı direnç kutularında yatay hareket sonrası yukarı kırılım gerçekleşirse, güçlü bir yükseliş ivmesi ve {direnc} seviyesine hareket beklenebilir."
        )
    result['scenario_comments'] = scenario_comments
    return result

@app.route('/analyze-image', methods=['POST'])
@login_required
def analyze_image():
    if 'image' not in request.files:
        return jsonify({'error': 'Görsel yüklenmedi'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Dosya seçilmedi'}), 400
    
    try:
        # Görseli analiz et
        image_bytes = file.read()
        print("Görsel boyutu:", len(image_bytes))
        
        result = improved_mum_graph_analysis(image_bytes)
        print("Analiz sonucu:", result)
        
        if isinstance(result, str):
            return jsonify({'error': result}), 400
            
        # Base64 formatına çevir
        import base64
        image_base64 = base64.b64encode(result['image_bytes']).decode('utf-8')
        ghost_image_base64 = base64.b64encode(result['ghost_image_bytes']).decode('utf-8') if 'ghost_image_bytes' in result else None
        
        response_data = {
            'image': image_base64,
            'ghost_image': ghost_image_base64,
            'analysis': {
                'direnc': result['direnc_y'],
                'destek': result['destek_y'],
                'son_fiyat': result['son_fiyat'],
                'seviyeler': result['most_touched_levels'],
                'bolgeler': result['clusters'],
                'trend': result['trend_data'],
                'scenario_comments': result['scenario_comments']
            }
        }
        print("Gönderilen veri:", response_data)
        
        return jsonify(response_data)
        
    except Exception as e:
        print("Hata:", str(e))
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 