from flask import request, jsonify, render_template, Response
from flask_login import login_required, current_user
from . import wallet_bp
from .services import WalletService
from app.models import Asset, AssetType, NetworkType
import logging

logger = logging.getLogger(__name__)

@wallet_bp.route('/deposit/crypto', methods=['GET'])
@login_required
def deposit_crypto_form():
    """Render the crypto deposit form"""
    # Get all active crypto assets
    crypto_assets = Asset.query.filter_by(
        asset_type=AssetType.CRYPTO,
        is_active=True,
        deleted_at=None
    ).all()
    
    # Convert assets to serializable format with CoinGecko icons
    serialized_assets = [
        {
            'symbol': asset.symbol,
            'name': asset.name,
            'icon': f"https://assets.coingecko.com/coins/images/1/large/{asset.coingecko_id}.png"
        }
        for asset in crypto_assets
    ]
    
    return render_template('wallet/deposit_crypto.html', crypto_assets=serialized_assets)

@wallet_bp.route('/deposit/crypto/address/<asset_symbol>/<network>')
@login_required
def get_deposit_address(asset_symbol: str, network: str):
    """
    Get a deposit address for a specific asset and network.
    
    Args:
        asset_symbol: The symbol of the asset (e.g., 'BTC', 'ETH')
        network: The network type (e.g., 'BITCOIN', 'ETHEREUM')
    """
    try:
        # Convert network string to enum
        network_type = NetworkType[network.upper()]
        
        # Get deposit address
        deposit_address = WalletService.get_deposit_address(
            current_user.id,
            asset_symbol,
            network_type
        )
        
        return jsonify({
            'address': deposit_address.address,
            'network': network_type.value
        })
        
    except (ValueError, KeyError) as e:
        logger.error(f"Error getting deposit address: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error getting deposit address: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to get deposit address'}), 500

@wallet_bp.route('/deposit/crypto/qr/<asset_symbol>/<network>')
@login_required
def get_deposit_qr(asset_symbol: str, network: str):
    """
    Generate and return a QR code for a deposit address.
    
    Args:
        asset_symbol: The symbol of the asset (e.g., 'BTC', 'ETH')
        network: The network type (e.g., 'BITCOIN', 'ETHEREUM')
    """
    try:
        # Convert network string to enum
        network_type = NetworkType[network.upper()]
        
        # Get deposit address
        deposit_address = WalletService.get_deposit_address(
            current_user.id,
            asset_symbol,
            network_type
        )
        
        # Generate QR code
        qr_buffer = WalletService.generate_deposit_qr(deposit_address)
        
        # Return as PNG image
        return Response(
            qr_buffer.getvalue(),
            mimetype='image/png',
            headers={
                'Content-Disposition': f'attachment; filename={asset_symbol}_{network}_deposit_qr.png'
            }
        )
        
    except (ValueError, KeyError) as e:
        logger.error(f"Error generating QR code: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error generating QR code: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to generate QR code'}), 500

@wallet_bp.route('/deposit/crypto', methods=['POST'])
@login_required
def deposit_crypto():
    """Handle crypto deposit form submission"""
    try:
        # Log form data for debugging
        logger.info(f"Received deposit form data: {request.form}")
        
        # Get form data
        asset_symbol = request.form.get('coin')
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

@wallet_bp.route('/withdraw', methods=['POST'])
@login_required
def withdraw():
    data = request.get_json()
    
    try:
        asset_symbol = data.get('asset')
        amount = float(data.get('amount'))
        
        if not asset_symbol or not amount:
            return jsonify({'error': 'Asset and amount are required'}), 400
            
        transaction = WalletService.withdraw(current_user.id, asset_symbol, amount)
        return jsonify({
            'message': 'Withdrawal successful',
            'transaction': {
                'id': transaction.id,
                'asset': asset_symbol,
                'amount': amount,
                'timestamp': transaction.timestamp.isoformat()
            }
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred'}), 500

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
