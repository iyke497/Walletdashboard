from datetime import datetime
from app.extensions import db

class DepositAddress(db.Model):
    __tablename__ = 'deposit_addresses'

    id          = db.Column(db.Integer, primary_key=True)
    asset_id    = db.Column(db.Integer, db.ForeignKey('crypto_assets.id'), nullable=False)
    address     = db.Column(db.String(255), unique=True, nullable=False)
    qr_code_png = db.Column(db.LargeBinary, nullable=False)  # raw PNG bytes
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    asset = db.relationship('CryptoAsset', back_populates='deposit_addresses')