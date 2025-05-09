from flask import render_template, request, jsonify
from app.copytrade import copytrade_bp

@copytrade_bp.route('/traders')
def trader_list():
    return render_template('copytrade/copy_trading_interface.html')




