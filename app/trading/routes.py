from decimal import Decimal
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import trading_bp
from .services import TradingService, OrderBookService, CryptoSwapService, SwapError
from app.extensions import db
from app.models import Asset, Holding
from app.trading.forms import MarketOrderForm, LimitOrderForm, SwapForm

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
    

# ------------ Swap Routes ----------------

@trading_bp.route('/swap', methods=['GET', 'POST'])
@login_required
def swap():
    """Main crypto swap interface"""
    form = SwapForm(user_id=current_user.id)
    
    swap_preview = None
    show_preview = False
    
    if form.validate_on_submit():
        try:
            if form.preview_swap.data:
                # Generate swap preview
                swap_preview = CryptoSwapService.calculate_swap_preview(
                    from_asset_id=form.from_asset_id.data,
                    to_asset_id=form.to_asset_id.data,
                    from_amount=form.from_amount.data
                )
                show_preview = True
                flash('Swap preview generated successfully', 'info')
                
            elif form.execute_swap.data:
                # Execute the swap
                result = CryptoSwapService.execute_swap(
                    user_id=current_user.id,
                    from_asset_id=form.from_asset_id.data,
                    to_asset_id=form.to_asset_id.data,
                    from_amount=form.from_amount.data
                )
                
                if result['success']:
                    flash(
                        f"Swap executed successfully! "
                        f"Swapped {result['from_amount']} to {result['to_amount']} "
                        f"(Fee: {result['fee_amount']})",
                        'success'
                    )
                    return redirect(url_for('trading.swap_history'))
                else:
                    flash('Swap execution failed', 'error')
                    
        except SwapError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash(f'An unexpected error occurred: {str(e)}', 'error')
    
    # Get user holdings for display
    user_holdings = CryptoSwapService.get_user_crypto_holdings(current_user.id)
    
    return render_template(
        'trading/swap.html',
        form=form,
        swap_preview=swap_preview,
        show_preview=show_preview,
        user_holdings=user_holdings
    )


@trading_bp.route('/swap/history')
@login_required
def swap_history():
    """View swap transaction history"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get recent swaps
    recent_swaps = CryptoSwapService.get_recent_swaps(current_user.id, limit=100)
    
    # Simple pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_swaps = recent_swaps[start_idx:end_idx]
    
    has_prev = page > 1
    has_next = len(recent_swaps) > end_idx
    
    return render_template(
        'trading/swap_history.html',
        transactions=paginated_swaps,
        page=page,
        has_prev=has_prev,
        has_next=has_next
    )


@trading_bp.route('/api/swap-preview', methods=['POST'])
@login_required
def api_swap_preview():
    """API endpoint for real-time swap preview"""
    try:
        data = request.get_json()
        
        from_asset_id = int(data.get('from_asset_id'))
        to_asset_id = int(data.get('to_asset_id'))
        from_amount = Decimal(str(data.get('from_amount', 0)))
        
        if from_amount <= 0:
            return jsonify({'error': 'Amount must be greater than 0'}), 400
        
        # Validate swap
        is_valid, error_msg = CryptoSwapService.validate_swap(
            current_user.id, from_asset_id, to_asset_id, from_amount
        )
        
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # Calculate preview
        preview = CryptoSwapService.calculate_swap_preview(
            from_asset_id, to_asset_id, from_amount
        )
        
        return jsonify({
            'success': True,
            'from_amount': str(preview['from_amount']),
            'to_amount': str(preview['net_to_amount']),
            'rate': str(preview['rate']),
            'fee_amount': str(preview['fee_amount']),
            'fee_percentage': str(preview['fee_percentage']),
            'from_asset_symbol': preview['from_asset'].symbol,
            'to_asset_symbol': preview['to_asset'].symbol
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trading_bp.route('/api/user-balance/<int:asset_id>')
@login_required
def api_user_balance(asset_id):
    """Get user balance for specific asset"""
    try:
        balance = CryptoSwapService.get_user_balance(current_user.id, asset_id)
        asset = Asset.query.get(asset_id)
        
        return jsonify({
            'balance': str(balance),
            'symbol': asset.symbol if asset else '',
            'name': asset.name if asset else ''
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500