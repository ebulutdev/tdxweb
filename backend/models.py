from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Stock(db.Model):
    __tablename__ = 'stocks'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False)
    dates = db.Column(db.JSON, nullable=False)
    prices = db.Column(db.JSON, nullable=False)
    support_levels = db.Column(db.JSON, nullable=False)
    resistance_levels = db.Column(db.JSON, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class StockNews(db.Model):
    __tablename__ = 'stock_news'
    
    id = db.Column(db.Integer, primary_key=True)
    stock_symbol = db.Column(db.String(10), db.ForeignKey('stocks.symbol'), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(500), nullable=False)
    summary = db.Column(db.Text)
    published = db.Column(db.DateTime)
    source = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class StockAnalysis(db.Model):
    __tablename__ = 'stock_analysis'
    
    id = db.Column(db.Integer, primary_key=True)
    stock_symbol = db.Column(db.String(10), db.ForeignKey('stocks.symbol'), nullable=False)
    analysis_text = db.Column(db.Text, nullable=False)
    scenario_lists = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow) 