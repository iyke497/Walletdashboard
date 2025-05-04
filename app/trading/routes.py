from decimal import Decimal
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from . import trading_bp
from .services import TradingService
from app.models import Asset

@trading_bp.route('/market', methods=['GET'])
@login_required
def market_trade():
    assets = Asset.query.filter_by(is_active=True).all()
    return render_template('trading/market.html', assets=assets)

@trading_bp.route('/api/orders/market', methods=['POST'])
@login_required
def execute_market_order():
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['base_asset', 'quote_asset', 'amount', 'side']
        if not all(k in data for k in required):
            return jsonify({'error': 'Missing required fields'}), 400

        # Get asset objects
        base = Asset.query.filter_by(symbol=data['base_asset']).first()
        quote = Asset.query.filter_by(symbol=data['quote_asset']).first()
        if not base or not quote:
            return jsonify({'error': 'Invalid asset symbols'}), 400

        # Convert amount to Decimal
        try:
            amount = Decimal(str(data['amount']))
        except:
            return jsonify({'error': 'Invalid amount format'}), 400

        # Execute order
        tx_pair = TradingService.execute_market_order(
            current_user.id,
            base,
            quote,
            amount,
            data['side'].lower()
        )

        return jsonify({
            'status': 'filled',
            'base_tx': tx_pair[0].id,
            'quote_tx': tx_pair[1].id,
            'executed_price': str(tx_pair[0].price)
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f'error: {e}')
        return jsonify({'error': 'Order execution failed'}), 500