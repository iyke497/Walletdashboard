from datetime import datetime, timedelta
from enum import Enum
import requests
import secrets
import pyotp
import qrcode
import io
import base64
from sqlalchemy import Enum as SQLAlchemyEnum, CheckConstraint
from sqlalchemy import orm, event
from flask_login import UserMixin
from .extensions import db, cache
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
    TRON = "tron"
    OTHER = "other"


# ---- Models ----
class User(db.Model, UserMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)

    # Personal Information
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)

    # Address Information
    address = db.Column(db.String(200), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    zip_code = db.Column(db.String(10), nullable=True)
    country = db.Column(db.String(50), nullable=True)

    # Preferences
    language = db.Column(db.String(5), nullable=True, default='en')
    timezone = db.Column(db.String(10), nullable=True)
    display_currency_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=True)

    # Email verification fields
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    email_verification_token = db.Column(db.String(100), unique=True, nullable=True)
    email_verification_sent_at = db.Column(db.DateTime, nullable=True)

    # Password reset fields
    password_reset_token = db.Column(db.String(100), nullable=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)

    # Two-Factor Authentication using TOTP
    two_factor_enabled = db.Column(db.Boolean, nullable=False, default=False)
    totp_secret = db.Column(db.String(32), nullable=True)  # Base32 encoded secret

    
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
    
    # Auth
    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    def generate_password_reset_token(self):
        """Generate a password reset token"""
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_expires = datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
        return self.password_reset_token
    
    def is_password_reset_token_valid(self, token):
        """Check if password reset token is valid and not expired"""
        return (self.password_reset_token == token and 
                self.password_reset_expires and 
                datetime.utcnow() < self.password_reset_expires)
    
    def clear_password_reset_token(self):
        """Clear password reset token after use"""
        self.password_reset_token = None
        self.password_reset_expires = None
    
    def generate_verification_token(self):
        """Generate a unique verification token"""
        self.email_verification_token = secrets.token_urlsafe(32)
        self.email_verification_sent_at = datetime.utcnow()
        return self.email_verification_token
    
    def is_verification_token_valid(self, token, expiry_hours=24):
        """Check if verification token is valid and not expired"""
        if not self.email_verification_token or self.email_verification_token != token:
            return False
        
        if not self.email_verification_sent_at:
            return False
            
        expiry_time = self.email_verification_sent_at + timedelta(hours=expiry_hours)
        return datetime.utcnow() <= expiry_time
    
    def verify_email(self):
        """Mark email as verified and clear verification token"""
        self.email_verified = True
        self.email_verification_token = None
        self.email_verification_sent_at = None

    def generate_totp_secret(self):
        """Generate a new TOTP secret for the user"""
        self.totp_secret = pyotp.random_base32()
        return self.totp_secret

    def get_totp_uri(self, app_name="Crypto Dashboard"):
        """Get the TOTP URI for QR code generation"""
        if not self.totp_secret:
            self.generate_totp_secret()
        
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.email,
            issuer_name=app_name
        )

    def verify_totp(self, token):
        """Verify a TOTP token"""
        if not self.totp_secret:
            return False
        
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(token, valid_window=1)  # Allow 1 window of tolerance

    def get_qr_code(self):
        """Generate QR code as base64 string for display"""
        if not self.totp_secret:
            self.generate_totp_secret()
        
        uri = self.get_totp_uri()
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 for HTML embedding
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_base64}"
    # ------------------->
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
    images = db.Column(db.JSON, nullable=True)
    networks = db.Column(db.JSON, nullable=True)
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


class DepositAddress(db.Model, TimestampMixin, SoftDeleteMixin): # TODO: Delete
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

class TradeOrder(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'trade_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    base_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    quote_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    order_type = db.Column(db.String(20))  # market/limit/stop
    side = db.Column(db.String(4))  # buy/sell
    amount = db.Column(db.Numeric(30, 18))
    price = db.Column(db.Numeric(30, 18))  # null for market orders
    status = db.Column(db.String(20), default='open')

    # Relationships
    user = db.relationship('User', backref='trade_orders')
    base_asset = db.relationship('Asset', foreign_keys=[base_asset_id])
    quote_asset = db.relationship('Asset', foreign_keys=[quote_asset_id])


class OrderBook(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'order_book'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    base_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    quote_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    order_type = db.Column(db.String(20))  # market/limit
    side = db.Column(db.String(4))  # buy/sell
    amount = db.Column(db.Numeric(30, 18))
    price = db.Column(db.Numeric(30, 18))
    status = db.Column(db.String(20), default='open')  # open/filled/cancelled

    # Relationships
    user = db.relationship('User', backref='limit_orders')
    base_asset = db.relationship('Asset', foreign_keys=[base_asset_id])
    quote_asset = db.relationship('Asset', foreign_keys=[quote_asset_id])

    __table_args__ = (
        db.Index('idx_order_book_assets', 'base_asset_id', 'quote_asset_id'),
        db.Index('idx_order_book_status', 'status'),
    )

    def __repr__(self):
        return (f"<OrderBook {self.order_type} {self.side} {self.amount} "
                f"{self.base_asset.symbol}/{self.quote_asset.symbol} @ {self.price}>")

# ---- Copy Trading Models ----
class Trader(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'traders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    bio = db.Column(db.Text)
    tags = db.Column(db.String(255))  # Comma-separated tags (e.g., "crypto,swing,conservative")
    win_rate = db.Column(db.Numeric(5, 2))  # Stored as percentage (e.g., 76.50)
    avg_monthly_return = db.Column(db.Numeric(5, 2))  # Percentage
    max_drawdown = db.Column(db.Numeric(5, 2))  # Percentage
    risk_score = db.Column(db.String(20), default='medium')  # low/medium/high
    is_verified = db.Column(db.Boolean, default=False)
    performance_metrics = db.Column(db.JSON)  # For storing additional stats
    
    # Relationships
    user = db.relationship('User', backref=db.backref('trader_profile', uselist=False))
    followers = db.relationship('CopyTrade', back_populates='trader')

    def __repr__(self):
        return f"<Trader {self.user.username}>"

class CopyTrade(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'copy_trades'
    
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    trader_id = db.Column(db.Integer, db.ForeignKey('traders.id'), nullable=False)
    allocation = db.Column(db.Numeric(5, 2))  # Percentage of capital to allocate
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    follower = db.relationship('User', foreign_keys=[follower_id], 
                              backref=db.backref('copied_trades'))
    trader = db.relationship('Trader', back_populates='followers')

    __table_args__ = (
        db.UniqueConstraint('follower_id', 'trader_id', name='uq_follower_trader'),
    )

    def __repr__(self):
        return f"<CopyTrade {self.follower.username} -> {self.trader.user.username}>"

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