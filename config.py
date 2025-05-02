import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://myapp_db_syo5_user:Ok1hGkhq7yprRvqjtgvXXSGSzgHbEmua@dpg-d0aekds9c44c738vad3g-a.oregon-postgres.render.com/myapp_db_syo5'
    SQLALCHEMY_TRACK_MODIFICATIONS = False 