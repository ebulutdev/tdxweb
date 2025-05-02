from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from config import Config
from models import db, User
from flask_migrate import Migrate

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

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

        # F/K ve PD/DD analizleri
        fk, fk_yorum = fk_degerleme(hisse_fiyati, net_kar, odenmis_sermaye, sektor_fk)
        pddd, pddd_yorum = pddd_degerleme(hisse_fiyati, ozsermaye, odenmis_sermaye, sektor_pddd)

        # Diğer klasik yöntemler
        fiyat_fk = (net_kar * fk_orani) / odenmis_sermaye
        fiyat_future_fk = (net_kar * fk_orani * 1.27) / odenmis_sermaye
        fiyat_pddd = (ozsermaye * pddd_orani) / odenmis_sermaye
        fiyat_sermaye = piyasa_degeri / odenmis_sermaye
        fiyat_potansiyel = (piyasa_degeri * 1.1) / odenmis_sermaye
        fiyat_ozsermaye_kar = (net_kar * 2) / odenmis_sermaye

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

        results = {
            'hisse_adi': hisse_adi,
            'fiyat_fk': f'{fiyat_fk:.2f}',
            'fiyat_future_fk': f'{fiyat_future_fk:.2f}',
            'fiyat_pddd': f'{fiyat_pddd:.2f}',
            'fiyat_sermaye': f'{fiyat_sermaye:.2f}',
            'fiyat_potansiyel': f'{fiyat_potansiyel:.2f}',
            'fiyat_ozsermaye_kar': f'{fiyat_ozsermaye_kar:.2f}',
            'ortalama_fiyat': f'{ortalama_fiyat:.2f}',
            'prim_potansiyeli': f'{prim_potansiyeli:.2f}'
        }
    return render_template('index.html', results=results, yorumlar=yorumlar)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 