import os

class Config:
    SECRET_KEY = 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = 'postgresql://myapp_db_syo5_user:Ok1hGkhq7yprRvqjtgvXXSGSzgHbEmua@dpg-d0aekds9c44c738vad3g-a.oregon-postgres.render.com/myapp_db_syo5'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = None
    MAIL_PASSWORD = None
    MAIL_DEFAULT_SENDER = None 