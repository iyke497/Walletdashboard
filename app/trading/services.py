# app/trading/services.py
from decimal import Decimal
from app.models import Asset, ExchangeRate, AssetType, Holding, TradeOrder, OrderBook
from app.wallet.services import WalletService
from app.extensions import db
from typing import List, Dict

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
        print(f"Executing market order - User: {user_id}, Base: {base_asset.symbol}, Quote: {quote_asset.symbol}, Amount: {amount}, Side: {side}")  # Debug log
        
        # Validate order parameters
        if side not in ['buy', 'sell']:
            raise ValueError("Invalid order side. Must be 'buy' or 'sell'")
            
        if amount <= Decimal('0'):
            raise ValueError("Order amount must be positive")

        # Initialize asset direction
        from_asset = None
        to_asset = None

        # Get current market price
        try:
            price = TradingService.get_market_price(base_asset, quote_asset)
            print(f"Current market price: {price}")  # Debug log
        except Exception as e:
            print(f"Error getting market price: {e}")  # Debug log
            raise
        
        # Calculate trade amounts and direction
        if side == 'buy':
            quote_amount = amount * price
            from_asset = quote_asset
            to_asset = base_asset
        else:  # sell
            quote_amount = amount / price
            from_asset = base_asset
            to_asset = quote_asset

        print(f"Trade calculation - From: {from_asset.symbol}, To: {to_asset.symbol}, Amount: {amount}, Quote Amount: {quote_amount}")  # Debug log

        # Final validation before execution
        if not from_asset or not to_asset:
            raise RuntimeError("Asset direction not properly configured")

        # Create trade order record
        try:
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
            print("Trade order record created")  # Debug log
        except Exception as e:
            print(f"Error creating trade order: {e}")  # Debug log
            raise

        # Execute the trade
        try:
            tx_pair = WalletService.transfer(
                user_id=user_id,
                from_asset_symbol=from_asset.symbol,
                to_asset_symbol=to_asset.symbol,
                amount=amount if side == 'sell' else quote_amount
            )
            print(f"Transfer executed successfully: {tx_pair}")  # Debug log
        except Exception as e:
            print(f"Error executing transfer: {e}")  # Debug log
            db.session.rollback()
            raise

        # Commit the trade order
        try:
            db.session.commit()
            print("Trade order committed to database")  # Debug log
        except Exception as e:
            print(f"Error committing trade order: {e}")  # Debug log
            db.session.rollback()
            raise

        return tx_pair
    
class OrderBookService:
    @staticmethod
    def get_order_book(base_asset_id: int, quote_asset_id: int, limit: int = 20) -> Dict:
        """Get order book for a trading pair"""
        # Get active buy orders (sorted by highest price first)
        buy_orders = OrderBook.query.filter_by(
            base_asset_id=base_asset_id,
            quote_asset_id=quote_asset_id,
            side='buy',
            status='open'
        ).order_by(OrderBook.price.desc()).limit(limit).all()

        # Get active sell orders (sorted by lowest price first)
        sell_orders = OrderBook.query.filter_by(
            base_asset_id=base_asset_id,
            quote_asset_id=quote_asset_id,
            side='sell',
            status='open'
        ).order_by(OrderBook.price.asc()).limit(limit).all()

        return {
            'bids': [{
                'price': str(order.price),
                'amount': str(order.amount),
                'total': str(order.price * order.amount)
            } for order in buy_orders],
            'asks': [{
                'price': str(order.price),
                'amount': str(order.amount),
                'total': str(order.price * order.amount)
            } for order in sell_orders]
        }

    @staticmethod
    def place_limit_order(user_id: int, base_asset: Asset, quote_asset: Asset,
                         amount: Decimal, price: Decimal, side: str) -> OrderBook:
        """Place a limit order in the order book"""
        if side not in ['buy', 'sell']:
            raise ValueError("Invalid order side. Must be 'buy' or 'sell'")
            
        if amount <= Decimal('0') or price <= Decimal('0'):
            raise ValueError("Amount and price must be positive")

        # Create order book entry
        order = OrderBook(
            user_id=user_id,
            base_asset_id=base_asset.id,
            quote_asset_id=quote_asset.id,
            order_type='limit',
            side=side,
            amount=amount,
            price=price,
            status='open'
        )
        db.session.add(order)
        db.session.commit()

        # Try to match the order
        OrderBookService.match_orders(base_asset.id, quote_asset.id)

        return order

    @staticmethod
    def match_orders(base_asset_id: int, quote_asset_id: int):
        """Match open orders in the order book"""
        # Get highest buy order
        buy_order = OrderBook.query.filter_by(
            base_asset_id=base_asset_id,
            quote_asset_id=quote_asset_id,
            side='buy',
            status='open'
        ).order_by(OrderBook.price.desc()).first()

        # Get lowest sell order
        sell_order = OrderBook.query.filter_by(
            base_asset_id=base_asset_id,
            quote_asset_id=quote_asset_id,
            side='sell',
            status='open'
        ).order_by(OrderBook.price.asc()).first()

        # If no matching orders, return
        if not buy_order or not sell_order or buy_order.price < sell_order.price:
            return

        # Determine trade amount (minimum of both orders)
        trade_amount = min(buy_order.amount, sell_order.amount)
        trade_price = sell_order.price  # Use sell order price for execution

        try:
            # Execute the trade
            tx_pair = WalletService.transfer(
                user_id=buy_order.user_id,
                from_asset_symbol=quote_asset.symbol,
                to_asset_symbol=base_asset.symbol,
                amount=trade_amount * trade_price
            )

            tx_pair = WalletService.transfer(
                user_id=sell_order.user_id,
                from_asset_symbol=base_asset.symbol,
                to_asset_symbol=quote_asset.symbol,
                amount=trade_amount
            )

            # Update order amounts
            buy_order.amount -= trade_amount
            sell_order.amount -= trade_amount

            # Close orders if fully filled
            if buy_order.amount == Decimal('0'):
                buy_order.status = 'filled'
            if sell_order.amount == Decimal('0'):
                sell_order.status = 'filled'

            # Create trade records
            TradeOrder(
                user_id=buy_order.user_id,
                base_asset_id=base_asset_id,
                quote_asset_id=quote_asset_id,
                order_type='limit',
                side='buy',
                amount=trade_amount,
                price=trade_price,
                status='filled'
            )

            TradeOrder(
                user_id=sell_order.user_id,
                base_asset_id=base_asset_id,
                quote_asset_id=quote_asset_id,
                order_type='limit',
                side='sell',
                amount=trade_amount,
                price=trade_price,
                status='filled'
            )

            db.session.commit()

            # Recursively match remaining orders
            OrderBookService.match_orders(base_asset_id, quote_asset_id)

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def cancel_order(user_id: int, order_id: int) -> bool:
        """Cancel an open order"""
        order = OrderBook.query.filter_by(
            id=order_id,
            user_id=user_id,
            status='open'
        ).first()

        if not order:
            return False

        order.status = 'cancelled'
        db.session.commit()
        return True 
 