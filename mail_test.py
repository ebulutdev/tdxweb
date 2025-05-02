from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'emircanbulut04@gmail.com'      # Kendi Gmail adresin
app.config['MAIL_PASSWORD'] = ''                 # Gmail uygulama şifren
app.config['MAIL_DEFAULT_SENDER'] = 'seninmailadresin@gmail.com' # Gönderen adres

mail = Mail(app)

with app.app_context():
    try:
        msg = Message(
            subject='Test Mail',
            recipients=['kendiadresin@gmail.com'],  # Buraya kendi adresini yaz
            body='Bu bir test mailidir.'
        )
        mail.send(msg)
        print("Mail başarıyla gönderildi!")
    except Exception as e:
        print("Mail gönderilemedi. Hata:", e) 