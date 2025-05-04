from datetime import datetime
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from app.models import Transaction, Asset, Holding, TransactionType, AssetType, ExchangeRate, DepositAddress, NetworkType
from app.extensions import db
import qrcode
from io import BytesIO
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class WalletService:
    @staticmethod
    def _get_or_create_holding(user_id, asset_id):
        """Get existing holding or create a new one if it doesn't exist"""
        holding = Holding.query.filter_by(
            user_id=user_id,
            asset_id=asset_id,
            deleted_at=None
        ).first()
        
        if not holding:
            holding = Holding(
                user_id=user_id,
                asset_id=asset_id,
                balance=Decimal('0')
            )
            db.session.add(holding)
        
        return holding

    @staticmethod
    def generate_deposit_qr(deposit_address: DepositAddress) -> BytesIO:
        """
        Generate a QR code for a deposit address.
        
        Args:
            deposit_address: The DepositAddress object containing the address to encode
            
        Returns:
            BytesIO: A buffer containing the PNG image data
        """
        if not deposit_address or not deposit_address.address:
            raise ValueError("Invalid deposit address")
            
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(deposit_address.address)
        qr.make(fit=True)
        
        # Generate image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to buffer
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        
        return buffer

    @staticmethod
    def get_deposit_address(user_id: int, asset_symbol: str, network: NetworkType) -> DepositAddress:
        """
        Get a deposit address for a specific asset and network.
        
        Args:
            user_id: The ID of the user requesting the address
            asset_symbol: The symbol of the asset (e.g., 'BTC', 'ETH')
            network: The network type (e.g., NetworkType.BITCOIN, NetworkType.ETHEREUM)
            
        Returns:
            DepositAddress: The matching deposit address
        """
        # Get the asset
        asset = Asset.query.filter_by(
            symbol=asset_symbol,
            asset_type=AssetType.CRYPTO,
            deleted_at=None
        ).first()
        
        if not asset:
            raise ValueError(f"Asset {asset_symbol} not found")
            
        # Get the deposit address
        deposit_address = DepositAddress.query.filter_by(
            asset_id=asset.id,
            network=network,
            is_active=True,
            deleted_at=None
        ).first()
        
        if not deposit_address:
            raise ValueError(f"No active deposit address found for {asset_symbol} on {network.value}")
            
        return deposit_address

    @staticmethod
    def deposit_crypto(user_id, asset_symbol, amount, tx_hash=None):
        """Record a cryptocurrency deposit transaction and update holdings"""
        try:
            logger.info(f"Processing crypto deposit: user_id={user_id}, asset={asset_symbol}, amount={amount}, tx_hash={tx_hash}")
            
            # Convert amount to Decimal
            try:
                amount = Decimal(str(amount))
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid amount format: {amount}")
            
            if amount <= Decimal('0'):
                raise ValueError("Deposit amount must be positive")

            asset = Asset.query.filter_by(
                symbol=asset_symbol,
                asset_type=AssetType.CRYPTO,
                deleted_at=None
            ).first()
            
            if not asset:
                raise ValueError(f"Crypto asset {asset_symbol} not found")

            # Create transaction
            transaction = Transaction(
                user_id=user_id,
                asset_id=asset.id,
                tx_type=TransactionType.DEPOSIT,
                amount=amount,
                timestamp=datetime.utcnow(),
                external_tx_id=tx_hash,  # Store blockchain transaction hash
                notes="Cryptocurrency deposit"
            )

            # Update or create holding
            holding = WalletService._get_or_create_holding(user_id, asset.id)
            holding.balance += amount

            try:
                db.session.add(transaction)
                db.session.commit()
                logger.info(f"Successfully processed deposit: transaction_id={transaction.id}")
                return transaction
            except IntegrityError as e:
                logger.error(f"Database integrity error during deposit: {str(e)}")
                db.session.rollback()
                raise ValueError("Failed to process crypto deposit due to database error")
            except Exception as e:
                logger.error(f"Unexpected database error during deposit: {str(e)}", exc_info=True)
                db.session.rollback()
                raise ValueError("Failed to process crypto deposit")
                
        except ValueError as e:
            logger.error(f"Value error in deposit_crypto: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in deposit_crypto: {str(e)}", exc_info=True)
            raise ValueError("An unexpected error occurred while processing the deposit")

    @staticmethod
    def get_recent_crypto_deposits(user_id, limit=5):
        """
        Fetch the user’s last `limit` crypto‐deposit transactions,
        ordered newest first.
        """
        return Transaction.query \
            .filter_by(user_id=user_id, tx_type=TransactionType.DEPOSIT) \
            .order_by(desc(Transaction.timestamp)) \
            .limit(limit) \
            .all()
    
    @staticmethod
    def deposit_fiat(user_id, asset_symbol, amount, reference=None):
        """Record a fiat currency deposit transaction and update holdings"""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        asset = Asset.query.filter_by(
            symbol=asset_symbol,
            asset_type=AssetType.FIAT,
            deleted_at=None
        ).first()
        
        if not asset:
            raise ValueError(f"Fiat asset {asset_symbol} not found")

        # Create transaction
        transaction = Transaction(
            user_id=user_id,
            asset_id=asset.id,
            tx_type=TransactionType.DEPOSIT,
            amount=amount,
            timestamp=datetime.utcnow(),
            external_tx_id=reference,  # Store bank reference or payment ID
            notes="Fiat currency deposit"
        )

        # Update or create holding
        holding = WalletService._get_or_create_holding(user_id, asset.id)
        holding.balance += amount

        try:
            db.session.add(transaction)
            db.session.commit()
            return transaction
        except IntegrityError:
            db.session.rollback()
            raise ValueError("Failed to process fiat deposit")

    # ********** Withdraw **********
    @staticmethod
    def withdraw_crypto(user_id, asset_symbol, amount, destination_address):
        """Process cryptocurrency withdrawal with blockchain integration"""
        # Get asset and validate
        asset = Asset.query.filter_by(
            symbol=asset_symbol,
            asset_type=AssetType.CRYPTO,
            deleted_at=None
        ).first()
        if not asset:
            raise ValueError(f"Asset {asset_symbol} not found")

        # Get user's holding
        holding = Holding.query.filter_by(
            user_id=user_id,
            asset_id=asset.id,
            deleted_at=None
        ).first()
        if not holding or holding.balance < amount:
            raise ValueError("Insufficient balance")

        # TODO: Integrate with blockchain provider for actual withdrawal
        # This is where you'd interface with your node or custody provider
        # For now, we'll just record the transaction
        tx_hash = "pending"  # Replace with real TX hash from provider

        # Create withdrawal transaction
        transaction = Transaction(
            user_id=user_id,
            asset_id=asset.id,
            tx_type=TransactionType.WITHDRAW,
            amount=amount,
            external_tx_id=tx_hash,
            notes=f"Withdrawal to {destination_address}",
            timestamp=datetime.utcnow()
        )

        # Update holding
        holding.balance -= amount

        try:
            db.session.add(transaction)
            db.session.commit()
            return transaction
        except IntegrityError:
            db.session.rollback()
            raise ValueError("Failed to record withdrawal transaction")

    @staticmethod
    def get_recent_crypto_withdrawals(user_id, limit=5):
        return Transaction.query.filter_by(
            user_id=user_id,
            tx_type=TransactionType.WITHDRAW
        ).order_by(Transaction.timestamp.desc()).limit(limit).all()    
    @staticmethod
    def transfer(user_id, from_asset_symbol, to_asset_symbol, amount):
        """Record a transfer between assets and update holdings"""
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")

        from_asset = Asset.query.filter_by(symbol=from_asset_symbol, deleted_at=None).first()
        to_asset = Asset.query.filter_by(symbol=to_asset_symbol, deleted_at=None).first()

        if not from_asset or not to_asset:
            raise ValueError("One or both assets not found")

        # Check sufficient balance
        from_holding = Holding.query.filter_by(
            user_id=user_id,
            asset_id=from_asset.id,
            deleted_at=None
        ).first()

        if not from_holding or from_holding.balance < amount:
            raise ValueError("Insufficient balance")

        # Get current exchange rate
        exchange_rate = db.session.query(ExchangeRate).filter_by(
            base_asset_id=from_asset.id,
            quote_asset_id=to_asset.id,
            deleted_at=None
        ).order_by(ExchangeRate.timestamp.desc()).first()

        if not exchange_rate:
            raise ValueError("No exchange rate available for transfer")

        # Calculate amount in target asset
        target_amount = amount * exchange_rate.rate

        # Create transactions
        withdraw_tx = Transaction(
            user_id=user_id,
            asset_id=from_asset.id,
            tx_type=TransactionType.TRANSFER,
            amount=amount,
            quote_asset_id=to_asset.id,
            price=exchange_rate.rate,
            timestamp=datetime.utcnow()
        )

        deposit_tx = Transaction(
            user_id=user_id,
            asset_id=to_asset.id,
            tx_type=TransactionType.TRANSFER,
            amount=target_amount,
            quote_asset_id=from_asset.id,
            price=1/exchange_rate.rate,
            timestamp=datetime.utcnow()
        )

        # Update holdings
        from_holding.balance -= amount
        to_holding = WalletService._get_or_create_holding(user_id, to_asset.id)
        to_holding.balance += target_amount

        try:
            db.session.add(withdraw_tx)
            db.session.add(deposit_tx)
            db.session.commit()
            return withdraw_tx, deposit_tx
        except IntegrityError:
            db.session.rollback()
            raise ValueError("Failed to process transfer")
