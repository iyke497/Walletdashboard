from app.models.transaction import Transaction
from ..extensions import db

class WalletService:
    def __init__(self, db):
        self.db = db

    def create_deposit(self, user_id, amount, currency):
        if amount <= 0:
            raise InvalidAmountError("Deposit must be positive")
        
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            currency=currency,
            type='DEPOSIT'
        )
        
        self.db.session.add(transaction)
        self.db.session.commit()
        return transaction

def get_portfolio_data(user_id):
    """
    Returns a dict mapping each currency to the user's net balance,
    based on all their transactions.
    """
    # pull all transactions for this user
    txs = Transaction.query.filter_by(user_id=user_id).all()
    portfolio = {}
    for t in txs:
        portfolio.setdefault(t.currency, 0)
        if t.type == 'DEPOSIT':
            portfolio[t.currency] += t.amount
        elif t.type == 'WITHDRAW':
            portfolio[t.currency] -= t.amount
        # you can extend: handle trades, stakes, etc.
    return portfolio

def record_deposit(user_id, currency, amount):
    return WalletService(db).create_deposit(user_id, amount, currency)

def record_withdraw(user_id, currency, amount):
    return WalletService(db).create_withdraw(user_id, amount, currency)

def execute_trade(user_id, from_currency, to_currency, amount):
    return WalletService(db).execute_trade(user_id, from_currency, to_currency, amount)

def record_stake(user_id, currency, amount, duration):
    return WalletService(db).record_stake(user_id, amount, currency, duration)
