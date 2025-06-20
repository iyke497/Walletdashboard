# app/trading/services.py
from flask import current_app, request
from flask_login import current_user
import ccxt
import requests
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal,  ROUND_DOWN
from app.models import Asset, ExchangeRate, AssetType, Holding, TradeOrder, OrderBook, Transaction, TransactionType
from app.wallet.services import WalletService
from app.extensions import db
from typing import List, Dict, Optional, Tuple
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


class SwapError(Exception):
    """Custom exception for swap-related errors"""
    pass


class CryptoSwapService:
    """Service class for handling crypto swap operations"""

    @staticmethod
    def fetch_live_exchange_rate(from_asset_id: int, to_asset_id: int) -> Optional[Decimal]:
        """
        Fetch live exchange rate from external API (CoinGecko)
        Returns rate where 1 unit of from_asset = rate units of to_asset
        """
        try:
            # Get assets from database to access coingecko_id
            from_asset = Asset.query.get(from_asset_id)
            to_asset = Asset.query.get(to_asset_id)
            
            if not from_asset or not to_asset:
                current_app.logger.error(f"Asset not found: from_asset_id={from_asset_id}, to_asset_id={to_asset_id}")
                return None
            
            if not from_asset.coingecko_id or not to_asset.coingecko_id:
                current_app.logger.warning(f"Missing coingecko_id: {from_asset.symbol}={from_asset.coingecko_id}, {to_asset.symbol}={to_asset.coingecko_id}")
                return None
            
            from_id = from_asset.coingecko_id
            to_id = to_asset.coingecko_id
            
            # First attempt: Direct conversion
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': from_id,
                'vs_currencies': to_id,
                'precision': 18
            }
            
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if from_id in data and to_id in data[from_id]:
                    rate = Decimal(str(data[from_id][to_id]))
                    current_app.logger.info(f"Fetched direct rate: {from_asset.symbol}/{to_asset.symbol} = {rate}")
                    return rate
            except Exception:
                # We'll try alternative methods if direct fails
                pass
            
            # Second attempt: Conversion via USD
            usd_asset = Asset.query.filter_by(symbol='USD').first()
            if usd_asset and usd_asset.coingecko_id:
                # Get both rates against USD in a single API call
                url_usd = "https://api.coingecko.com/api/v3/simple/price"
                params_usd = {
                    'ids': f"{from_id},{to_id}",
                    'vs_currencies': 'usd',
                    'precision': 18
                }
                
                try:
                    response_usd = requests.get(url_usd, params=params_usd, timeout=10)
                    response_usd.raise_for_status()
                    data_usd = response_usd.json()
                    
                    if (from_id in data_usd and 'usd' in data_usd[from_id] and 
                        to_id in data_usd and 'usd' in data_usd[to_id]):
                        
                        from_usd_price = Decimal(str(data_usd[from_id]['usd']))
                        to_usd_price = Decimal(str(data_usd[to_id]['usd']))
                        
                        if to_usd_price > 0:
                            rate = from_usd_price / to_usd_price
                            current_app.logger.info(f"Calculated cross rate via USD: {from_asset.symbol}/{to_asset.symbol} = {rate}")
                            return rate
                except Exception as e:
                    current_app.logger.warning(f"USD conversion failed: {str(e)}")
            
            # Final fallback: Try recursive USD conversion
            if usd_asset and usd_asset.coingecko_id and to_asset_id != usd_asset.id:
                try:
                    from_usd_rate = CryptoSwapService.fetch_live_exchange_rate(from_asset_id, usd_asset.id)
                    to_usd_rate = CryptoSwapService.fetch_live_exchange_rate(to_asset_id, usd_asset.id)
                    
                    if from_usd_rate and to_usd_rate and to_usd_rate > 0:
                        rate = from_usd_rate / to_usd_rate
                        current_app.logger.info(f"Calculated recursive rate via USD: {from_asset.symbol}/{to_asset.symbol} = {rate}")
                        return rate
                except Exception as e:
                    current_app.logger.warning(f"Recursive USD conversion failed: {str(e)}")
            
            current_app.logger.warning(f"No rate data available for {from_asset.symbol}/{to_asset.symbol}")
            return None
            
        except Exception as e:
            current_app.logger.error(f"Failed to fetch live rate for asset IDs {from_asset_id}/{to_asset_id}: {str(e)}")
            return None    
    
    @staticmethod
    def store_exchange_rate(from_asset_id: int, to_asset_id: int, rate: Decimal, source: str = "live_api"):
        """Store exchange rate in database for future use"""
        try:
            exchange_rate = ExchangeRate(
                base_asset_id=from_asset_id,
                quote_asset_id=to_asset_id,
                rate=rate,
                timestamp=datetime.utcnow(),
                source=source
            )
            db.session.add(exchange_rate)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Failed to store exchange rate: {str(e)}")
            db.session.rollback()
    
    @staticmethod
    def get_exchange_rate(from_asset_id: int, to_asset_id: int, fetch_live: bool = True) -> Optional[Decimal]:
        """
        Get exchange rate between two assets with live fetching capability
        Returns rate where 1 unit of from_asset = rate units of to_asset
        """
        if from_asset_id == to_asset_id:
            return Decimal('1')
        
        from_asset = Asset.query.get(from_asset_id)
        to_asset = Asset.query.get(to_asset_id)
        
        if not from_asset or not to_asset:
            return None
        
        # Try to get recent rate from database first (within last 5 minutes)
        recent_cutoff = datetime.utcnow() - timedelta(minutes=5)
        
        # Try direct rate
        recent_rate = ExchangeRate.query.filter_by(
            base_asset_id=from_asset_id,
            quote_asset_id=to_asset_id
        ).filter(
            ExchangeRate.timestamp >= recent_cutoff
        ).order_by(ExchangeRate.timestamp.desc()).first()
        
        if recent_rate:
            current_app.logger.info(f"Using recent cached rate: {from_asset.symbol}/{to_asset.symbol} = {recent_rate.rate}")
            return recent_rate.rate
        
        # Try inverse rate
        recent_inverse = ExchangeRate.query.filter_by(
            base_asset_id=to_asset_id,
            quote_asset_id=from_asset_id
        ).filter(
            ExchangeRate.timestamp >= recent_cutoff
        ).order_by(ExchangeRate.timestamp.desc()).first()
        
        if recent_inverse and recent_inverse.rate > 0:
            rate = Decimal('1') / recent_inverse.rate
            current_app.logger.info(f"Using recent cached inverse rate: {from_asset.symbol}/{to_asset.symbol} = {rate}")
            return rate
        
        # If no recent rate and live fetching is enabled, fetch from API
        if fetch_live:
            live_rate = CryptoSwapService.fetch_live_exchange_rate(from_asset_id, to_asset_id)
            if live_rate:
                # Store the fetched rate for future use
                CryptoSwapService.store_exchange_rate(from_asset_id, to_asset_id, live_rate, "coingecko_api")
                return live_rate
        
        # Fallback to any available rate (even if older)
        fallback_rate = ExchangeRate.query.filter_by(
            base_asset_id=from_asset_id,
            quote_asset_id=to_asset_id
        ).order_by(ExchangeRate.timestamp.desc()).first()
        
        if fallback_rate:
            current_app.logger.warning(f"Using older cached rate: {from_asset.symbol}/{to_asset.symbol} = {fallback_rate.rate}")
            return fallback_rate.rate
        
        # Try fallback inverse rate
        fallback_inverse = ExchangeRate.query.filter_by(
            base_asset_id=to_asset_id,
            quote_asset_id=from_asset_id
        ).order_by(ExchangeRate.timestamp.desc()).first()
        
        if fallback_inverse and fallback_inverse.rate > 0:
            rate = Decimal('1') / fallback_inverse.rate
            current_app.logger.warning(f"Using older cached inverse rate: {from_asset.symbol}/{to_asset.symbol} = {rate}")
            return rate
        
        current_app.logger.error(f"No exchange rate available for {from_asset.symbol}/{to_asset.symbol}")
        return None
    
    @staticmethod
    def get_user_crypto_holdings(user_id: int) -> list:
        """Get user's crypto holdings with positive balance"""
        return db.session.query(Holding, Asset).join(Asset).filter(
            Holding.user_id == user_id,
            Holding.balance > 0,
            Asset.is_active == True,
            Asset.asset_type == AssetType.CRYPTO
        ).order_by(Asset.symbol).all()
    
    @staticmethod
    def get_available_crypto_assets() -> list:
        """Get all active crypto assets"""
        return Asset.query.filter(
            Asset.is_active == True,
            Asset.asset_type == AssetType.CRYPTO
        ).order_by(Asset.symbol).all()
    
    @staticmethod
    def get_user_balance(user_id: int, asset_id: int) -> Decimal:
        """Get user's balance for a specific asset"""
        holding = Holding.query.filter_by(
            user_id=user_id, 
            asset_id=asset_id
        ).first()
        return holding.balance if holding else Decimal('0')
    
    # @staticmethod
    # def get_exchange_rate(from_asset_id: int, to_asset_id: int) -> Optional[Decimal]:
    #     """
    #     Get exchange rate between two assets
    #     Returns rate where 1 unit of from_asset = rate units of to_asset
    #     """
    #     if from_asset_id == to_asset_id:
    #         return Decimal('1')
        
    #     # Try direct rate
    #     rate = ExchangeRate.query.filter_by(
    #         base_asset_id=from_asset_id,
    #         quote_asset_id=to_asset_id
    #     ).order_by(ExchangeRate.timestamp.desc()).first()
        
    #     if rate:
    #         return rate.rate
        
    #     # Try inverse rate
    #     inverse_rate = ExchangeRate.query.filter_by(
    #         base_asset_id=to_asset_id,
    #         quote_asset_id=from_asset_id
    #     ).order_by(ExchangeRate.timestamp.desc()).first()
        
    #     if inverse_rate and inverse_rate.rate > 0:
    #         return Decimal('1') / inverse_rate.rate
        
    #     return None
    
    @staticmethod
    def calculate_swap_preview(from_asset_id: int, to_asset_id: int, 
                             from_amount: Decimal, fee_percentage: Decimal = Decimal('0.001')) -> Dict:
        """Calculate swap preview including fees with live rate fetching"""
        from_asset = Asset.query.get(from_asset_id)
        to_asset = Asset.query.get(to_asset_id)
        
        if not from_asset or not to_asset:
            raise SwapError("Asset not found")
        
        # Fetch live rate (this will try live API if no recent cached rate)
        rate = CryptoSwapService.get_exchange_rate(from_asset_id, to_asset_id, fetch_live=True)
        if not rate:
            # If live fetch fails, try with a simulated rate for common pairs
            rate = CryptoSwapService._get_fallback_rate(from_asset_id, to_asset_id)
            if not rate:
                raise SwapError(f"Exchange rate not available for {from_asset.symbol}/{to_asset.symbol}")
        
        # Calculate amounts
        fee_amount = from_amount * fee_percentage
        net_from_amount = from_amount - fee_amount
        net_to_amount = net_from_amount * rate
        
        return {
            'from_asset': from_asset,
            'to_asset': to_asset,
            'from_amount': from_amount,
            'rate': rate,
            'fee_amount': fee_amount,
            'fee_percentage': fee_percentage * 100,
            'net_to_amount': net_to_amount,
        }
    
    @staticmethod
    def _get_fallback_rate(from_asset_id: int, to_asset_id: int) -> Optional[Decimal]:
        """
        Provide fallback rates for common trading pairs when API fails
        This is just for demo purposes - in production you'd want better fallback logic
        """
        from_asset = Asset.query.get(from_asset_id)
        to_asset = Asset.query.get(to_asset_id)
        
        if not from_asset or not to_asset:
            return None
        
        # Approximate rates for testing (you can update these or remove this method)
        fallback_rates = {
            ('ETH', 'BTC'): Decimal('0.065'),
            ('BTC', 'ETH'): Decimal('15.38'),
            ('ETH', 'USDT'): Decimal('2000'),
            ('USDT', 'ETH'): Decimal('0.0005'),
            ('BTC', 'USDT'): Decimal('30000'),
            ('USDT', 'BTC'): Decimal('0.000033'),
            ('ARB', 'ETH'): Decimal('0.0005'),
            ('ETH', 'ARB'): Decimal('2000'),
            ('ARB', 'USDT'): Decimal('1.0'),
            ('USDT', 'ARB'): Decimal('1.0'),
        }
        
        key = (from_asset.symbol.upper(), to_asset.symbol.upper())
        if key in fallback_rates:
            current_app.logger.warning(f"Using fallback rate for {from_asset.symbol}/{to_asset.symbol}")
            return fallback_rates[key]
        
        return None
    
    @staticmethod
    def validate_swap(user_id: int, from_asset_id: int, to_asset_id: int, 
                     from_amount: Decimal) -> Tuple[bool, str]:
        """Validate if swap can be executed"""
        if from_asset_id == to_asset_id:
            return False, "Cannot swap asset to itself"
        
        if from_amount <= 0:
            return False, "Amount must be positive"
        
        # Check assets exist
        from_asset = Asset.query.get(from_asset_id)
        to_asset = Asset.query.get(to_asset_id)
        
        if not from_asset or not to_asset:
            return False, "Asset not found"
        
        if not from_asset.is_active or not to_asset.is_active:
            return False, "Asset not available for trading"
        
        # Check balance
        user_balance = CryptoSwapService.get_user_balance(user_id, from_asset_id)
        if user_balance < from_amount:
            return False, f"Insufficient {from_asset.symbol} balance"
        
        # Check exchange rate (with live fetching)
        rate = CryptoSwapService.get_exchange_rate(from_asset_id, to_asset_id, fetch_live=True)
        if not rate:
            # Try fallback rate
            rate = CryptoSwapService._get_fallback_rate(from_asset_id, to_asset_id)
            if not rate:
                return False, f"Exchange rate not available for {from_asset.symbol}/{to_asset.symbol}"
        
        return True, ""
    
    @staticmethod
    def execute_swap(user_id: int, from_asset_id: int, to_asset_id: int, 
                    from_amount: Decimal, fee_percentage: Decimal = Decimal('0.001')) -> Dict:
        """Execute the crypto swap transaction"""
        # Validate swap
        is_valid, error_msg = CryptoSwapService.validate_swap(
            user_id, from_asset_id, to_asset_id, from_amount
        )
        
        if not is_valid:
            raise SwapError(error_msg)
        
        # Calculate swap details
        swap_preview = CryptoSwapService.calculate_swap_preview(
            from_asset_id, to_asset_id, from_amount, fee_percentage
        )
        
        try:
            # Update holdings
            CryptoSwapService._update_holding(user_id, from_asset_id, -from_amount)
            CryptoSwapService._update_holding(user_id, to_asset_id, swap_preview['net_to_amount'])
            
            # Create sell transaction
            sell_transaction = Transaction(
                user_id=user_id,
                asset_id=from_asset_id,
                tx_type=TransactionType.TRADE_SELL,
                amount=from_amount,
                fee_amount=swap_preview['fee_amount'],
                fee_asset_id=from_asset_id,
                price=swap_preview['rate'],
                quote_asset_id=to_asset_id,
                timestamp=datetime.utcnow(),
                notes=f"Swap: {swap_preview['from_asset'].symbol} → {swap_preview['to_asset'].symbol}"
            )
            
            # Create buy transaction
            buy_transaction = Transaction(
                user_id=user_id,
                asset_id=to_asset_id,
                tx_type=TransactionType.TRADE_BUY,
                amount=swap_preview['net_to_amount'],
                price=Decimal('1') / swap_preview['rate'],
                quote_asset_id=from_asset_id,
                timestamp=datetime.utcnow(),
                notes=f"Swap: {swap_preview['from_asset'].symbol} → {swap_preview['to_asset'].symbol}"
            )
            
            db.session.add(sell_transaction)
            db.session.add(buy_transaction)
            db.session.commit()
            
            return {
                'success': True,
                'sell_transaction_id': sell_transaction.id,
                'buy_transaction_id': buy_transaction.id,
                'from_amount': from_amount,
                'to_amount': swap_preview['net_to_amount'],
                'fee_amount': swap_preview['fee_amount'],
                'rate': swap_preview['rate']
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Swap execution failed: {str(e)}")
            raise SwapError(f"Swap execution failed: {str(e)}")
    
    @staticmethod
    def _update_holding(user_id: int, asset_id: int, amount_change: Decimal):
        """Update user holdings"""
        holding = Holding.query.filter_by(user_id=user_id, asset_id=asset_id).first()
        
        if holding:
            new_balance = holding.balance + amount_change
            if new_balance < 0:
                raise SwapError("Insufficient balance")
            holding.balance = new_balance
            holding.updated_at = datetime.utcnow()
        else:
            if amount_change < 0:
                raise SwapError("No existing holding to deduct from")
            
            holding = Holding(
                user_id=user_id,
                asset_id=asset_id,
                balance=amount_change
            )
            db.session.add(holding)
    
    @staticmethod
    def get_recent_swaps(user_id: int, limit: int = 10) -> list:
        """Get user's recent swap transactions"""
        return Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.tx_type.in_([TransactionType.TRADE_BUY, TransactionType.TRADE_SELL])
        ).order_by(Transaction.timestamp.desc()).limit(limit).all()
