from app.models.transaction import Transaction

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