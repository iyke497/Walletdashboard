# app/trading/services.py
from decimal import Decimal
from app.models import Asset, ExchangeRate, AssetType, Holding, TradeOrder
from app.wallet.services import WalletService
from app.extensions import db

class TradingService:
    @staticmethod
    def get_market_price(base_asset: Asset, quote_asset: Asset) -> Decimal:
        """Get latest market price from exchange rates"""
        rate = ExchangeRate.query.filter_by(
            base_asset_id=base_asset.id,
            quote_asset_id=quote_asset.id
        ).order_by(ExchangeRate.timestamp.desc()).first()
        
        if not rate:
            raise ValueError(f"No market price available for {base_asset.symbol}/{quote_asset.symbol}")
        return rate.rate

    @staticmethod
    def execute_market_order(user_id: int, base_asset: Asset, quote_asset: Asset, 
                            amount: Decimal, side: str) -> tuple:
        """
        Execute a market order
        Returns: (base_tx, quote_tx) transaction pair
        """
        # Validate order parameters
        if side not in ['buy', 'sell']:
            raise ValueError("Invalid order side. Must be 'buy' or 'sell'")
            
        if amount <= Decimal('0'):
            raise ValueError("Order amount must be positive")

        # Initialize asset direction
        from_asset = None
        to_asset = None

        # Get current market price
        price = TradingService.get_market_price(base_asset, quote_asset)
        
        # Calculate trade amounts and direction
        if side == 'buy':
            quote_amount = amount * price
            from_asset = quote_asset
            to_asset = base_asset
        else:  # sell
            quote_amount = amount / price
            from_asset = base_asset
            to_asset = quote_asset

        # Final validation before execution
        if not from_asset or not to_asset:
            raise RuntimeError("Asset direction not properly configured")

        # Create trade order record
        trade_order = TradeOrder(
            user_id=user_id,
            base_asset_id=base_asset.id,
            quote_asset_id=quote_asset.id,
            order_type='market',
            side=side,
            amount=amount,
            price=price,
            status='filled'
        )
        db.session.add(trade_order)

        # Execute the trade
        tx_pair = WalletService.transfer(
            user_id=user_id,
            from_asset_symbol=from_asset.symbol,
            to_asset_symbol=to_asset.symbol,
            amount=amount if side == 'sell' else quote_amount
        )

        # Commit the trade order
        db.session.commit()

        return tx_pair