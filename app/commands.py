# app/commands.py
import click
from decimal import Decimal
import json
import time
import math
import random
import requests
from faker import Faker
from sqlalchemy import exc
from flask.cli import with_appcontext
from datetime import datetime
from .extensions import db
from app.models import Asset, User, NetworkType, AssetType, Holding, DepositAddress, Trader, AssetType, MiningAlgorithm, HashrateUnit, MiningPool, MiningDifficulty, HashratePackage, PackageType
from .dashboard.services import CoinGeckoService
from sqlalchemy.exc import IntegrityError, SQLAlchemyError, NoResultFound
from app.utils.network_symbol import get_network_symbol

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
def load_crypto_assets_command_old(json_file):
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

@click.command('load-crypto-assets')
@click.argument('json_file', type=click.Path(exists=True))
@with_appcontext
def load_crypto_assets_command(json_file):
    """Load cryptocurrency asset data from a JSON file into the database,
    with structured network data in the proper format.
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
        
        # Convert platforms to structured network data
        networks_data = []
        
        # Handle assets with empty platforms (native blockchains)
        if not platforms:
            networks_data.append({
                "id": coingecko_id,
                "symbol": symbol,
                "deposit_address": "",
                "contract_address": "",
                "minimum_deposit": "0.001",
                "fees": "0.0001"
            })
        else:
            # Process platforms for tokens
            for network_id, contract_address in platforms.items():
                # Skip empty contract addresses
                if not contract_address:
                    continue
                
                network_entry = {
                    "id": network_id,
                    "symbol": get_network_symbol(network_id),
                    "deposit_address": "",
                    "contract_address": contract_address,
                    "minimum_deposit": "0.001",
                    "fees": "0.001"
                }
                
                networks_data.append(network_entry)

        # Disable autoflush during query
        with db.session.no_autoflush:
            asset = Asset.query.filter_by(coingecko_id=coingecko_id).first()

        if asset:
            action = 'Update'
            asset.symbol = symbol
            asset.name = name
            asset.networks = networks_data
        else:
            action = 'Create'
            asset = Asset(
                symbol=symbol,
                name=name,
                coingecko_id=coingecko_id,
                networks=networks_data
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


@click.command('update-network-structure')
@with_appcontext
def update_network_structure():
    """
    Simple script to convert network data from list of strings to structured format.
    
    Converts:
      ["ethereum", "tron"]
    
    To:
      [
        {"id": "ethereum", "symbol": "ERC20", "deposit_address": "", "contract_address": "", "minimum_deposit": "0.001", "fees": "0.0005"},
        {"id": "tron", "symbol": "TRC20", "deposit_address": "", "contract_address": "", "minimum_deposit": "10", "fees": "1"}
      ]
    
    For assets with empty networks, creates a single entry using the asset's ID.
    """
    
    # Network defaults
    network_defaults = {
        "ethereum": {"minimum_deposit": "0.001", "fees": "0.0005"},
        "tron": {"minimum_deposit": "10", "fees": "1"},
        "binance-smart-chain": {"minimum_deposit": "0.002", "fees": "0.0002"}
    }
    
    # Get all assets
    assets = Asset.query.all()
    count = 0
    
    for asset in assets:
        # Skip assets that already have structured networks
        if asset.networks and isinstance(asset.networks, list) and len(asset.networks) > 0:
            if isinstance(asset.networks[0], dict) and "id" in asset.networks[0]:
                continue
        
        # Handle case where networks is empty or None
        if not asset.networks:
            # For assets without networks (like Bitcoin), create a single entry
            structured_networks = [{
                "id": asset.coingecko_id,
                "symbol": get_network_symbol(asset.coingecko_id),
                "deposit_address": "",
                "contract_address": "",
                "minimum_deposit": "0.001",
                "fees": "0.0001"
            }]
        else:
            # Convert string list to structured format
            structured_networks = []
            
            for network_id in asset.networks:
                network_entry = {
                    "id": network_id,
                    "symbol": get_network_symbol(network_id),
                    "deposit_address": "",
                    "contract_address": "",
                    "minimum_deposit": "0.001",
                    "fees": "0.001"
                }
                
                # Apply defaults for known networks
                if network_id in network_defaults:
                    network_entry.update(network_defaults[network_id])
                
                structured_networks.append(network_entry)
        
        # Update the asset
        asset.networks = structured_networks
        count += 1
        
        # Commit every 50 records to avoid memory issues
        if count % 50 == 0:
            db.session.commit()
            click.echo(f"Processed {count} assets")
    
    # Final commit
    db.session.commit()
    click.echo(f"Successfully updated {count} assets")


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


@click.command('seed-traders')
@click.argument('json_file', type=click.Path(exists=True))
@with_appcontext
def seed_traders_command(json_file):
    """
    Seed the database with trader profiles from a JSON file.
    
    This command creates or updates trader profiles along with their performance metrics.
    It also creates associated user accounts if they don't already exist.
    
    Example:
        flask seed-traders data/sample_traders.json
    """
   
    
    created_users = 0
    created_traders = 0
    updated_traders = 0
    errors = []
    
    # Load data from JSON file
    try:
        with open(json_file, 'r') as file:
            traders_data = json.load(file)
        
        click.echo(f"Processing {len(traders_data)} traders from {json_file}...")
        
        # Process each trader
        for trader_data in traders_data:
            try:
                username = trader_data.get('username')
                if not username:
                    errors.append("Skipped entry with missing username")
                    continue
                
                # Check if user exists by username
                user = User.query.filter_by(username=username).first()
                
                # If user doesn't exist, create one
                if not user:
                    user = User(
                        username=username,
                        email=f"{username.lower()}@example.com"
                    )
                    # Set a default password
                    user.set_password("password123")
                    db.session.add(user)
                    db.session.flush()  # Get the user ID without committing
                    created_users += 1
                
                # Check if trader profile exists
                trader = Trader.query.filter_by(user_id=user.id).first()
                
                performance_metrics = trader_data.get('performance_metrics', {})
                
                if trader:
                    # Update existing trader
                    trader.bio = trader_data.get('bio', '')
                    trader.tags = trader_data.get('tags', '')
                    trader.win_rate = Decimal(str(trader_data.get('win_rate', 0)))
                    trader.avg_monthly_return = Decimal(str(trader_data.get('avg_monthly_return', 0)))
                    trader.max_drawdown = Decimal(str(trader_data.get('max_drawdown', 0)))
                    trader.risk_score = trader_data.get('risk_score', 'medium')
                    trader.is_verified = trader_data.get('is_verified', False)
                    trader.avatar_url = trader_data.get('avatar_url', '')
                    
                    # Update performance metrics JSON
                    if performance_metrics:
                        trader.performance_metrics = performance_metrics
                    
                    updated_traders += 1
                    click.echo(f"Updated trader: {username}")
                else:
                    # Create new trader
                    trader = Trader(
                        user_id=user.id,
                        bio=trader_data.get('bio', ''),
                        tags=trader_data.get('tags', ''),
                        win_rate=Decimal(str(trader_data.get('win_rate', 0))),
                        avg_monthly_return=Decimal(str(trader_data.get('avg_monthly_return', 0))),
                        max_drawdown=Decimal(str(trader_data.get('max_drawdown', 0))),
                        risk_score=trader_data.get('risk_score', 'medium'),
                        is_verified=trader_data.get('is_verified', False),
                        performance_metrics=performance_metrics
                    )
                    db.session.add(trader)
                    created_traders += 1
                    click.echo(f"Created trader: {username}")
                
            except Exception as e:
                db.session.rollback()
                errors.append(f"Error processing trader {trader_data.get('username', 'unknown')}: {str(e)}")
                click.echo(f"Error: {str(e)}", err=True)
        
        # Commit all changes
        try:
            db.session.commit()
            click.echo(f"\nTrader data import complete!")
            click.echo(f"Created users: {created_users}")
            click.echo(f"Created traders: {created_traders}")
            click.echo(f"Updated traders: {updated_traders}")
            
            if errors:
                click.echo("\nErrors encountered:")
                for error in errors:
                    click.echo(f"- {error}")
                
        except Exception as e:
            db.session.rollback()
            click.echo(f"Database commit failed: {str(e)}", err=True)
            
    except Exception as e:
        click.echo(f"Failed to load JSON file: {str(e)}", err=True)

@click.command('seed-mining-pools')
@click.option('--pools', default=5, help='Number of mining pools to create')
@click.option('--packages', default=3, help='Number of hashrate packages per pool')
def load_mining_data(pools, packages):
    """Load dummy data for mining pools and hashrate packages"""
    fake = Faker()
    click.echo(f"Creating {pools} mining pools with {packages} packages each...")

    # Asset symbols we'll use (assuming they exist)
    asset_symbols = ["btc", "eth", "ltc", "doge"]
    
    # Asset-algorithm mapping
    asset_algorithms = {
        "btc": MiningAlgorithm.SHA256,
        "eth": MiningAlgorithm.ETHASH,
        "ltc": MiningAlgorithm.SCRYPT,
        "doge": MiningAlgorithm.SCRYPT,
    }

    # Asset-unit mapping
    asset_units = {
        "btc": HashrateUnit.TERAHASH_S,
        "eth": HashrateUnit.MEGAHASH_S,
        "ltc": HashrateUnit.GIGAHASH_S,
        "doge": HashrateUnit.KILOHASH_S,
    }

    # Create mining pools
    created_pools = 0
    created_packages = 0
    
    for _ in range(pools):
        symbol = random.choice(asset_symbols)
        
        try:
            # Fetch existing asset - will fail if not found
            asset = db.session.query(Asset).filter_by(symbol=symbol).first()
            
            pool = MiningPool(
                asset_id=asset.id,
                name=f"{asset.name} {fake.color_name()} Pool",
                algorithm=asset_algorithms[symbol],
                pool_fee=round(random.uniform(0.005, 0.03), 4),  # 0.5% - 3%
                difficulty=random.choice(list(MiningDifficulty)),
                min_hashrate=round(random.uniform(10, 1000), 2),  # 10-1000 units
                min_hashrate_unit=asset_units[symbol],
                estimated_daily_earnings_per_unit=round(random.uniform(0.01, 0.5), 4),  # $0.01-$0.5/day
                description=fake.text(),
                is_active=random.choices([True, False], weights=[0.8, 0.2])[0],
                total_hashrate=round(random.uniform(1000, 100000), 2),
                total_hashrate_unit=asset_units[symbol],
                active_miners=random.randint(100, 10000),
                blocks_found_24h=random.randint(1, 100)
            )
            db.session.add(pool)
            db.session.flush()  # Get pool ID for packages
            
            # Create packages for this pool
            for j in range(packages):
                multiplier = [1, 5, 10, 20, 50][j] if j < 5 else 100
                package = HashratePackage(
                    pool_id=pool.id,
                    name=f"{fake.word().capitalize()} Package",
                    hashrate=pool.min_hashrate * multiplier,
                    hashrate_unit=pool.min_hashrate_unit,
                    monthly_cost_usd=round(30 * pool.estimated_daily_earnings_per_unit * multiplier * random.uniform(0.8, 1.2), 2),
                    power_consumption_watts=random.randint(100, 5000),
                    is_active=random.choices([True, False], weights=[0.9, 0.1])[0],
                    sort_order=j
                )
                db.session.add(package)
                created_packages += 1
                
            db.session.commit()
            created_pools += 1
            click.echo(f"Created pool: {pool.name} with {packages} packages")
            
        except NoResultFound:
            db.session.rollback()
            click.echo(f"⚠️ Asset {symbol} not found in database. Skipping pool creation.")
        except IntegrityError as e:
            db.session.rollback()
            click.echo(f"⚠️ Skipped duplicate pool: {e.orig}")

    click.echo(f"✅ Successfully created {created_pools} mining pools")
    click.echo(f"✅ Successfully created {created_packages} packages")
    click.echo(f"💡 Note: {pools - created_pools} pools skipped due to errors")

@click.command('standardize-packages')
@with_appcontext
def standardize_packages_command():
    """Standardize hashrate packages to use Basic, Pro, Enterprise naming."""
    click.echo("Standardizing hashrate packages...")
    
    # Get all mining pools
    pools = MiningPool.query.all()
    
    if not pools:
        click.echo("No mining pools found. Nothing to standardize.")
        return
    
    click.echo(f"Found {len(pools)} mining pools")
    updated_count = 0
    created_count = 0
    
    for pool in pools:
        click.echo(f"\nProcessing pool {pool.id} ({pool.asset.symbol if pool.asset else 'Unknown'})")
        
        # Get existing packages for this pool
        existing_packages = HashratePackage.query.filter_by(pool_id=pool.id).order_by(HashratePackage.hashrate).all()
        
        # Get or create base hashrate and unit from pool
        base_hashrate = (pool.min_hashrate if hasattr(pool, 'min_hashrate') and pool.min_hashrate is not None else Decimal('0.1'))
        hashrate_unit = pool.min_hashrate_unit if hasattr(pool, 'min_hashrate_unit') and pool.min_hashrate_unit else HashrateUnit.TERAHASH_S
        
        # Define standard package configurations
        standard_packages = [
            {
                'name': 'Basic',
                'hashrate_multiplier': 1,
                'cost_multiplier': 1.0,
                'power_efficiency': 1.0,
                'sort_order': 1
            },
            {
                'name': 'Pro',
                'hashrate_multiplier': 5,
                'cost_multiplier': 0.9,  # 10% discount per unit
                'power_efficiency': 0.9,  # 10% more efficient
                'sort_order': 2
            },
            {
                'name': 'Enterprise',
                'hashrate_multiplier': 20,
                'cost_multiplier': 0.8,  # 20% discount per unit
                'power_efficiency': 0.8,  # 20% more efficient
                'sort_order': 3
            }
        ]
        
        # Calculate base cost per unit based on pool's daily earnings
        #base_cost_per_unit = 30 * pool.estimated_daily_earnings_per_unit * 1.2 if hasattr(pool, 'estimated_daily_earnings_per_unit') and pool.estimated_daily_earnings_per_unit else 10.0
        if hasattr(pool, 'estimated_daily_earnings_per_unit') and pool.estimated_daily_earnings_per_unit:
            # Convert multipliers to Decimal before arithmetic operations
            base_cost_per_unit = Decimal(30) * pool.estimated_daily_earnings_per_unit * Decimal('1.2')
        else:
            base_cost_per_unit = Decimal('10.0')
        
        # Calculate base power consumption
        base_power = Decimal(100)
        
        # Create or update packages
        for pkg_config in standard_packages:
            # Check if we already have a package with this name
            existing_pkg = next((p for p in existing_packages if p.name == pkg_config['name']), None)
            
            if existing_pkg:
                # Update existing package
                existing_pkg.hashrate = base_hashrate * pkg_config['hashrate_multiplier']
                existing_pkg.hashrate_unit = hashrate_unit
                existing_pkg.monthly_cost_usd = base_cost_per_unit * pkg_config['hashrate_multiplier'] * pkg_config['cost_multiplier']
                existing_pkg.power_consumption_watts = int(base_power * pkg_config['hashrate_multiplier'] * pkg_config['power_efficiency'])
                existing_pkg.is_active = True
                existing_pkg.sort_order = pkg_config['sort_order']
                
                click.echo(f"  ✅ Updated {pkg_config['name']} package: {existing_pkg.hashrate} {existing_pkg.hashrate_unit.value}, ${existing_pkg.monthly_cost_usd:.2f}/month")
                updated_count += 1
            else:
                # Create new package
                new_pkg = HashratePackage(
                    pool_id=pool.id,
                    name=pkg_config['name'],
                    hashrate=base_hashrate * pkg_config['hashrate_multiplier'],
                    hashrate_unit=hashrate_unit,
                    monthly_cost_usd=(base_cost_per_unit * Decimal(pkg_config['hashrate_multiplier']) * Decimal(str(pkg_config['cost_multiplier']))).quantize(Decimal('0.01')),
                    power_consumption_watts=int( base_power * Decimal(pkg_config['hashrate_multiplier']) * Decimal(str(pkg_config['power_efficiency'])) ),
                    is_active=True,
                    sort_order=pkg_config['sort_order']
                )
                db.session.add(new_pkg)
                
                click.echo(f"  ✅ Created {pkg_config['name']} package: {new_pkg.hashrate} {new_pkg.hashrate_unit.value}, ${new_pkg.monthly_cost_usd:.2f}/month")
                created_count += 1
        
        # Deactivate other packages that don't match standard names
        for pkg in existing_packages:
            if pkg.name not in ['Basic', 'Pro', 'Enterprise']:
                pkg.is_active = False
                click.echo(f"  ❌ Deactivated non-standard package: {pkg.name}")
                updated_count += 1
    
    # Commit changes
    try:
        db.session.commit()
        click.echo(f"\n✅ Successfully standardized packages: updated {updated_count}, created {created_count}")
    except Exception as e:
        db.session.rollback()
        click.echo(f"\n❌ Error committing changes: {str(e)}")

# Add this command to fix the package_type field in your database

@click.command('fix-package-types')
@with_appcontext
def fix_package_types_command():
    """Fix package_type field for hashrate packages based on their names."""
    click.echo("Fixing package types...")
    
    # Get all hashrate packages
    packages = HashratePackage.query.filter_by(is_active=True).all()
    
    if not packages:
        click.echo("No active packages found.")
        return
    
    click.echo(f"Found {len(packages)} active packages")
    updated_count = 0
    
    for package in packages:
        old_type = package.package_type.value if package.package_type else 'None'
        
        # Set package_type based on name
        if package.name.lower() == 'basic':
            package.package_type = PackageType.BASIC
        elif package.name.lower() == 'pro':
            package.package_type = PackageType.PRO
        elif package.name.lower() == 'enterprise':
            package.package_type = PackageType.ENTERPRISE
        else:
            # For any other names, try to map based on hashrate
            # Get the pool's minimum hashrate
            pool = MiningPool.query.get(package.pool_id)
            if pool and pool.min_hashrate:
                ratio = float(package.hashrate) / float(pool.min_hashrate)
                if ratio <= 2:
                    package.package_type = PackageType.BASIC
                elif ratio <= 10:
                    package.package_type = PackageType.PRO
                else:
                    package.package_type = PackageType.ENTERPRISE
            else:
                package.package_type = PackageType.BASIC  # Default fallback
        
        new_type = package.package_type.value
        
        if old_type != new_type:
            click.echo(f"Pool {package.pool_id} - {package.name}: {old_type} → {new_type}")
            updated_count += 1
        else:
            click.echo(f"Pool {package.pool_id} - {package.name}: {new_type} (no change)")
    
    # Commit changes
    try:
        db.session.commit()
        click.echo(f"\n✅ Successfully updated {updated_count} package types")
    except Exception as e:
        db.session.rollback()
        click.echo(f"\n❌ Error committing changes: {str(e)}")

@click.command('deactivate-invalid-assets')
@with_appcontext
def deactivate_invalid_assets():
    """Deactivate assets with null images and no deposit addresses in any network."""
    count = 0
    
    # Get all assets that have null images
    assets_with_null_images = Asset.query.filter(Asset.images.is_(None)).all()
    
    for asset in assets_with_null_images:
        networks = asset.networks or []
        
        # Check if all networks have empty deposit addresses
        has_deposit_address = False
        for network in networks:
            if network.get('deposit_address'):
                has_deposit_address = True
                break
        
        # If no deposit addresses found in any network, deactivate the asset
        if not has_deposit_address:
            asset.is_active = False
            db.session.add(asset)
            count += 1
            click.echo(f"Deactivating asset {asset.symbol} (ID: {asset.id}) - null image and no deposit addresses")
    
    if count > 0:
        db.session.commit()
        click.echo(f"Successfully deactivated {count} assets")
    else:
        click.echo("No assets matching the criteria found")


def init_app(app):
    app.cli.add_command(seed_db_command)
    app.cli.add_command(seed_holdings_command)
    app.cli.add_command(seed_deposit_addresses)
    app.cli.add_command(fetch_rates_command)
    app.cli.add_command(load_crypto_assets_command)
    app.cli.add_command(fetch_crypto_images_command)
    app.cli.add_command(seed_traders_command)
    app.cli.add_command(update_network_structure)
    app.cli.add_command(load_mining_data)
    app.cli.add_command(standardize_packages_command)
    app.cli.add_command(fix_package_types_command)
    app.cli.add_command(deactivate_invalid_assets)