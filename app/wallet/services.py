from datetime import datetime
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from app.models import User, Transaction, Asset, Holding, TransactionType, AssetType, ExchangeRate, TransactionStatus
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

    # TODO: Delete
    @staticmethod
    def generate_qr_png(data: str) -> BytesIO:
        """
        Generate a QR code for a deposit address.
        
        Args:
            deposit_address: The DepositAddress object containing the address to encode
            
        Returns:
            BytesIO: A buffer containing the PNG image data
        """
        if not data:
            raise ValueError("Invalid deposit address")
            
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        # Generate image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to buffer
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        
        return buffer

    @staticmethod
    def get_deposit_info(asset_symbol: str, network_id: str):
        """Return address & metadata for the pair."""
        asset = Asset.query.filter_by(symbol=asset_symbol,
                                      asset_type=AssetType.CRYPTO,
                                      deleted_at=None).first()
        if not asset:
            raise ValueError(f"{asset_symbol} not found")

        record = next(
            (n for n in (asset.networks or []) if n["id"] == network_id),
            None
        )
        if not record:
            raise ValueError(f"{asset_symbol} is not supported on {network_id}")

        return record   # whole dict

    @staticmethod
    def deposit_crypto_old(user_id, asset_symbol, amount, tx_hash=None):
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
    def deposit_crypto(user_id, asset_symbol, amount, tx_hash=None):
        """Record a cryptocurrency deposit - ALWAYS PENDING"""
        try:
            amount = Decimal(str(amount))
            if amount <= Decimal('0'):
                raise ValueError("Deposit amount must be positive")

            asset = Asset.query.filter_by(
                symbol=asset_symbol,
                asset_type=AssetType.CRYPTO,
                deleted_at=None
            ).first()
            
            if not asset:
                raise ValueError(f"Crypto asset {asset_symbol} not found")
            

            # Create transaction as PENDING - DON'T update holdings yet
            transaction = Transaction(
                user_id=user_id,
                asset_id=asset.id,
                tx_type=TransactionType.DEPOSIT,
                amount=amount,
                status=TransactionStatus.PENDING,  # Always pending
                timestamp=datetime.utcnow(),
                external_tx_id=tx_hash,
                notes="Cryptocurrency deposit"
            )

            # DON'T update holdings - that happens when admin confirms
            
            db.session.add(transaction)
            db.session.commit()
            logger.info(f"Deposit created as PENDING: transaction_id={transaction.id}")
            return transaction
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating deposit: {str(e)}")
            raise ValueError(f"Failed to process deposit: {str(e)}")

    @staticmethod
    def get_recent_crypto_deposits_old(user_id, limit=5):
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
    def get_recent_crypto_deposits(user_id, limit=None):
        """
        Fetch the user's crypto deposit transactions,
        ordered newest first. If limit is None, fetch all deposits.
        """
        
        query = Transaction.query \
            .options(joinedload(Transaction.asset)) \
            .filter_by(user_id=user_id, tx_type=TransactionType.DEPOSIT) \
            .order_by(desc(Transaction.timestamp))
        
        if limit:
            query = query.limit(limit)
        
        return query.all()


    @staticmethod
    def get_user_deposits(user_id, limit=None):
        """
        Simple method to fetch user deposits with asset info
        """
        
        query = db.session.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.tx_type == TransactionType.DEPOSIT
        ).order_by(Transaction.timestamp.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()


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

        # Add input validation
        if not isinstance(amount, Decimal):
            raise ValueError("Amount must be a Decimal type")
        
        if amount <= Decimal('0'):
            raise ValueError("Withdrawal amount must be positive")

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

    @staticmethod
    def confirm_deposit(transaction_id):
        """Confirm pending deposit and update holdings"""
        try:
            transaction = Transaction.query.filter_by(
                id=transaction_id,
                tx_type=TransactionType.DEPOSIT,
                status=TransactionStatus.PENDING
            ).first()
            
            if not transaction:
                raise ValueError("Pending deposit not found")
            
            # Update status
            transaction.status = TransactionStatus.SUCCESS
            
            # NOW update holdings
            holding = WalletService._get_or_create_holding(transaction.user_id, transaction.asset_id)
            holding.balance += transaction.amount
            
            db.session.commit()
            logger.info(f"Deposit confirmed: transaction_id={transaction_id}, amount={transaction.amount}")
            return transaction
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error confirming deposit: {str(e)}")
            raise ValueError(f"Failed to confirm deposit: {str(e)}")
        
    # Add these methods to your WalletService class

    @staticmethod
    def transfer_between_users(sender_id, recipient_email, asset_id, amount, note=None):
        """
        Transfer funds between Bloxxxchain users
        """

        try:
            # Validate inputs
            amount = Decimal(str(amount))
            if amount <= 0:
                raise ValueError("Transfer amount must be greater than 0")
            
            # Get sender (current user)
            sender = User.query.get(sender_id)
            if not sender:
                raise ValueError("Sender not found")
            
            # Get recipient
            recipient = User.query.filter_by(email=recipient_email.lower()).first()
            if not recipient:
                raise ValueError("Recipient not found")
            
            if sender.id == recipient.id:
                raise ValueError("Cannot transfer to yourself")
            
            # Validate recipient is active and verified
            if not recipient.is_active:
                raise ValueError("Recipient account is not active")
            
            if not recipient.email_verified:
                raise ValueError("Recipient must verify their email to receive transfers")
            
            # Get asset
            asset = Asset.query.get(asset_id)
            if not asset or not asset.is_active:
                raise ValueError("Invalid asset")
            
            # Check sender's balance
            sender_holding = Holding.query.filter_by(
                user_id=sender_id,
                asset_id=asset_id
            ).first()
            
            if not sender_holding or sender_holding.balance < amount:
                raise ValueError("Insufficient balance")
            
            # Begin transaction
            # Deduct from sender
            sender_holding.balance -= amount
            
            # Add to recipient (create holding if doesn't exist)
            recipient_holding = Holding.query.filter_by(
                user_id=recipient.id,
                asset_id=asset_id
            ).first()
            
            if recipient_holding:
                recipient_holding.balance += amount
            else:
                recipient_holding = Holding(
                    user_id=recipient.id,
                    asset_id=asset_id,
                    balance=amount
                )
                db.session.add(recipient_holding)
            
            # Create transaction records
            # Outgoing transaction for sender
            sender_transaction = Transaction(
                user_id=sender_id,
                asset_id=asset_id,
                tx_type=TransactionType.TRANSFER_OUT,
                amount=amount,
                status=TransactionStatus.SUCCESS,
                notes=f"Transfer to {recipient.email}" + (f" - {note}" if note else ""),
                timestamp=datetime.utcnow()
            )
            
            # Incoming transaction for recipient
            recipient_transaction = Transaction(
                user_id=recipient.id,
                asset_id=asset_id,
                tx_type=TransactionType.TRANSFER_IN,
                amount=amount,
                status=TransactionStatus.SUCCESS,
                notes=f"Transfer from {sender.email}" + (f" - {note}" if note else ""),
                timestamp=datetime.utcnow()
            )
            
            db.session.add(sender_transaction)
            db.session.add(recipient_transaction)
            
            # Commit all changes
            db.session.commit()
            
            return {
                'success': True,
                'sender_transaction': sender_transaction,
                'recipient_transaction': recipient_transaction,
                'message': f'Successfully transferred {amount} {asset.symbol.upper()} to {recipient.email}'
            }
            
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_transfer_preview(sender_id, recipient_email, asset_id, amount):
        """
        Get transfer preview without executing the transfer
        """
        
        try:
            amount = Decimal(str(amount))
            
            # Get recipient info
            recipient = User.query.filter_by(email=recipient_email.lower()).first()
            if not recipient:
                raise ValueError("Recipient not found")
            
            # Get asset info
            asset = Asset.query.get(asset_id)
            if not asset:
                raise ValueError("Asset not found")
            
            # Get sender's balance
            sender_holding = Holding.query.filter_by(
                user_id=sender_id,
                asset_id=asset_id
            ).first()
            
            current_balance = sender_holding.balance if sender_holding else Decimal('0')
            remaining_balance = current_balance - amount
            
            return {
                'recipient_email': recipient.email,
                'recipient_name': f"{recipient.first_name} {recipient.last_name}" if recipient.first_name else recipient.email,
                'asset_symbol': asset.symbol.upper(),
                'asset_name': asset.name,
                'transfer_amount': amount,
                'current_balance': current_balance,
                'remaining_balance': remaining_balance,
                'fees': Decimal('0'),  # No fees for internal transfers
                'total_deducted': amount
            }
            
        except Exception as e:
            raise e

    @staticmethod
    def get_user_transfers(user_id, limit=None):
        """
        Get user's transfer history (both sent and received)
        """
        
        query = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.tx_type.in_([TransactionType.TRANSFER_IN, TransactionType.TRANSFER_OUT])
        ).order_by(Transaction.timestamp.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
