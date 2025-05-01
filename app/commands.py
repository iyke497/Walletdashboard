# app/commands.py

import click
from flask.cli import with_appcontext
from datetime import datetime
from .extensions import db
from .models import Asset, User, NetworkType, AssetType

@click.command('seed-db')
@with_appcontext
def seed_db_command():
    """Seed the database with initial data."""
    # Seed fiat currencies
    fiat_currencies = [
        {"symbol": "USD", "name": "US Dollar", "coingecko_id": "usd", "decimals": 2, "asset_type": AssetType.FIAT},
        {"symbol": "EUR", "name": "Euro", "coingecko_id": "eur", "decimals": 2, "asset_type": AssetType.FIAT},
        {"symbol": "GBP", "name": "British Pound", "coingecko_id": "gbp", "decimals": 2, "asset_type": AssetType.FIAT},
        {"symbol": "JPY", "name": "Japanese Yen", "coingecko_id": "jpy", "decimals": 0, "asset_type": AssetType.FIAT},
    ]
    
    # Seed cryptocurrencies
    cryptocurrencies = [
        {"symbol": "BTC", "name": "Bitcoin", "coingecko_id": "bitcoin", "decimals": 8, "asset_type": AssetType.CRYPTO},
        {"symbol": "ETH", "name": "Ethereum", "coingecko_id": "ethereum", "decimals": 18, "asset_type": AssetType.CRYPTO},
        {"symbol": "SOL", "name": "Solana", "coingecko_id": "solana", "decimals": 9, "asset_type": AssetType.CRYPTO},
        {"symbol": "BNB", "name": "Binance Coin", "coingecko_id": "binancecoin", "decimals": 18, "asset_type": AssetType.CRYPTO},
        {"symbol": "USDT", "name": "Tether", "coingecko_id": "tether", "decimals": 6, "asset_type": AssetType.CRYPTO},
        {"symbol": "USDC", "name": "USD Coin", "coingecko_id": "usd-coin", "decimals": 6, "asset_type": AssetType.CRYPTO},
        {"symbol": "ADA", "name": "Cardano", "coingecko_id": "cardano", "decimals": 6, "asset_type": AssetType.CRYPTO},
        {"symbol": "DOT", "name": "Polkadot", "coingecko_id": "polkadot", "decimals": 10, "asset_type": AssetType.CRYPTO},
        {"symbol": "AVAX", "name": "Avalanche", "coingecko_id": "avalanche-2", "decimals": 18, "asset_type": AssetType.CRYPTO},
        {"symbol": "ATOM", "name": "Cosmos", "coingecko_id": "cosmos", "decimals": 6, "asset_type": AssetType.CRYPTO},
    ]
    
    # Add fiat currencies
    for currency in fiat_currencies:
        if not Asset.query.filter_by(symbol=currency["symbol"]).first():
            asset = Asset(
                symbol=currency["symbol"],
                name=currency["name"],
                coingecko_id=currency["coingecko_id"],
                decimals=currency["decimals"],
                asset_type=currency["asset_type"],
                is_active=True
            )
            db.session.add(asset)
    
    # Add cryptocurrencies
    for crypto in cryptocurrencies:
        if not Asset.query.filter_by(symbol=crypto["symbol"]).first():
            asset = Asset(
                symbol=crypto["symbol"],
                name=crypto["name"],
                coingecko_id=crypto["coingecko_id"],
                decimals=crypto["decimals"],
                asset_type=crypto["asset_type"],
                is_active=True
            )
            db.session.add(asset)
    
    # Create a test user if none exists
    if not User.query.filter_by(username="testuser").first():
        test_user = User(
            username="testuser",
            email="test@example.com"
        )
        test_user.set_password("password123")
        
        # Set USD as default display currency
        usd = Asset.query.filter_by(symbol="USD").first()
        if usd:
            test_user.display_currency_id = usd.id
            
        db.session.add(test_user)
    
    db.session.commit()
    click.echo('Database seeded successfully!')

def init_app(app):
    app.cli.add_command(seed_db_command)