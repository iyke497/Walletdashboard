from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.wallet.services import get_portfolio_data

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('')
@login_required
def index(): # import db from your extensions
    data = get_portfolio_data(current_user.id)
    return render_template('dashboard/dashboard.html', portfolio=data)