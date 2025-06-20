from flask import request, jsonify, render_template, flash, redirect, url_for, session
from flask_login import login_required, current_user
import base64
from . import wallet_bp
from app.extensions import db
from app.decorators import email_verified_required
from .services import WalletService
from .forms import WithdrawForm, DepositForm
from app.models import Asset, AssetType, Holding
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)


# ********** Deposit **********

@wallet_bp.route('/deposit/crypto', methods=['GET'])
@login_required
@email_verified_required
def deposit_crypto_form():
    """Render the crypto deposit form"""
    form = DepositForm()
    # Get first 20 most popular crypto assets for initial display
    crypto_assets = Asset.query.filter_by(
        asset_type=AssetType.CRYPTO,
        is_active=True,
        deleted_at=None
    ).limit(20).all() 

    # Convert assets to serializable format with CoinGecko icons
    serialized_assets = [
        {
            'symbol': asset.symbol,
            'name': asset.name,
            'images': asset.images.get('thumb') if asset.images else None
        }
        for asset in crypto_assets
    ]

    # Fetch recent deposits for the current user
    recent_deposits = WalletService.get_recent_crypto_deposits(current_user.id, limit=5)
    
    return render_template('wallet/deposit_crypto_fixed.html',
                           form=form, 
                           crypto_assets=serialized_assets, 
                           recent_deposits=recent_deposits)

@wallet_bp.route('/search-assets/<search_term>')
@login_required
def search_assets(search_term):
    """Search crypto assets by name or symbol"""
    # Search in database with ILIKE for case-insensitive partial matching
    crypto_assets = Asset.query.filter(
        Asset.asset_type == AssetType.CRYPTO,
        Asset.is_active == True,
        Asset.deleted_at == None,
        db.or_(
            Asset.name.ilike(f'%{search_term}%'),
            Asset.symbol.ilike(f'%{search_term}%')
        )
    ).limit(50).all()

    # Convert to JSON format
    serialized_assets = [
        {
            'symbol': asset.symbol,
            'name': asset.name,
            'images': asset.images.get('thumb') if asset.images else None
        }
        for asset in crypto_assets
    ]

    return jsonify(serialized_assets)

# @wallet_bp.route('/get-networks/<asset_symbol>')
# def get_networks(asset_symbol):
#     asset = Asset.query.filter_by(symbol=asset_symbol).first()
#     nets = [{'id': n['id'], 'symbol': n['symbol']} for n in (asset.networks or [])]
#     #return jsonify(asset.networks if asset else [])  # Directly return the JSON array
#     return jsonify(nets)

# --- NEW NETWORKS FETCH ---

@wallet_bp.route('/get-networks/<asset_symbol>')
def get_networks(asset_symbol):
    asset = Asset.query.filter_by(symbol=asset_symbol).first()
    
    if not asset or not asset.networks:
        return jsonify([])
    
    # Filter networks that have deposit_address field populated
    networks_with_deposits = [
        {
            'id': n['id'], 
            'symbol': n['symbol'],
            'deposit_address': n.get('deposit_address')  # Include address if needed
        }
        for n in asset.networks 
        if n.get('deposit_address')  # Only include if deposit_address exists and is not empty
    ]

    return jsonify(networks_with_deposits)

@wallet_bp.route('/deposit-info/<asset_symbol>/<network_id>')
@login_required
def get_deposit_info(asset_symbol, network_id):
    """ Retreive wallet address for specific network id. Dynamically generate QR code and metadata. """
    rec = WalletService.get_deposit_info(asset_symbol, network_id)
    qr_buf = WalletService.generate_qr_png(rec['deposit_address'])
    # Encode PNG → base64 for easy embedding
    b64 = base64.b64encode(qr_buf.getvalue()).decode()
    return jsonify({
        "address": rec["deposit_address"],
        "qr": f"data:image/png;base64,{b64}",
        "minimum_deposit": rec.get("minimum_deposit"),
        "fees": rec.get("fees")
    })

@wallet_bp.route('/deposit/crypto', methods=['POST'])
@login_required
@email_verified_required
def deposit_crypto():
    """Handle crypto deposit form submission"""
    try:
        # Log form data for debugging
        logger.info(f"Received deposit form data: {request.form}")
        
        # Get form data
        asset_symbol = request.form.get('asset')
        amount = float(request.form.get('amount'))
        tx_hash = request.form.get('tx_hash')  # Optional blockchain transaction hash
        
        logger.info(f"Processing deposit: asset={asset_symbol}, amount={amount}, tx_hash={tx_hash}")
        
        if not asset_symbol or not amount:
            logger.warning("Missing required fields in deposit form")
            return jsonify({'error': 'Asset and amount are required'}), 400
            
        transaction = WalletService.deposit_crypto(current_user.id, asset_symbol, amount, tx_hash)
        
        logger.info(f"Successfully processed deposit: transaction_id={transaction.id}")
        
        # Better UX - Different message for pending vs confirmed
        if transaction.status.value == 'pending':
            return jsonify({
                'success': True,
                'status': 'pending',
                'message': '⏳ Deposit Submitted!',
                'details': 'Your deposit is being processed and will appear in your balance once confirmed by our team.',
                'transaction': {
                    'id': transaction.id,
                    'asset': asset_symbol,
                    'amount': amount,
                    'status': 'pending',
                    'timestamp': transaction.timestamp.isoformat()
                }
            }), 201
        else:
            return jsonify({
                'success': True,
                'status': 'confirmed',
                'message': '✅ Deposit Confirmed!',
                'details': 'Your deposit has been added to your balance.',
                'transaction': {
                    'id': transaction.id,
                    'asset': asset_symbol,
                    'amount': amount,
                    'status': 'confirmed',
                    'timestamp': transaction.timestamp.isoformat()
                }
            }), 201
        
    except ValueError as e:
        logger.error(f"Value error in deposit: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Unexpected error in deposit: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred'
        }), 500

@wallet_bp.route('/deposit/fiat', methods=['POST'])
@login_required
def deposit_fiat():
    data = request.get_json()
    
    try:
        asset_symbol = data.get('asset')
        amount = float(data.get('amount'))
        reference = data.get('reference')  # Optional bank reference or payment ID
        
        if not asset_symbol or not amount:
            return jsonify({'error': 'Asset and amount are required'}), 400
            
        transaction = WalletService.deposit_fiat(current_user.id, asset_symbol, amount, reference)
        return jsonify({
            'message': 'Fiat deposit successful',
            'transaction': {
                'id': transaction.id,
                'asset': asset_symbol,
                'amount': amount,
                'reference': reference,
                'timestamp': transaction.timestamp.isoformat()
            }
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred'}), 500

# ********** Withdraw **********
@wallet_bp.route('/withdraw/crypto', methods=['GET'])
@login_required
@email_verified_required
def withdraw_crypto_form():
    """Render crypto withdrawal form"""
    form = WithdrawForm()
    
    # Get crypto assets with balances
    crypto_assets = Asset.query.filter_by(
        asset_type=AssetType.CRYPTO,
        is_active=True,
        deleted_at=None
    ).join(Holding).filter(
        Holding.user_id == current_user.id,
        Holding.balance > 0
    ).all()

    # Add balance info to assets
    serialized_assets = []
    for asset in crypto_assets:
        holding = next((h for h in current_user.holdings if h.asset_id == asset.id), None)
        serialized_assets.append({
            'symbol': asset.symbol,
            'name': asset.name,
            'balance': holding.balance if holding else 0,
            'images': asset.images.get('thumb') if asset.images else None
        })

    # Get recent withdrawals
    recent_withdrawals = WalletService.get_recent_crypto_withdrawals(current_user.id, limit=5)
    
    return render_template('wallet/withdraw_crypto_fixed.html',  # Updated template name
                         form=form,
                         crypto_assets=serialized_assets,
                         recent_withdrawals=recent_withdrawals)

@wallet_bp.route('/withdraw/crypto', methods=['POST'])
@login_required
def withdraw_crypto():
    """Handle crypto withdrawal form submission - supports both form data and JSON"""
    try:
        # Handle both form data (with CSRF) and JSON data
        if request.is_json:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Missing request body'}), 400
            
            asset_symbol = data.get('asset')
            amount_str = data.get('amount')
            address = data.get('address')
            network_id = data.get('network')
        else:
            # Form data (with CSRF protection)
            asset_symbol = request.form.get('asset')
            amount_str = request.form.get('amount')
            address = request.form.get('address')
            network_id = request.form.get('network')

        # Validate presence of all fields
        if not all([asset_symbol, amount_str, address]):
            return jsonify({'error': 'Asset, amount, and address are required'}), 400

        # Convert amount to Decimal safely
        try:
            amount = Decimal(amount_str)
            if amount <= Decimal('0'):
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError, InvalidOperation):
            return jsonify({'error': 'Invalid amount format'}), 400

        # Process withdrawal
        transaction = WalletService.withdraw_crypto(
            user_id=current_user.id,
            asset_symbol=asset_symbol,
            amount=amount,
            destination_address=address
        )

        return jsonify({
            'success': True,
            'message': f'Withdrawal of {amount} {asset_symbol} initiated!',
            'tx_id': transaction.id
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Withdrawal error: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to process withdrawal'}), 500

@wallet_bp.route('/verify-withdrawal', methods=['POST'])
@login_required
def verify_withdrawal():
    """Verify withdrawal details before processing"""
    try:
        # Handle both form data and JSON
        if request.is_json:
            data = request.get_json()
            asset_symbol = data.get('asset')
            amount_str = data.get('amount')
            address = data.get('address')
        else:
            # Form data (with CSRF protection)
            asset_symbol = request.form.get('asset')
            amount_str = request.form.get('amount')
            address = request.form.get('address')

        # Basic validation
        if not all([asset_symbol, amount_str, address]):
            return jsonify({'error': 'All fields are required'}), 400
        
        # Convert amount to Decimal safely
        try:
            amount = Decimal(amount_str)
            if amount <= Decimal('0'):
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError, InvalidOperation):
            return jsonify({'error': 'Invalid amount format'}), 400

        # Check if asset exists
        asset = Asset.query.filter_by(symbol=asset_symbol).first()
        if not asset:
            return jsonify({'error': f'Asset {asset_symbol} not found'}), 400

        # Check balance
        holding = Holding.query.filter_by(
            user_id=current_user.id,
            asset_id=asset.id
        ).first()

        if not holding or holding.balance < amount:
            return jsonify({'error': 'Insufficient balance'}), 400

        # Additional validation can be added here
        # - Address format validation
        # - Minimum withdrawal amounts
        # - Daily withdrawal limits
        # - etc.

        return jsonify({
            'valid': True,
            'message': 'Withdrawal verification successful',
            'available_balance': float(holding.balance),
            'withdrawal_amount': float(amount)
        })

    except Exception as e:
        logger.error(f"Withdrawal verification error: {str(e)}", exc_info=True)
        return jsonify({'error': 'Verification failed'}), 500