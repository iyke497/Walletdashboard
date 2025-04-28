from datetime import datetime
from app.extensions import db

class CryptoAsset(db.Model):
    __tablename__ = 'crypto_assets'
    id       = db.Column(db.Integer, primary_key=True)
    symbol   = db.Column(db.String(10), nullable=False)
    name     = db.Column(db.String(50), nullable=False)
    coingecko_id = db.Column(db.String(50), unique=True, nullable=False)
    decimals = db.Column(db.Integer, default=8)

    balances = db.relationship('AccountAssetBalance', back_populates='asset', lazy='dynamic')
    deposit_addresses = db.relationship('DepositAddress', back_populates='asset', lazy='dynamic')