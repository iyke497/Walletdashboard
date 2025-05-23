# app/commands.py
import click
import json
import time
import math
import requests
from sqlalchemy import exc
from flask.cli import with_appcontext
from datetime import datetime
from .extensions import db
from .models import Asset, User, NetworkType, AssetType, Holding, DepositAddress
from .dashboard.services import CoinGeckoService
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

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

@click.command('seed-holdings')
@with_appcontext
def seed_holdings_command():
    """Seed test holdings for the test user."""
    test_user = User.query.filter_by(username="testuser").first()
    if not test_user:
        click.echo('Test user not found. Please run seed-db first.')
        return

    # Define test holdings with realistic amounts
    test_holdings = [
        {"symbol": "BTC", "balance": 0.5},    # 0.5 BTC
        {"symbol": "ETH", "balance": 5.0},    # 5 ETH
        {"symbol": "SOL", "balance": 100.0},  # 100 SOL
        {"symbol": "USDT", "balance": 10000.0},  # 10,000 USDT
        {"symbol": "USDC", "balance": 5000.0},   # 5,000 USDC
    ]

    for holding in test_holdings:
        asset = Asset.query.filter_by(symbol=holding["symbol"]).first()
        if not asset:
            click.echo(f'Asset {holding["symbol"]} not found.')
            continue

        # Check if holding already exists
        existing_holding = Holding.query.filter_by(
            user_id=test_user.id,
            asset_id=asset.id
        ).first()

        if existing_holding:
            existing_holding.balance = holding["balance"]
            click.echo(f'Updated {holding["symbol"]} balance to {holding["balance"]}')
        else:
            new_holding = Holding(
                user_id=test_user.id,
                asset_id=asset.id,
                balance=holding["balance"]
            )
            db.session.add(new_holding)
            click.echo(f'Added {holding["symbol"]} with balance {holding["balance"]}')

    db.session.commit()
    click.echo('Test holdings seeded successfully!')


@click.command('seed-deposit-addresses')
@with_appcontext
def seed_deposit_addresses():
    """Seed deposit addresses for the test user."""

    # Get or create assets (assuming these exist in your DB)
    assets = {
        'BTC': Asset.query.filter_by(symbol='BTC').first(),
        'ETH': Asset.query.filter_by(symbol='ETH').first(),
        'SOL': Asset.query.filter_by(symbol='SOL').first(),
        'USDT': Asset.query.filter_by(symbol='USDT').first()
    }

    # Validate assets exist
    for sym, asset in assets.items():
        if not asset:
            print(f"Error: {sym} asset not found in database!")

    # Sample deposit addresses (use real addresses in production!)
    sample_addresses = [
        # Bitcoin addresses
        {
            'asset': 'BTC',
            'address': '1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2',
            'network': NetworkType.BITCOIN
        },
        
        # Ethereum addresses
        {
            'asset': 'ETH',
            'address': '0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE',
            'network': NetworkType.ETHEREUM
        },
        
        # USDT addresses
        {
            'asset': 'USDT',
            'address': '0x37d8B8E3f36F82BFB3c61f69b3b7fF5e331Ad4E9',
            'network': NetworkType.ETHEREUM
        },
        {
            'asset': 'USDT',
            'address': 'TRzLvZ6Ga6TWuAaJn6iE7XF98eqG5Jz2P4',
            'network': NetworkType.TRON
        }
    ]

    # Create deposit addresses
    created = 0
    for addr_data in sample_addresses:
        # Check if address already exists
        if DepositAddress.query.filter_by(address=addr_data['address']).first():
            continue

        asset = assets[addr_data['asset']]
        
        deposit_address = DepositAddress(
            asset_id=asset.id,
            address=addr_data['address'],
            network=addr_data['network'],
            is_active=True
        )
        
        db.session.add(deposit_address)
        created += 1

    try:
        db.session.commit()
        print(f"Successfully created {created} deposit addresses")
    except Exception as e:
        db.session.rollback()
        print(f"Error seeding addresses: {str(e)}")

@click.command('fetch-rates')
@with_appcontext
def fetch_rates_command():
    """Fetch and store current exchange rates from CoinGecko."""
    try:
        count = CoinGeckoService.fetch_and_store_rates()
        click.echo(f'Successfully stored {count} exchange rates')
    except Exception as e:
        click.echo(f'Error fetching rates: {str(e)}', err=True)


@click.command('load-crypto-assets')
@click.argument('json_file', type=click.Path(exists=True))
@with_appcontext
def load_crypto_assets_command(json_file):
    """Load cryptocurrency asset data from a JSON file into the database,
    populating the new JSON 'networks' field with platform keys, committing per entry
    and logging any integrity errors to a separate file.
    """

    error_log_path = 'load_crypto_assets_errors.log'
    new_count = 0
    update_count = 0
    fail_count = 0

    # Load the JSON data
    with open(json_file, 'r') as f:
        data = json.load(f)

    for entry in data:
        coingecko_id = entry.get('id')
        symbol = entry.get('symbol')
        name = entry.get('name')
        platforms = entry.get('platforms', {}) or {}
        networks = list(platforms.keys())

        # Disable autoflush during query
        with db.session.no_autoflush:
            asset = Asset.query.filter_by(coingecko_id=coingecko_id).first()

        if asset:
            action = 'Update'
            asset.symbol = symbol
            asset.name = name
            asset.networks = networks
        else:
            action = 'Create'
            asset = Asset(
                symbol=symbol,
                name=name,
                coingecko_id=coingecko_id,
                networks=networks
            )
            db.session.add(asset)

        # Commit per asset and handle integrity errors
        try:
            db.session.commit()
            if action == 'Create':
                new_count += 1
            else:
                update_count += 1
            click.echo(f"{action} successful for {coingecko_id}")
        except IntegrityError as err:
            db.session.rollback()
            fail_count += 1
            # Log the failure
            with open(error_log_path, 'a') as log_file:
                log_file.write(f"{coingecko_id}: {err}\n")
            click.echo(f"Skipped {action} for {coingecko_id} due to integrity error")
            continue

    # Summary output
    click.echo(f"Created {new_count} new assets, updated {update_count} assets, {fail_count} failures.")
    click.echo(f"Integrity errors logged to {error_log_path}")

@click.command('fetch-crypto-images')
@click.argument('json_file', type=click.Path(exists=True))
@click.option('--top', default=2000, help='Number of top market cap coins to process')
@with_appcontext
def fetch_crypto_images_command(json_file, top):
    """Fetch image URLs for the top N market-cap coins (by CoinGecko) present in the JSON file and save them into Asset.images, with backoff on rate limits."""
    # Rate limiting parameters
    per_minute_limit = 50
    delay = 60.0 / per_minute_limit
    fail_count = 0
    update_count = 0
    error_log_path = 'fetch_crypto_images_errors.log'

    # 1. Load all entries and collect valid IDs
    with open(json_file, 'r') as f:
        entries = json.load(f)
    valid_ids = {e.get('id') for e in entries if e.get('id')}

    # 2. Retrieve top N IDs by market cap in pages, with retry/backoff
    top_ids = []
    per_page = 250
    pages = math.ceil(top / per_page)
    for page in range(1, pages + 1):
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': per_page,
            'page': page
        }
        retries = 0
        while True:
            try:
                resp = requests.get(
                    'https://api.coingecko.com/api/v3/coins/markets',
                    params=params,
                    timeout=15
                )
                resp.raise_for_status()
                data = resp.json()
                top_ids.extend([coin['id'] for coin in data])
                break
            except requests.exceptions.HTTPError as http_err:
                status = getattr(http_err.response, 'status_code', None)
                if status == 429 and retries < 5:
                    wait = 60  # back off for 60 seconds on rate limit
                    click.echo(f"Rate limit reached on page {page}, retrying after {wait}s... (retry {retries+1})")
                    time.sleep(wait)
                    retries += 1
                    continue
                else:
                    click.echo(f"Error fetching market data page {page}: {http_err}")
                    return
            except Exception as err:
                click.echo(f"Error fetching market data page {page}: {err}")
                return
        time.sleep(delay)

    top_ids = top_ids[:top]

    # 3. Filter to those present in local JSON data
    to_process = [cid for cid in top_ids if cid in valid_ids]
    click.echo(f"Will fetch images for {len(to_process)} of the top {top} coins from JSON.")

    # 4. Fetch images and update DB, with per-call backoff
    for coin_id in to_process:
        retries = 0
        while True:
            try:
                resp = requests.get(
                    f"https://api.coingecko.com/api/v3/coins/{coin_id}",
                    timeout=15
                )
                resp.raise_for_status()
                images = resp.json().get('image', {}) or {}
                break
            except requests.exceptions.HTTPError as http_err:
                status = getattr(http_err.response, 'status_code', None)
                if status == 429 and retries < 5:
                    wait = 60
                    click.echo(f"Rate limit reached fetching {coin_id}, retry {retries+1}, waiting {wait}s...")
                    time.sleep(wait)
                    retries += 1
                    continue
                click.echo(f"Fetch error for {coin_id}: {http_err}")
                fail_count += 1
                with open(error_log_path, 'a') as log:
                    log.write(f"Fetch failure {coin_id}: {http_err}\n")
                images = None
                break
            except Exception as err:
                click.echo(f"Fetch error for {coin_id}: {err}")
                fail_count += 1
                with open(error_log_path, 'a') as log:
                    log.write(f"Fetch failure {coin_id}: {err}\n")
                images = None
                break
        if images is None:
            continue

        # Update database
        try:
            asset = Asset.query.filter_by(coingecko_id=coin_id).first()
            if asset:
                asset.images = images
                db.session.commit()
                update_count += 1
                click.echo(f"Updated images for {coin_id}")
            else:
                click.echo(f"No asset found for {coin_id}, skipping.")
        except SQLAlchemyError as db_err:
            db.session.rollback()
            fail_count += 1
            click.echo(f"DB error for {coin_id}: {db_err}")
            with open(error_log_path, 'a') as log:
                log.write(f"DB failure {coin_id}: {db_err}\n")

        time.sleep(delay)

    click.echo(f"Done: {update_count} updated, {fail_count} failed.")
    click.echo(f"Errors logged in {error_log_path}")


def init_app(app):
    app.cli.add_command(seed_db_command)
    app.cli.add_command(seed_holdings_command)
    app.cli.add_command(seed_deposit_addresses)
    app.cli.add_command(fetch_rates_command)
    app.cli.add_command(load_crypto_assets_command)
    app.cli.add_command(fetch_crypto_images_command)