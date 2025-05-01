from datetime import datetime
import requests
import os
from sqlalchemy import func
from app.models import User, Holding, Asset, ExchangeRate, AssetType
from app.extensions import db

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
        
        total_value = 0
        for holding, asset in holdings:
            if asset.id == base_currency_id:
                # If the holding is in the base currency, add directly
                total_value += float(holding.balance)
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
                    total_value += float(holding.balance) * float(latest_rate.rate)
        
        return total_value

    @staticmethod
    def get_portfolio_details(user_id, base_currency_id):
        """Get detailed portfolio information including holdings and their values"""
        holdings = PortfolioService.get_user_holdings(user_id)
        total_value = PortfolioService.get_portfolio_value(user_id, base_currency_id)
        
        portfolio_details = []
        for holding, asset in holdings:
            holding_value = 0
            if asset.id == base_currency_id:
                holding_value = float(holding.balance)
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
                    holding_value = float(holding.balance) * float(latest_rate.rate)
            
            portfolio_details.append({
                'asset': {
                    'symbol': asset.symbol,
                    'name': asset.name
                },
                'balance': float(holding.balance),
                'value': holding_value,
                'percentage': (holding_value / total_value * 100) if total_value > 0 else 0
            })
        

        print(portfolio_details)
        print(total_value)
        return {
            'total_value': total_value,
            'holdings': portfolio_details
        }

class CoinGeckoService:
    COINGECKO_API = "https://api.coingecko.com/api/v3"
    
    @staticmethod
    def fetch_and_store_rates():
        """Get the latest exchange rate between two assets"""
        
        # Get all assets that have CoinGecko IDs
        crypto_assets = Asset.query.filter(
            Asset.asset_type == AssetType.CRYPTO,
            Asset.coingecko_id.isnot(None)
        ).all()
        
        # Get all fiat quote assets
        fiat_assets = Asset.query.filter(
            Asset.asset_type == AssetType.FIAT
        ).all()

        if not crypto_assets or not fiat_assets:
            raise ValueError("No crypto/fiat assets configured in database")

        # Build CoinGecko parameters
        coin_ids = [asset.coingecko_id for asset in crypto_assets]
        vs_currencies = [asset.symbol.lower() for asset in fiat_assets]

        # Make API request
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

        # Process response
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

        # Bulk insert
        db.session.bulk_save_objects(new_rates)
        db.session.commit()
        return len(new_rates)
