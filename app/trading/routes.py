from decimal import Decimal
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from . import trading_bp
from .services import TradingService, OrderBookService
from app.models import Asset
from app.trading.forms import MarketOrderForm, LimitOrderForm

@trading_bp.route('/market', methods=['GET'])
@login_required
def market_trade():
    assets = Asset.query.filter_by(is_active=True).all()
    return render_template('trading/market.html', assets=assets, form=MarketOrderForm())

@trading_bp.route('/api/orders/market', methods=['POST'])
@login_required
def execute_market_order():
    try:
        data = request.get_json()
        print(f"Received market order request: {data}")  # Debug log
        
        # Validate required fields
        required = ['base_asset', 'quote_asset', 'amount', 'side']
        if not all(k in data for k in required):
            print(f"Missing required fields. Received: {data}")  # Debug log
            return jsonify({'error': 'Missing required fields'}), 400

        # Get asset objects
        base = Asset.query.filter_by(symbol=data['base_asset']).first()
        quote = Asset.query.filter_by(symbol=data['quote_asset']).first()
        if not base or not quote:
            print(f"Invalid asset symbols. Base: {data['base_asset']}, Quote: {data['quote_asset']}")  # Debug log
            return jsonify({'error': 'Invalid asset symbols'}), 400

        # Convert amount to Decimal
        try:
            amount = Decimal(str(data['amount']))
            print(f"Converted amount: {amount}")  # Debug log
        except Exception as e:
            print(f"Amount conversion error: {e}")  # Debug log
            return jsonify({'error': 'Invalid amount format'}), 400

        # Execute order
        try:
            tx_pair = TradingService.execute_market_order(
                current_user.id,
                base,
                quote,
                amount,
                data['side'].lower()
            )
            print(f"Order executed successfully. TX pair: {tx_pair}")  # Debug log
        except Exception as e:
            print(f"Order execution error: {e}")  # Debug log
            return jsonify({'error': str(e)}), 400

        return jsonify({
            'status': 'filled',
            'base_tx': tx_pair[0].id,
            'quote_tx': tx_pair[1].id,
            'executed_price': str(tx_pair[0].price)
        }), 200

    except Exception as e:
        print(f'Unexpected error in market order: {e}')  # Debug log
        return jsonify({'error': 'Order execution failed'}), 500

#ToDo: Rename the route to be congruent with naming convention
@trading_bp.route('/limit', methods=['GET'])
@login_required
def limit_trade():
    assets = Asset.query.filter_by(is_active=True).all()
    
    # Get default trading pair (e.g., BTC/USDT)
    default_base = Asset.query.filter_by(symbol='btc').first()
    default_quote = Asset.query.filter_by(symbol='usdt').first()

    print("*"*50)
    print(default_base)
    
    # Get market data
    ticker = TradingService.get_ticker(default_base, default_quote)
    current_price = ticker['last']
    price_change = ticker['percentage']
    daily_volume = ticker['quoteVolume']
    
    # Get order book data
    order_book = OrderBookService.get_order_book(default_base.id, default_quote.id)
    
    
    # Get recent trades
    recent_trades = [] # TODO: Implement recent trades fetching
    
    # Get trading pairs
    trading_pairs = [f"{asset.symbol}/USDT" for asset in assets if asset.symbol != 'USDT']
    
    # Initialize forms
    market_order_form = MarketOrderForm()
    limit_order_form = LimitOrderForm()

    return render_template('main/under-maintenance.html')
    
    # return render_template('trading/limit.html',
    #                      assets=assets,
    #                      trading_pairs=trading_pairs,
    #                      current_price=current_price,
    #                      price_change=price_change,
    #                      daily_volume=daily_volume,
    #                      order_book=order_book,
    #                      recent_trades=recent_trades,
    #                      market_order_form=market_order_form,
    #                      limit_order_form=limit_order_form) y2fhRxSzU4oub2u






@trading_bp.route('/api/orders/limit', methods=['POST'])
@login_required
def place_limit_order():
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['base_asset', 'quote_asset', 'amount', 'price', 'side']
        if not all(k in data for k in required):
            return jsonify({'error': 'Missing required fields'}), 400

        # Get asset objects
        base = Asset.query.filter_by(symbol=data['base_asset']).first()
        quote = Asset.query.filter_by(symbol=data['quote_asset']).first()
        if not base or not quote:
            return jsonify({'error': 'Invalid asset symbols'}), 400

        # Convert amounts to Decimal
        try:
            amount = Decimal(str(data['amount']))
            price = Decimal(str(data['price']))
        except:
            return jsonify({'error': 'Invalid amount or price format'}), 400

        # Place limit order
        order = OrderBookService.place_limit_order(
            current_user.id,
            base,
            quote,
            amount,
            price,
            data['side'].lower()
        )

        return jsonify({
            'status': 'open',
            'order_id': order.id,
            'amount': str(order.amount),
            'price': str(order.price)
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f'error: {e}')
        return jsonify({'error': 'Order placement failed'}), 500

@trading_bp.route('/api/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    try:
        success = OrderBookService.cancel_order(current_user.id, order_id)
        if not success:
            return jsonify({'error': 'Order not found or not cancellable'}), 404
            
        return jsonify({'status': 'cancelled'}), 200
    except Exception as e:
        print(f'error: {e}')
        return jsonify({'error': 'Order cancellation failed'}), 500

@trading_bp.route('/api/orderbook/<base_asset>/<quote_asset>', methods=['GET'])
@login_required
def get_order_book(base_asset, quote_asset):
    try:
        base = Asset.query.filter_by(symbol=base_asset).first()
        quote = Asset.query.filter_by(symbol=quote_asset).first()
        if not base or not quote:
            return jsonify({'error': 'Invalid asset symbols'}), 400

        order_book = OrderBookService.get_order_book(base.id, quote.id)
        return jsonify(order_book), 200
    except Exception as e:
        print(f'error: {e}')
        return jsonify({'error': 'Failed to fetch order book'}), 500