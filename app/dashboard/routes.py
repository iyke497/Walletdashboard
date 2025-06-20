from flask import render_template, current_app
from app.extensions import db
from flask_login import current_user, login_required
from app.models import Asset, CopyTrade
from .services import PortfolioService, CoinGeckoService
from . import dashboard_bp


@dashboard_bp.route('/portfolio')
@login_required
def show_portfolio():
    base_currency_id = current_user.display_currency_id
    data = PortfolioService.get_portfolio_details(current_user.id, base_currency_id)

    day_change = PortfolioService.get_portfolio_24h_change(current_user.id, current_user.display_currency_id)

    currency_symbol = ""
    if base_currency_id:
        asset = Asset.query.get(base_currency_id)
        currency_symbol = asset.symbol if asset else ""

    # NEW: Get followed traders for dashboard display
    followed_traders = CopyTrade.query.filter_by(
    follower_id=current_user.id,
    is_active=True).all()  # Simple query that works

    return render_template(
        'dashboard/portfolio.html',
        portfolio=data['holdings'],
        total_value=data['total_value'],
        currency=currency_symbol,
        day_change=day_change,
        followed_traders=followed_traders
    )