import csv
from app import db, create_app
from app.models import Asset
from sqlalchemy.orm.attributes import flag_modified

# Network mapping from CSV identifiers to database network IDs
NETWORK_MAPPING = {
    'btc': 'bitcoin',
    'eth': 'ethereum',
    'trx': 'tron',
    'sol': 'solana',
    'bep20': 'binance-smart-chain',
    'base': 'base',
    'avax': 'avalanche',
    'polygon': 'polygon-pos',
    'xrp': 'ripple',
    'ada': 'cardano',
    'doge': 'dogecoin',
    'xlm': 'stellar',
    'bch': 'bitcoin-cash',
    'ton': 'toncoin',
    'ltc': 'litecoin',
    'dot': 'polkadot',
    'etc': 'ethereum-classic',
    'xdai': 'xdai',
    'cro': 'cronos',
    'icp': 'internet-computer',
    'mnt': 'mantle',
    'vet': 'vechain',
    'fil': 'filecoin',
    'atom': 'cosmos',
    'algo': 'algorand',
    'arb': 'arbitrum-one',
    'tia': 'celestia',
    'erc20': 'ethereum',
    'trc20': 'tron',
    'spl': 'solana',
    'TON': 'toncoin',
    'sui': 'sui',
    'apt': 'aptos',
    'near': 'near-protocol',
}

def update_deposit_addresses(csv_path):
    app = create_app()
    with app.app_context():
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                coingecko_id = row['coingecko_id']
                symbol = row['symbol']
                csv_network = row['network']
                address = row['address']
                
                # Get corresponding database network ID
                db_network_id = NETWORK_MAPPING.get(csv_network)
                if not db_network_id:
                    print(f"⚠️ No mapping for network '{csv_network}'. Skipping {coingecko_id}/{symbol}")
                    continue
                
                # Find asset in database
                asset = Asset.query.filter_by(
                    coingecko_id=coingecko_id, 
                    symbol=symbol
                ).first()
                
                if not asset:
                    print(f"⏭️ Asset not found: {coingecko_id}/{symbol}")
                    continue
                
                if not asset.networks:
                    print(f"🔍 No networks defined for {coingecko_id}/{symbol}")
                    continue
                
                # Update deposit address for the specific network
                updated = False
                for network in asset.networks:
                    if network['id'] == db_network_id:
                        if network.get('deposit_address') != address:
                            network['deposit_address'] = address
                            updated = True
                        break
                
                if updated:
                    flag_modified(asset, "networks")
                    db.session.add(asset)
                    print(f"✅ Updated {coingecko_id}/{symbol} on {db_network_id}")
                else:
                    print(f"⏩ No update needed for {coingecko_id}/{symbol} on {db_network_id}")
            
            db.session.commit()
            print("🚀 All updates committed to database")

if __name__ == "__main__":
    update_deposit_addresses('bloxxchain-wallets-normalized.csv')