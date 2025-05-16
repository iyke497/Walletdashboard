from flask import request, jsonify, render_template, flash, redirect, url_for, session
from flask_login import login_required, current_user
import base64
from . import wallet_bp
from .services import WalletService
from .forms import WithdrawForm, DepositForm
from app.models import Asset, AssetType, Holding
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

@wallet_bp.route('/deposit/crypto', methods=['GET'])
@login_required
def deposit_crypto_form():
    """Render the crypto deposit form"""
    form = DepositForm()
    # Get all active crypto assets
    crypto_assets = Asset.query.filter_by(
        asset_type=AssetType.CRYPTO,
        is_active=True,
        deleted_at=None
    ).limit(1000).all()

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

@wallet_bp.route('/get-networks/<asset_symbol>')
def get_networks(asset_symbol):
    asset = Asset.query.filter_by(symbol=asset_symbol).first()
    nets = [{'id': n['id'], 'symbol': n['symbol']} for n in (asset.networks or [])]
    #return jsonify(asset.networks if asset else [])  # Directly return the JSON array
    return jsonify(nets)

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
        
        # Redirect to success page or show success message
        return jsonify({
            'message': 'Crypto deposit successful',
            'transaction': {
                'id': transaction.id,
                'asset': asset_symbol,
                'amount': amount,
                'tx_hash': tx_hash,
                'timestamp': transaction.timestamp.isoformat()
            }
        }), 201
        
    except ValueError as e:
        logger.error(f"Value error in deposit: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error in deposit: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred'}), 500

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
            'balance': holding.balance if holding else 0
        })

    # Get recent withdrawals
    recent_withdrawals = WalletService.get_recent_crypto_withdrawals(current_user.id, limit=5)
    
    return render_template('wallet/withdraw_crypto.html',
                         form=form,
                         crypto_assets=serialized_assets,
                         recent_withdrawals=recent_withdrawals)

@wallet_bp.route('/withdraw/crypto', methods=['POST'])
@login_required
def withdraw_crypto():
    """Handle crypto withdrawal form submission"""
    try:
        asset_symbol = request.form.get('asset')
        amount = Decimal(request.form.get('amount'))
        address = request.form.get('address')

        # Basic validation
        if not all([asset_symbol, amount, address]):
            flash('All fields are required', 'danger')
            return redirect(url_for('wallet.withdraw_crypto_form'))

        # Process withdrawal
        transaction = WalletService.withdraw_crypto(
            user_id=current_user.id,
            asset_symbol=asset_symbol,
            amount=amount,
            destination_address=address
        )

        flash(f'Withdrawal of {amount} {asset_symbol} initiated!', 'success')
        return redirect(url_for('wallet.withdraw_crypto_form'))

    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('wallet.withdraw_crypto_form'))
    except Exception as e:
        logger.error(f"Withdrawal error: {str(e)}")
        flash('Failed to process withdrawal', 'danger')
        return redirect(url_for('wallet.withdraw_crypto_form'))

@wallet_bp.route('/transfer', methods=['POST'])
@login_required
def transfer():
    data = request.get_json()
    
    try:
        from_asset = data.get('from_asset')
        to_asset = data.get('to_asset')
        amount = float(data.get('amount'))
        
        if not all([from_asset, to_asset, amount]):
            return jsonify({'error': 'From asset, to asset, and amount are required'}), 400
            
        withdraw_tx, deposit_tx = WalletService.transfer(
            current_user.id,
            from_asset,
            to_asset,
            amount
        )
        
        return jsonify({
            'message': 'Transfer successful',
            'transactions': {
                'withdraw': {
                    'id': withdraw_tx.id,
                    'asset': from_asset,
                    'amount': amount,
                    'timestamp': withdraw_tx.timestamp.isoformat()
                },
                'deposit': {
                    'id': deposit_tx.id,
                    'asset': to_asset,
                    'amount': deposit_tx.amount,
                    'timestamp': deposit_tx.timestamp.isoformat()
                }
            }
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred'}), 500
