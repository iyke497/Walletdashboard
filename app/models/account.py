from datetime import datetime
from app.extensions import db


class Account(db.Model):
    __tablename__ = 'accounts'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name         = db.Column(db.String(50), nullable=False)  # e.g. “Funding”
    account_type = db.Column(
        db.Enum('funding','trading','fiat','margin','spot', name='acct_types'),
        nullable=False
    )
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user         = db.relationship('User', back_populates='accounts')
    balances     = db.relationship('AccountAssetBalance', back_populates='account', lazy='dynamic')
    transactions = db.relationship('Transaction', back_populates='account', lazy='dynamic')