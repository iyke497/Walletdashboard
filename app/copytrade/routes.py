from flask import render_template, request, jsonify
from app.copytrade import copytrade_bp
from app.copytrade.services import get_list_of_traders
@copytrade_bp.route('/traders')
def trader_list():
    traders = get_list_of_traders()
    return render_template('copytrade/copy-trading.html', traders=traders)




