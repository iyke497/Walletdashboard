from datetime import datetime, timedelta
import requests
import os
from sqlalchemy import func
from app.models import User, Holding, Asset, ExchangeRate, AssetType, Transaction, TransactionType
from app.extensions import db, cache
from decimal import Decimal

class PortfolioService:
    @staticmethod
    def get_user_holdings(user_id):
        """Get all holdings for a specific user with asset details"""
        holdings = db.session.query(
            Holding,
            Asset
        ).join(
            Asset,
            Holding.asset_id == Asset.id
        ).filter(
            Holding.user_id == user_id,
            Holding.deleted_at.is_(None)
        ).all()
        
        return holdings

    @staticmethod
    def get_portfolio_value(user_id, base_currency_id):
        """Calculate total portfolio value in specified base currency"""
        # Get all holdings for the user
        holdings = PortfolioService.get_user_holdings(user_id)
        
        total_value = Decimal('0')
        for holding, asset in holdings:
            if asset.id == base_currency_id:
                # If the holding is in the base currency, add directly
                total_value += Decimal(str(holding.balance))
            else:
                # Get latest exchange rate to base currency
                latest_rate = db.session.query(
                    ExchangeRate.rate
                ).filter(
                    ExchangeRate.base_asset_id == asset.id,
                    ExchangeRate.quote_asset_id == base_currency_id,
                    ExchangeRate.deleted_at.is_(None)
                ).order_by(
                    ExchangeRate.timestamp.desc()
                ).first()
                
                if latest_rate:
                    total_value += Decimal(str(holding.balance)) * Decimal(str(latest_rate.rate))
        
        return total_value

    @staticmethod
    def get_portfolio_details(user_id, base_currency_id):
        """Get detailed portfolio information including holdings and their values"""
        holdings = PortfolioService.get_user_holdings(user_id)
        total_value = PortfolioService.get_portfolio_value(user_id, base_currency_id)
        
        portfolio_details = []
        for holding, asset in holdings:
            holding_value = Decimal('0')
            if asset.id == base_currency_id:
                holding_value = Decimal(str(holding.balance))
            else:
                latest_rate = db.session.query(
                    ExchangeRate.rate
                ).filter(
                    ExchangeRate.base_asset_id == asset.id,
                    ExchangeRate.quote_asset_id == base_currency_id,
                    ExchangeRate.deleted_at.is_(None)
                ).order_by(
                    ExchangeRate.timestamp.desc()
                ).first()
                
                if latest_rate:
                    holding_value = Decimal(str(holding.balance)) * Decimal(str(latest_rate.rate))
            
            percentage = (holding_value / total_value * 100) if total_value > 0 else Decimal('0')
            
            portfolio_details.append({
                'asset': {
                    'symbol': asset.symbol.upper(),
                    'name': asset.name,
                    'image': asset.images.get('small') if asset.images else None
                },
                'balance': float(holding.balance),
                'value': float(holding_value),
                'percentage': float(percentage)
            })
        
        # Sort by value (descending)
        portfolio_details.sort(key=lambda x: x['value'], reverse=True)

        return {
            'total_value': float(total_value),
            'holdings': portfolio_details
        }
        
    @staticmethod
    @cache.memoize(timeout=300)  # Cache for 5 minutes
    def get_portfolio_24h_change(user_id, base_currency_id):
        """
        Calculate the 24-hour change for the portfolio
        Returns a tuple of (current_value, previous_value, absolute_change, percentage_change)
        """
        # Get current portfolio value
        current_value = PortfolioService.get_portfolio_value(user_id, base_currency_id)
        
        # Calculate portfolio value from 24 hours ago
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        
        holdings = PortfolioService.get_user_holdings(user_id)
        previous_value = Decimal('0')
        
        for holding, asset in holdings:
            if asset.id == base_currency_id:
                previous_value += Decimal(str(holding.balance))
            else:
                # Get exchange rate from 24 hours ago
                old_rate = db.session.query(
                    ExchangeRate.rate
                ).filter(
                    ExchangeRate.base_asset_id == asset.id,
                    ExchangeRate.quote_asset_id == base_currency_id,
                    ExchangeRate.timestamp <= yesterday,
                    ExchangeRate.deleted_at.is_(None)
                ).order_by(
                    ExchangeRate.timestamp.desc()
                ).first()
                
                if old_rate:
                    previous_value += Decimal(str(holding.balance)) * Decimal(str(old_rate.rate))
                else:
                    # Fallback to latest rate if no historical rate available
                    latest_rate = db.session.query(
                        ExchangeRate.rate
                    ).filter(
                        ExchangeRate.base_asset_id == asset.id,
                        ExchangeRate.quote_asset_id == base_currency_id,
                        ExchangeRate.deleted_at.is_(None)
                    ).order_by(
                        ExchangeRate.timestamp.desc()
                    ).first()
                    
                    if latest_rate:
                        previous_value += Decimal(str(holding.balance)) * Decimal(str(latest_rate.rate))
        
        # Calculate changes
        absolute_change = current_value - previous_value
        percentage_change = (absolute_change / previous_value * 100) if previous_value > 0 else Decimal('0')
        
        return {
            'current_value': float(current_value),
            'previous_value': float(previous_value),
            'absolute_change': float(absolute_change),
            'percentage_change': float(percentage_change)
        }
    
    @staticmethod
    def calculate_profit_loss(user_id, base_currency_id, time_period='all'):
        """
        Calculate profit and loss for a given time period
        
        Parameters:
        - user_id: The user ID
        - base_currency_id: The base currency ID for valuation
        - time_period: 'day', 'week', 'month', 'year', or 'all'
        
        Returns a dictionary with total investment, current value, profit/loss, and ROI
        """
        # Define time periods
        now = datetime.utcnow()
        time_filters = {
            'day': now - timedelta(days=1),
            'week': now - timedelta(weeks=1),
            'month': now - timedelta(days=30),
            'year': now - timedelta(days=365),
            'all': None  # No time filter
        }
        
        start_date = time_filters.get(time_period)
        
        # Get current portfolio value
        current_value = PortfolioService.get_portfolio_value(user_id, base_currency_id)
        
        # Calculate total investment using transaction history
        query = db.session.query(
            func.sum(Transaction.amount * Transaction.price).label('total_investment')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
            Transaction.tx_type.in_([TransactionType.DEPOSIT, TransactionType.TRADE_BUY])
        )
        
        # Apply time filter if specified
        if start_date:
            query = query.filter(Transaction.timestamp >= start_date)
        
        result = query.first()
        total_investment = Decimal(str(result.total_investment)) if result and result.total_investment else Decimal('0')
        
        # Calculate profit/loss
        profit_loss = current_value - total_investment
        roi_percentage = (profit_loss / total_investment * 100) if total_investment > 0 else Decimal('0')
        
        return {
            'total_investment': float(total_investment),
            'current_value': float(current_value),
            'profit_loss': float(profit_loss),
            'roi_percentage': float(roi_percentage),
            'time_period': time_period
        }
    
    @staticmethod
    def get_asset_performance(user_id, base_currency_id, time_period='all'):
        """
        Calculate performance metrics for each asset in the portfolio
        
        Parameters:
        - user_id: The user ID
        - base_currency_id: The base currency ID for valuation
        - time_period: 'day', 'week', 'month', 'year', or 'all'
        
        Returns a list of assets with their performance metrics
        """
        # Define time periods
        now = datetime.utcnow()
        time_filters = {
            'day': now - timedelta(days=1),
            'week': now - timedelta(weeks=1),
            'month': now - timedelta(days=30),
            'year': now - timedelta(days=365),
            'all': None  # No time filter
        }
        
        start_date = time_filters.get(time_period)
        
        # Get current holdings
        holdings = PortfolioService.get_user_holdings(user_id)
        
        performance_data = []
        for holding, asset in holdings:
            # Skip zero balance holdings
            if Decimal(str(holding.balance)) == 0:
                continue
                
            # Get current value of this asset
            current_value = Decimal('0')
            current_rate = None
            
            if asset.id == base_currency_id:
                current_value = Decimal(str(holding.balance))
            else:
                # Get latest exchange rate
                current_rate = db.session.query(
                    ExchangeRate.rate
                ).filter(
                    ExchangeRate.base_asset_id == asset.id,
                    ExchangeRate.quote_asset_id == base_currency_id,
                    ExchangeRate.deleted_at.is_(None)
                ).order_by(
                    ExchangeRate.timestamp.desc()
                ).first()
                
                if current_rate:
                    current_value = Decimal(str(holding.balance)) * Decimal(str(current_rate.rate))
            
            # Calculate cost basis from transactions
            query = db.session.query(
                func.sum(Transaction.amount * Transaction.price).label('total_cost'),
                func.sum(Transaction.amount).label('total_amount')
            ).filter(
                Transaction.user_id == user_id,
                Transaction.asset_id == asset.id,
                Transaction.deleted_at.is_(None),
                Transaction.tx_type == TransactionType.TRADE_BUY
            )
            
            # Apply time filter if specified
            if start_date:
                query = query.filter(Transaction.timestamp >= start_date)
            
            result = query.first()
            total_cost = Decimal(str(result.total_cost)) if result and result.total_cost else Decimal('0')
            
            # Calculate profit/loss for this asset
            profit_loss = current_value - total_cost
            roi_percentage = (profit_loss / total_cost * 100) if total_cost > 0 else Decimal('0')
            
            # Get price change data
            price_change = {
                'current_price': float(current_rate.rate) if current_rate else 1.0,
                'percentage_change_24h': 0.0
            }
            
            if asset.id != base_currency_id and current_rate:
                # Get rate from 24 hours ago
                old_rate = db.session.query(
                    ExchangeRate.rate
                ).filter(
                    ExchangeRate.base_asset_id == asset.id,
                    ExchangeRate.quote_asset_id == base_currency_id,
                    ExchangeRate.timestamp <= (now - timedelta(days=1)),
                    ExchangeRate.deleted_at.is_(None)
                ).order_by(
                    ExchangeRate.timestamp.desc()
                ).first()
                
                if old_rate:
                    old_price = Decimal(str(old_rate.rate))
                    current_price = Decimal(str(current_rate.rate))
                    change = current_price - old_price
                    percentage_change = (change / old_price * 100) if old_price > 0 else Decimal('0')
                    price_change['percentage_change_24h'] = float(percentage_change)
            
            performance_data.append({
                'asset': {
                    'id': asset.id,
                    'symbol': asset.symbol.upper(),
                    'name': asset.name,
                    'image': asset.images.get('small') if asset.images else None
                },
                'balance': float(holding.balance),
                'current_value': float(current_value),
                'cost_basis': float(total_cost),
                'profit_loss': float(profit_loss),
                'roi_percentage': float(roi_percentage),
                'price_data': price_change
            })
        
        # Sort by current value (descending)
        performance_data.sort(key=lambda x: x['current_value'], reverse=True)
        
        return performance_data

    @staticmethod
    def get_historical_portfolio_value(user_id, base_currency_id, days=30):
        """
        Get historical portfolio value over time
        
        Parameters:
        - user_id: The user ID
        - base_currency_id: The base currency ID for valuation
        - days: Number of days to look back
        
        Returns a list of {date, value} data points
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get distinct dates with exchange rate data
        distinct_dates = db.session.query(
            func.date(ExchangeRate.timestamp).label('date')
        ).filter(
            ExchangeRate.timestamp >= start_date,
            ExchangeRate.deleted_at.is_(None)
        ).group_by(
            func.date(ExchangeRate.timestamp)
        ).order_by(
            func.date(ExchangeRate.timestamp)
        ).all()
        
        # Get all assets the user holds
        holdings = PortfolioService.get_user_holdings(user_id)
        
        historical_values = []
        for date_obj in distinct_dates:
            date = date_obj.date
            end_of_day = datetime.combine(date, datetime.max.time())
            
            # Calculate portfolio value at this date
            portfolio_value = Decimal('0')
            
            for holding, asset in holdings:
                # Skip zero balance holdings
                if Decimal(str(holding.balance)) == 0:
                    continue
                
                if asset.id == base_currency_id:
                    portfolio_value += Decimal(str(holding.balance))
                else:
                    # Get the exchange rate for this date
                    rate = db.session.query(
                        ExchangeRate.rate
                    ).filter(
                        ExchangeRate.base_asset_id == asset.id,
                        ExchangeRate.quote_asset_id == base_currency_id,
                        ExchangeRate.timestamp <= end_of_day,
                        ExchangeRate.deleted_at.is_(None)
                    ).order_by(
                        ExchangeRate.timestamp.desc()
                    ).first()
                    
                    if rate:
                        # Need to adjust for transactions that occurred after this date
                        # This is a simplified approach - for full accuracy, transaction history should be considered
                        portfolio_value += Decimal(str(holding.balance)) * Decimal(str(rate.rate))
            
            historical_values.append({
                'date': date.isoformat(),
                'value': float(portfolio_value)
            })
        
        return historical_values
    
class CoinGeckoService:
    COINGECKO_API = "https://api.coingecko.com/api/v3"
    
    @staticmethod
    def fetch_and_store_rates():
        """Get the latest exchange rates for crypto-to-fiat and crypto-to-crypto pairs"""
        
        # Get all assets that have CoinGecko IDs
        crypto_assets = Asset.query.filter(
            Asset.asset_type == AssetType.CRYPTO,
            Asset.coingecko_id.isnot(None)
        ).limit(150).all()
        
        # Get all fiat quote assets
        fiat_assets = Asset.query.filter(
            Asset.asset_type == AssetType.FIAT
        ).all()

        if not crypto_assets:
            raise ValueError("No crypto assets configured in database")

        # Build CoinGecko parameters for crypto-to-fiat rates
        coin_ids = [asset.coingecko_id for asset in crypto_assets]
        vs_currencies = [asset.symbol.lower() for asset in fiat_assets]

        # Make API request for crypto-to-fiat rates
        url = f"{CoinGeckoService.COINGECKO_API}/simple/price"
        params = {
            "ids": ",".join(coin_ids),
            "vs_currencies": ",".join(vs_currencies),
            "include_last_updated_at": True
        }
        
        if os.getenv("COINGECKO_API_KEY"):
            params["x_cg_pro_api_key"] = os.getenv("COINGECKO_API_KEY")

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # Process response for crypto-to-fiat rates
        timestamp = datetime.utcnow()
        new_rates = []

        for crypto in crypto_assets:
            coin_data = data.get(crypto.coingecko_id, {})
            
            for fiat in fiat_assets:
                rate = coin_data.get(fiat.symbol.lower())
                if rate is None:
                    continue

                # Create ExchangeRate entry
                new_rate = ExchangeRate(
                    base_asset_id=crypto.id,
                    quote_asset_id=fiat.id,
                    rate=rate,
                    timestamp=timestamp,
                    source="coingecko"
                )
                new_rates.append(new_rate)

        # Calculate and store crypto-to-crypto rates using USD as intermediate
        usd_asset = Asset.query.filter_by(symbol="USD", asset_type=AssetType.FIAT).first()
        if usd_asset:
            for base_crypto in crypto_assets:
                base_usd_rate = data.get(base_crypto.coingecko_id, {}).get("usd")
                if not base_usd_rate:
                    continue
                    
                for quote_crypto in crypto_assets:
                    if base_crypto.id == quote_crypto.id:
                        continue
                        
                    quote_usd_rate = data.get(quote_crypto.coingecko_id, {}).get("usd")
                    if not quote_usd_rate:
                        continue
                        
                    # Calculate rate between the two cryptos using USD as intermediate
                    rate = Decimal(str(base_usd_rate)) / Decimal(str(quote_usd_rate))
                    
                    new_rate = ExchangeRate(
                        base_asset_id=base_crypto.id,
                        quote_asset_id=quote_crypto.id,
                        rate=rate,
                        timestamp=timestamp,
                        source="coingecko"
                    )
                    new_rates.append(new_rate)

        # Bulk insert
        db.session.bulk_save_objects(new_rates)
        db.session.commit()
        return len(new_rates)
