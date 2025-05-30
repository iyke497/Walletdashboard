from app.models import Trader, CopyTrade, User
from app.extensions import db

def get_traders(sort_by='win_rate', sort_order='desc', market='all', time_period='all'):
    query = db.session.query(Trader)
    
def get_list_of_traders_old():
    return db.session.query(Trader).order_by(Trader.win_rate.desc()).all()

def get_trader_by_id(trader_id):
    return db.session.query(Trader).filter_by(id=trader_id).first()

# services.py - Updated get_list_of_traders function
def get_list_of_traders(search=None, sort_by='win_rate', sort_order='desc', 
                       page=1, per_page=10, market='all', time_period='all'):
    # Base query
    query = Trader.query.filter_by(deleted_at=None)
    
    # Search filter
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                Trader.user.has(User.username.ilike(search_filter)),
                Trader.bio.ilike(search_filter),
                Trader.tags.ilike(search_filter)
            )
        )
    
    # Market filter
    if market != 'all':
        query = query.filter(Trader.tags.ilike(f"%{market}%"))
    
    # Sort handling
    sort_column = {
        'win_rate': Trader.win_rate,
        'avg_monthly_return': Trader.avg_monthly_return,
        'max_drawdown': Trader.max_drawdown,
        'followers': db.func.count(CopyTrade.id)
    }.get(sort_by, Trader.win_rate)
    
    if sort_order == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Pagination
    return query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )