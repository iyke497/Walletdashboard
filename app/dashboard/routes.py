from flask import render_template, current_app
from flask_login import current_user, login_required
from app.models import Asset
from .services import PortfolioService, CoinGeckoService
from . import dashboard_bp

# @dashboard_bp.route("/", methods=["GET"])
# def index():
#     # For now just render a placeholder
#     return render_template("dashboard/index.html")


@dashboard_bp.route("/", methods=["GET"])
def index():
    # Fetch and store exchange rates
    # CoinGeckoService.fetch_and_store_rates()
    # Get current user's portfolio details
    portfolio = PortfolioService.get_portfolio_details(current_user.id, current_user.display_currency_id)

    return render_template("dashboard/index.html", portfolio=portfolio)

@dashboard_bp.route('/portfolio')
@login_required
def show_portfolio():
    base_currency_id = current_user.display_currency_id
    data = PortfolioService.get_portfolio_details(current_user.id, base_currency_id)

    currency_symbol = ""
    if base_currency_id:
        asset = Asset.query.get(base_currency_id)
        currency_symbol = asset.symbol if asset else ""

    return render_template(
        'dashboard/portfolio.html',
        portfolio=data['holdings'],
        total_value=data['total_value'],
        currency=currency_symbol
    )