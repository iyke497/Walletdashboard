from decimal import Decimal
import requests
from ..extensions import db, cache
from app.models.account import Account
from app.models.asset import CryptoAsset
from app.models.balance import AccountAssetBalance
from app.models.transaction import Transaction
from flask import current_app
from sqlalchemy import func, outerjoin
from sqlalchemy.exc import IntegrityError

COINGECKO_URL = 'https://api.coingecko.com/api/v3/simple/price'

def record_deposit(user_id: int,
                   account_type: str,
                   asset_symbol: str,
                   amount: Decimal,
                   reference: str) -> None:
    acct = Account.query.filter_by(user_id=user_id, account_type=account_type).first()
    if not acct:
        raise ValueError(f"No {account_type} account for user {user_id}")

    asset = CryptoAsset.query.filter_by(symbol=asset_symbol).one_or_none()
    if not asset:
        raise ValueError(f"Unsupported asset: {asset_symbol}")

    bal = (
        AccountAssetBalance.query
        .filter_by(account_id=acct.id, asset_id=asset.id)
        .with_for_update()
        .first()
    )
    if not bal:
        bal = AccountAssetBalance(
            account_id=acct.id,
            asset_id=asset.id,
            available_balance=Decimal('0'),
            frozen_balance=Decimal('0')
        )
        db.session.add(bal)

    txn = Transaction(
        account_id=acct.id,
        asset_id=asset.id,
        amount=amount,
        tx_type='deposit',
        reference=reference
    )
    db.session.add(txn)

    bal.available_balance += amount

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise

    current_app.logger.info(f"Deposit recorded: user={user_id} asset={asset_symbol} +{amount}")

# services.py
@cache.memoize()  # caches on (tuple(symbols), vs_currency)
def fetch_prices(cg_ids: tuple[str, ...], vs_currency: str = 'usd') -> dict:
    """
    symbols: ('btc','eth','sol',...)
    returns: { 'btc': {'usd': 29745.23, 'btc':1}, 'eth': {...}, … }
    """
    # CoinGecko expects comma-separated, lowercase ids
    ids = ','.join(cg_ids)
    resp = requests.get(COINGECKO_URL, params={
        'ids': ids,
        'vs_currencies': vs_currency,
    }, timeout=5)
    resp.raise_for_status()
    return resp.json()

def get_portfolio_valuation_old(user_id: int,
                            vs_currency: str = 'usd') -> dict:
    """
    Returns:
    {
      "assets": [
        {
          "asset": "BTC",
          "available": "0.015",
          "frozen": "0.000",
          "total": "0.015",
          "price_usd": "29745.23",
          "value_usd": "446.18"
        }, …
      ],
      "total_value_usd": "446.18"
    }
    """
    # 1️⃣ pull all balances
    balances = (
        AccountAssetBalance.query
        .filter(AccountAssetBalance.account.has(user_id=user_id))
        .join(AccountAssetBalance.asset)
        .all()
    )

    # 2️⃣ fetch live prices
    # build a list of coingecko_ids
    cg_ids    = tuple(b.asset.coingecko_id for b in balances)
    price_map = fetch_prices(cg_ids, vs_currency)

    # 3️⃣ compute per-asset and portfolio totals
    assets_out = []
    portfolio_total = Decimal('0')
    for b in balances:
        sym = b.asset.symbol
        
        cg_id   = b.asset.coingecko_id
        price   = Decimal(str(price_map.get(cg_id, {}).get(vs_currency, 0)))
        
        total_bal = b.total_balance
        value = total_bal * price
        portfolio_total += value

        assets_out.append({
            'asset':      sym,
            'available':  str(b.available_balance),
            'frozen':     str(b.frozen_balance),
            'total':      str(total_bal),
            f'price_{vs_currency}': str(price),
            f'value_{vs_currency}': str(value.quantize(Decimal('0.01'))),
        })

    return {
        'assets':           assets_out,
        f'total_value_{vs_currency}': str(portfolio_total.quantize(Decimal('0.01')))
    }

def get_portfolio_valuation(user_id: int,
                            vs_currency: str = 'usd') -> dict:
    """
    Returns all supported assets, with user balances (zero if none),
    live price and USD value, plus a portfolio total.
    """
    # 1️⃣ Query all assets + left-joined balances
    bal_alias = outerjoin(
        CryptoAsset,
        AccountAssetBalance,
        db.and_(
            AccountAssetBalance.asset_id == CryptoAsset.id,
            AccountAssetBalance.account.has(user_id=user_id)
        )
    )

    rows = (
        db.session.query(
            CryptoAsset,
            func.coalesce(AccountAssetBalance.available_balance, 0).label('available'),
            func.coalesce(AccountAssetBalance.frozen_balance,    0).label('frozen')
        )
        .select_from(bal_alias)
        .all()
    )

    # 2️⃣ Fetch live prices
    cg_ids = tuple(asset.coingecko_id for asset, _, _ in rows)
    price_map = fetch_prices(cg_ids, vs_currency)

    # 3️⃣ Build output
    assets_out      = []
    portfolio_total = Decimal('0')
    for asset, avail, frozen in rows:
        total = Decimal(avail) + Decimal(frozen)
        price = Decimal(str(price_map.get(asset.coingecko_id, {}).get(vs_currency, 0)))
        value = total * price
        portfolio_total += value

        assets_out.append({
            'asset':      asset.symbol,
            'available':  str(Decimal(avail)),
            'frozen':     str(Decimal(frozen)),
            'total':      str(total),
            f'price_{vs_currency}': str(price),
            f'value_{vs_currency}': str(value.quantize(Decimal('0.01'))),
        })

    return {
        'assets':                assets_out,
        f'total_value_{vs_currency}': str(portfolio_total.quantize(Decimal('0.01')))
    }