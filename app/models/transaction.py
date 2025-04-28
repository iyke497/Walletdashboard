from datetime import datetime
from app.extensions import db

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id          = db.Column(db.Integer, primary_key=True)
    account_id  = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    asset_id    = db.Column(db.Integer, db.ForeignKey('crypto_assets.id'), nullable=False)
    amount      = db.Column(db.Numeric(36,18), nullable=False)  # + for deposit/buy, – for withdraw/sell
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    tx_type     = db.Column(
        db.Enum('deposit','withdrawal','trade','transfer', name='tx_types'),
        nullable=False
    )
    reference   = db.Column(db.String(255))  # on-chain txid or internal ref

    account     = db.relationship('Account', back_populates='transactions')
    asset       = db.relationship('CryptoAsset')