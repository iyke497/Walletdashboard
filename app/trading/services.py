# app/trading/services.py
import ccxt
import pandas as pd
import time
from decimal import Decimal
from app.models import Asset, ExchangeRate, AssetType, Holding, TradeOrder, OrderBook
from app.wallet.services import WalletService
from app.extensions import db
from typing import List, Dict
from app.config import BaseConfig

class ExchangeService:
    def __init__(self):
        """Initialize exchange with configuration"""
        self.exchange = ccxt.binance({
            'apiKey': BaseConfig.EXCHANGE_API_KEY,
            'secret': BaseConfig.EXCHANGE_SECRET_KEY,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True
            }
        })

    def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """Get order book from exchange"""
        try:
            return self.exchange.fetch_order_book(symbol, limit)
        except Exception as e:
            print(f"Error fetching order book: {e}")
            raise

    def get_ticker(self, symbol: str) -> Dict:
        """Get current ticker information"""
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            print(f"Error fetching ticker: {e}")
            raise

    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List:
        """Get OHLCV data for a symbol"""
        try:
            return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            print(f"Error fetching OHLCV data: {e}")
            raise

    def create_order(self, symbol: str, order_type: str, side: str, amount: float, price: float = None) -> Dict:
        """Create a new order"""
        try:
            return self.exchange.create_order(symbol, order_type, side, amount, price)
        except Exception as e:
            print(f"Error creating order: {e}")
            raise

    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """Cancel an existing order"""
        try:
            return self.exchange.cancel_order(order_id, symbol)
        except Exception as e:
            print(f"Error canceling order: {e}")
            raise

    def get_order(self, order_id: str, symbol: str) -> Dict:
        """Get order details"""
        try:
            return self.exchange.fetch_order(order_id, symbol)
        except Exception as e:
            print(f"Error fetching order: {e}")
            raise

    def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """Get all open orders"""
        try:
            return self.exchange.fetch_open_orders(symbol)
        except Exception as e:
            print(f"Error fetching open orders: {e}")
            raise

# Create a singleton instance
exchange_service = ExchangeService()

class OrderBookService:
    @staticmethod
    def get_order_book(base_asset_id: int, quote_asset_id: int, limit: int = 5) -> Dict:
        """Get order book for a trading pair"""
        # Get assets
        base_asset = Asset.query.get(base_asset_id)
        quote_asset = Asset.query.get(quote_asset_id)
        
        if not base_asset or not quote_asset:
            raise ValueError("Invalid asset IDs")
            
        symbol = f"{base_asset.symbol.upper()}/{quote_asset.symbol.upper()}"
        
        try:
            # Get order book from exchange
            exchange_order_book = exchange_service.get_order_book(symbol, limit)

            # Calculate mid price
            mid_price = (exchange_order_book['bids'][0][0] + exchange_order_book['asks'][0][0]) / 2

            asks = []
            max_amount = max([amount for price, amount in exchange_order_book['asks']] or [0])
            for price, amount in exchange_order_book['asks']:
                asks.append({
                    'price': price,
                    'amount': amount,
                    'total': amount * price,
                    'depth': 100 * float(amount) / float(max_amount) if max_amount else 0
                })

            bids = []
            max_amount = max([amount for price, amount in exchange_order_book['bids']] or [0])
            for price, amount in exchange_order_book['bids']:
                bids.append({
                    'price': price,
                    'amount': amount,
                    'total': amount * price,
                    'depth': 100 * float(amount) / float(max_amount) if max_amount else 0    
                })

            # Format the response
            return {
                'bids': bids,
                'asks': asks,
                'mid_price': mid_price
            }
        except Exception as e:
            print(f"Error getting order book from exchange: {e}")
            # Fallback to database order book if exchange fails
            return "Error in Order book service"

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
    
    @staticmethod
    def get_ticker(base_asset: Asset, quote_asset: Asset) -> Decimal:
        """Get latest ticker information from exchange service"""
        print(base_asset)
        symbol = f"{base_asset.symbol.upper()}/{quote_asset.symbol.upper()}"
        ticker = exchange_service.get_ticker(symbol)
        return ticker
    
    @staticmethod
    def get_ohlcv(base_asset: Asset, quote_asset: Asset, timeframe: str = '1h', limit: int = 100) -> List:
        """Get OHLCV data for a trading pair"""
        symbol = f"{base_asset.symbol}/{quote_asset.symbol}"
        return exchange_service.get_ohlcv(symbol, timeframe, limit)

