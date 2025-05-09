from app.models import Trader, CopyTrade
from app.extensions import db

def get_traders(sort_by='win_rate', sort_order='desc', market='all', time_period='all'):
    query = db.session.query(Trader)
    
def get_list_of_traders():
    return db.session.query(Trader).order_by(Trader.win_rate.desc()).all()

def get_trader_by_id(trader_id):
    return db.session.query(Trader).filter_by(id=trader_id).first()

