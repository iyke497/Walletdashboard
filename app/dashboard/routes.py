from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.wallet.services import get_portfolio_data
from .services import get_portfolio_valuation

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard', template_folder='templates')

@bp.route('/')
@login_required
def index():
    """
    Returns JSON:
    [
      {
        "asset": "BTC",
        "available": "0.12345678",
        "frozen": "0.00000000",
        "total": "0.12345678"
      }, …
    ]
    """
    
    vs = request.args.get('vs', 'usd').lower()
    payload = get_portfolio_valuation(current_user.id, vs_currency=vs)
    return jsonify(payload), 200