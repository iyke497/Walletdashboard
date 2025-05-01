from datetime import datetime
from enum import Enum
from sqlalchemy import Enum as SQLAlchemyEnum, CheckConstraint
from sqlalchemy import orm, event
from flask_login import UserMixin
from .extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


# Configure soft-delete query
class SoftDeleteQuery(orm.Query):
    def __new__(cls, *args, **kwargs):
        query = super().__new__(cls)
        query._with_deleted = False
        return query

    def with_deleted(self):
        query = self.__class__(db.session())
        query._with_deleted = True
        return query

    def _get_from_identity_map(self, key):
        # Added this to ensure consistency with non-deleted filtering
        if key is not None and not self._with_deleted:
            session = self.session
            instance = session.identity_map.get(key)
            if instance is not None and instance.deleted_at is not None:
                return None
        return super()._get_from_identity_map(key)

    def __iter__(self):
        if not self._with_deleted:
            return super().__iter__().filter(SoftDeleteMixin.deleted_at.is_(None))
        return super().__iter__()

    def get(self, ident):
        # Override to ensure soft-deleted records aren't returned by get()
        obj = super().get(ident)
        if obj is None:
            return None
        if self._with_deleted or obj.deleted_at is None:
            return obj
        return None


# ---- Mixins ----
class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SoftDeleteMixin:
    deleted_at = db.Column(db.DateTime, nullable=True)  # Null = not deleted
    query_class = SoftDeleteQuery

    def soft_delete(self):
        self.deleted_at = datetime.utcnow()
        return self

    def restore(self):
        self.deleted_at = None
        return self


# ---- Enums ----
class TransactionType(Enum):
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    TRADE_BUY = "trade_buy"
    TRADE_SELL = "trade_sell"
    STAKE = "stake"
    UNSTAKE = "unstake"
    FEE = "fee"
    TRANSFER = "transfer"


class AssetType(Enum):
    CRYPTO = "crypto"
    FIAT = "fiat"


class NetworkType(Enum):
    ETHEREUM = "ethereum"
    BITCOIN = "bitcoin"
    BINANCE_SMART_CHAIN = "bsc"
    POLYGON = "polygon"
    SOLANA = "solana"
    AVALANCHE = "avalanche"
    COSMOS = "cosmos"
    OTHER = "other"


# ---- Models ----
class User(db.Model, UserMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    display_currency_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=True)
    
    # Enhanced relationships
    display_currency = db.relationship('Asset', foreign_keys=[display_currency_id])
    holdings = db.relationship('Holding', back_populates='user', cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', back_populates='user', cascade='all, delete-orphan')
    staking_positions = db.relationship('StakingPosition', back_populates='user', cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint('LENGTH(username) >= 3', name='ck_username_min_length'),
        CheckConstraint('LENGTH(email) >= 5', name='ck_email_min_length'),
    )

    def __repr__(self):
        return f"<User {self.username}>"
    
    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    def get_portfolio_value(self, base_currency_id):
        """Calculate portfolio value in the specified base currency"""
        # Implementation would use exchange rates and sum holdings
        pass


class Asset(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    coingecko_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    decimals = db.Column(db.Integer, default=8)
    asset_type = db.Column(SQLAlchemyEnum(AssetType), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    staking_positions = db.relationship('StakingPosition', back_populates='asset')
    deposit_addresses = db.relationship('DepositAddress', back_populates='asset')
    holdings = db.relationship('Holding', primaryjoin="Asset.id==Holding.asset_id", cascade="all, delete-orphan")
    
    # Transactions where this asset is the primary asset
    primary_transactions = db.relationship(
        'Transaction',
        primaryjoin="Asset.id==Transaction.asset_id",
        backref="primary_asset"
    )
    
    # Transactions where this asset is the quote asset
    quote_transactions = db.relationship(
        'Transaction',
        primaryjoin="Asset.id==Transaction.quote_asset_id",
        back_populates='quote_asset'
    )

    def __repr__(self):
        return f"<Asset {self.symbol}>"


class Holding(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'holdings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    balance = db.Column(db.Numeric(30, 18), default=0)
    cost_basis = db.Column(db.Numeric(30, 18), nullable=True)  # Average cost basis

    user = db.relationship('User', back_populates='holdings')
    asset = db.relationship('Asset', foreign_keys=[asset_id])

    __table_args__ = (
        db.UniqueConstraint('user_id', 'asset_id', name='uq_user_asset'),
        CheckConstraint('balance >= 0', name='ck_balance_non_negative'),
    )

    def __repr__(self):
        return f"<Holding {self.user_id}:{self.asset.symbol}={self.balance}>"

    @property
    def current_value(self):
        """Calculate current value based on latest exchange rate"""
        # Implementation required - this is just a placeholder
        pass


class Transaction(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    tx_type = db.Column(SQLAlchemyEnum(TransactionType), nullable=False, index=True)
    amount = db.Column(db.Numeric(30, 18), nullable=False)
    fee_amount = db.Column(db.Numeric(30, 18), nullable=True)
    fee_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=True)
    price = db.Column(db.Numeric(30, 18), nullable=True)
    quote_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=True, index=True)
    fiat_conversion_rate = db.Column(db.Numeric(20, 8), nullable=True)
    fiat_conversion_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    external_tx_id = db.Column(db.String(255), nullable=True, index=True)  # For blockchain txs
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', back_populates='transactions')
    asset = db.relationship('Asset', foreign_keys=[asset_id])
    quote_asset = db.relationship('Asset', foreign_keys=[quote_asset_id], back_populates='quote_transactions')
    fiat_conversion_asset = db.relationship('Asset', foreign_keys=[fiat_conversion_asset_id])
    fee_asset = db.relationship('Asset', foreign_keys=[fee_asset_id], backref='fee_transactions')

    __table_args__ = (
        CheckConstraint('amount > 0', name='ck_transaction_amount_positive'),
        CheckConstraint('fee_amount >= 0', name='ck_fee_amount_non_negative'),
    )

    def __repr__(self):
        price_info = f"@{self.price} {self.quote_asset.symbol}" if self.price and self.quote_asset else ""
        conversion_info = f" (~{self.fiat_conversion_rate} {self.fiat_conversion_asset.symbol})" if self.fiat_conversion_rate and self.fiat_conversion_asset else ""
        return (f"<Transaction {self.tx_type.value.upper()} {self.amount} "
                f"{self.asset.symbol}{price_info}{conversion_info} @ {self.timestamp}>")


class ExchangeRate(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'exchange_rates'
    id = db.Column(db.Integer, primary_key=True)
    base_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    quote_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    rate = db.Column(db.Numeric(30, 18), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    source = db.Column(db.String(50), nullable=True)  # Data source (e.g., 'coingecko', 'binance')

    base_asset = db.relationship('Asset', foreign_keys=[base_asset_id])
    quote_asset = db.relationship('Asset', foreign_keys=[quote_asset_id])

    __table_args__ = (
        db.UniqueConstraint('base_asset_id', 'quote_asset_id', 'timestamp', name='uq_rate_assets_time'),
    )

    def __repr__(self):
        return f"<ExchangeRate {self.base_asset.symbol}/{self.quote_asset.symbol}={self.rate} @ {self.timestamp}>"


class DepositAddress(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'deposit_addresses'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    address = db.Column(db.String(255), unique=True, nullable=False)
    network = db.Column(SQLAlchemyEnum(NetworkType), nullable=False)  # Changed to Enum
    is_active = db.Column(db.Boolean, default=True)
    
    asset = db.relationship('Asset', back_populates='deposit_addresses')

    def __repr__(self):
        return f"<DepositAddress {self.asset.symbol}:{self.address} on {self.network.value}>"


class StakingPosition(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'staking_positions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    amount = db.Column(db.Numeric(30, 18), nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)  # Optional lock period
    apy = db.Column(db.Numeric(10, 4), nullable=True)  # Annual percentage yield at time of staking
    provider = db.Column(db.String(100), nullable=True)  # Staking provider info

    user = db.relationship('User', back_populates='staking_positions')
    asset = db.relationship('Asset', back_populates='staking_positions')

    __table_args__ = (
        CheckConstraint('amount > 0', name='ck_staking_amount_positive'),
    )

    def __repr__(self):
        lock_info = f" (locked until {self.locked_until})" if self.locked_until else " (flexible)"
        return f"<StakingPosition {self.user.username}: {self.amount} {self.asset.symbol}{lock_info}>"


# ----- Event listeners -----

@event.listens_for(Transaction, 'after_insert')
def update_holding_after_transaction(mapper, connection, target):
    """Update holdings after transaction is added"""
    # Implementation would adjust the user's holding based on transaction type
    pass


@event.listens_for(Transaction, 'after_delete')
def update_holding_after_transaction_delete(mapper, connection, target):
    """Update holdings after transaction is deleted"""
    # Implementation would adjust the user's holding based on the removed transaction
    pass