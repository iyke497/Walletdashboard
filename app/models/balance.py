from decimal import Decimal
from app.extensions import db

class AccountAssetBalance(db.Model):
    __tablename__ = 'account_asset_balances'

    id                = db.Column(db.Integer, primary_key=True)
    account_id        = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    asset_id          = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    available_balance = db.Column(db.Numeric(36,18), nullable=False, default=Decimal('0'))
    frozen_balance    = db.Column(db.Numeric(36,18), nullable=False, default=Decimal('0'))

    account = db.relationship('Account', back_populates='balances')
    asset   = db.relationship('CryptoAsset', back_populates='balances')