# app/admin/routes.py
from flask import render_template, flash, redirect, url_for, request, jsonify
from datetime import datetime, timedelta
import random
from decimal import Decimal
from flask_login import login_required
from . import admin_bp
from app.decorators import admin_required
from app.models import Transaction, TransactionType, TransactionStatus, User, Asset, AssetType, Trader, CopyTrade, CopyTradeTransaction
from app.wallet.services import WalletService
from app.extensions import db
from .forms import AssetForm, AssetSearchForm
import json
import logging

logger = logging.getLogger(__name__)

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Simple admin dashboard"""
    # Quick stats
    total_users = User.query.count()
    pending_deposits = Transaction.query.filter_by(
        tx_type=TransactionType.DEPOSIT,
        status=TransactionStatus.PENDING
    ).count()
    
    recent_transactions = Transaction.query.order_by(
        Transaction.timestamp.desc()
    ).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         pending_deposits=pending_deposits,
                         recent_transactions=recent_transactions)

@admin_bp.route('/pending-deposits')
@login_required
@admin_required
def pending_deposits():
    """View all pending deposits"""
    deposits = Transaction.query.filter_by(
        tx_type=TransactionType.DEPOSIT,
        status=TransactionStatus.PENDING
    ).order_by(Transaction.timestamp.desc()).all()
    
    return render_template('admin/pending_deposits.html', deposits=deposits)

@admin_bp.route('/confirm-deposit/<int:transaction_id>')
@login_required
@admin_required
def confirm_deposit(transaction_id):
    """Confirm a pending deposit"""
    try:
        WalletService.confirm_deposit(transaction_id)
        flash(f'Deposit {transaction_id} confirmed successfully!', 'success')
    except Exception as e:
        flash(f'Error confirming deposit: {str(e)}', 'error')
    
    return redirect(url_for('admin.pending_deposits'))

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """View all users"""
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('admin/users.html', users=users)

@admin_bp.route('/transactions')
@login_required
@admin_required
def transactions():
    """View all transactions"""
    page = request.args.get('page', 1, type=int)
    transactions = Transaction.query.order_by(
        Transaction.timestamp.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/transactions.html', transactions=transactions)

# --------- Assets ------------
# ========== ASSET MANAGEMENT ROUTES ==========

@admin_bp.route('/assets')
@login_required
@admin_required
def assets_list():
    """List all assets with search and filter capabilities"""
    search_form = AssetSearchForm(request.args)
    
    # Build query
    query = Asset.query.filter(Asset.deleted_at.is_(None))
    
    # Apply search filters
    if search_form.search.data:
        search_term = f"%{search_form.search.data}%"
        query = query.filter(
            db.or_(
                Asset.symbol.ilike(search_term),
                Asset.name.ilike(search_term),
                Asset.coingecko_id.ilike(search_term)
            )
        )
    
    if search_form.asset_type.data:
        query = query.filter(Asset.asset_type == search_form.asset_type.data)
    
    if search_form.status.data:
        if search_form.status.data == 'active':
            query = query.filter(Asset.is_active == True)
        elif search_form.status.data == 'inactive':
            query = query.filter(Asset.is_active == False)
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    assets = query.order_by(Asset.symbol).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Statistics
    stats = {
        'total': Asset.query.filter(Asset.deleted_at.is_(None)).count(),
        'active': Asset.query.filter(Asset.is_active == True, Asset.deleted_at.is_(None)).count(),
        'inactive': Asset.query.filter(Asset.is_active == False, Asset.deleted_at.is_(None)).count(),
        'crypto': Asset.query.filter(Asset.asset_type == AssetType.CRYPTO, Asset.deleted_at.is_(None)).count(),
    }
    
    return render_template('admin/assets_list.html',
                         assets=assets,
                         search_form=search_form,
                         stats=stats)

@admin_bp.route('/assets/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_asset():
    """Create a new asset"""
    form = AssetForm()
    
    if form.validate_on_submit():
        try:
            # Parse JSON fields
            images = None
            if form.images_json.data and form.images_json.data.strip():
                images = json.loads(form.images_json.data)
            
            networks = None
            if form.networks_json.data and form.networks_json.data.strip():
                networks = json.loads(form.networks_json.data)
            
            # Create new asset
            asset = Asset(
                symbol=form.symbol.data.upper(),
                name=form.name.data,
                coingecko_id=form.coingecko_id.data.lower(),
                asset_type=AssetType(form.asset_type.data),
                decimals=form.decimals.data,
                images=images,
                networks=networks,
                is_active=form.is_active.data
            )
            
            db.session.add(asset)
            db.session.commit()
            
            flash(f'✅ Asset {asset.symbol} created successfully!', 'success')
            return redirect(url_for('admin.assets_list'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating asset: {str(e)}")
            flash(f'❌ Error creating asset: {str(e)}', 'error')
    
    return render_template('admin/asset_form.html', form=form, title='Create Asset')

# Replace your edit_asset route with this debug version temporarily
@admin_bp.route('/assets/<int:asset_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_asset(asset_id):
    """Edit an existing asset - Debug Version"""
    print(f"DEBUG: Editing asset ID: {asset_id}")
    
    asset = Asset.query.get_or_404(asset_id)
    print(f"DEBUG: Found asset: {asset.symbol}")
    
    if request.method == 'GET':
        print("DEBUG: GET request - creating form")
        form = AssetForm()
        
        # Manually populate all fields
        form.symbol.data = asset.symbol
        form.name.data = asset.name
        form.coingecko_id.data = asset.coingecko_id
        form.asset_type.data = asset.asset_type.value
        form.decimals.data = asset.decimals
        form.is_active.data = asset.is_active
        
        # Populate JSON fields
        if asset.images:
            form.images_json.data = json.dumps(asset.images, indent=2)
        if asset.networks:
            form.networks_json.data = json.dumps(asset.networks, indent=2)
            
        print("DEBUG: Form populated, rendering template")
        
    else:
        print("DEBUG: POST request - validating form")
        form = AssetForm()
        
        if form.validate_on_submit():
            print("DEBUG: Form is valid, updating asset")
            try:
                # Parse JSON fields
                images = None
                if form.images_json.data and form.images_json.data.strip():
                    images = json.loads(form.images_json.data)
                
                networks = None
                if form.networks_json.data and form.networks_json.data.strip():
                    networks = json.loads(form.networks_json.data)
                
                # Update asset
                asset.symbol = form.symbol.data.upper()
                asset.name = form.name.data
                asset.coingecko_id = form.coingecko_id.data.lower()
                asset.asset_type = AssetType(form.asset_type.data)
                asset.decimals = form.decimals.data
                asset.images = images
                asset.networks = networks
                asset.is_active = form.is_active.data
                
                db.session.commit()
                
                flash(f'✅ Asset {asset.symbol} updated successfully!', 'success')
                return redirect(url_for('admin.assets_list'))
                
            except Exception as e:
                db.session.rollback()
                print(f"DEBUG: Error updating asset: {str(e)}")
                flash(f'❌ Error updating asset: {str(e)}', 'error')
        else:
            print(f"DEBUG: Form validation failed: {form.errors}")
    
    print("DEBUG: Rendering template")
    return render_template('admin/asset_form.html', 
                         form=form, 
                         asset=asset, 
                         title=f'Edit Asset - {asset.symbol}')
@admin_bp.route('/assets/<int:asset_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_asset_status(asset_id):
    """Toggle asset active/inactive status"""
    asset = Asset.query.get_or_404(asset_id)
    
    try:
        asset.is_active = not asset.is_active
        db.session.commit()
        
        status = "activated" if asset.is_active else "deactivated"
        flash(f'✅ Asset {asset.symbol} {status} successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling asset status: {str(e)}")
        flash(f'❌ Error updating asset status: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('admin.assets_list'))

@admin_bp.route('/assets/<int:asset_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_asset(asset_id):
    """Soft delete an asset"""
    asset = Asset.query.get_or_404(asset_id)
    
    try:
        # Check if asset has any holdings or transactions
        if hasattr(asset, 'holdings') and asset.holdings.filter_by(deleted_at=None).count() > 0:
            flash(f'❌ Cannot delete {asset.symbol}: Asset has active holdings', 'error')
            return redirect(request.referrer or url_for('admin.assets_list'))
        
        # Soft delete
        asset.deleted_at = db.func.now()
        asset.is_active = False
        db.session.commit()
        
        flash(f'✅ Asset {asset.symbol} deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting asset: {str(e)}")
        flash(f'❌ Error deleting asset: {str(e)}', 'error')
    
    return redirect(url_for('admin.assets_list'))


# ------ copytrade -------
# Add this to your existing admin routes.py
@admin_bp.route('/copy-transactions')
@login_required
@admin_required
def copy_transactions_admin():
    """Admin page to manage copy trading transactions"""
    
    # Get current counts
    stats = {
        'total_transactions': CopyTradeTransaction.query.count(),
        'completed_transactions': CopyTradeTransaction.query.filter_by(status='completed').count(),
        'pending_transactions': CopyTradeTransaction.query.filter_by(status='pending').count(),
        'users': User.query.count(),
        'traders': Trader.query.count(),
        'copy_trades': CopyTrade.query.count(),
        'assets': Asset.query.filter_by(is_active=True).count()
    }
    
    # Get data for dropdowns
    users = User.query.limit(20).all()  # Limit for performance
    traders = Trader.query.options(db.joinedload(Trader.user)).limit(20).all()
    copy_trades = CopyTrade.query.options(
        db.joinedload(CopyTrade.trader).joinedload(Trader.user),
        db.joinedload(CopyTrade.follower)
    ).limit(50).all()
    assets = Asset.query.filter_by(is_active=True).order_by(Asset.symbol).all()
    
    # Recent transactions
    recent_transactions = CopyTradeTransaction.query.options(
        db.joinedload(CopyTradeTransaction.copy_trade).joinedload(CopyTrade.trader).joinedload(Trader.user),
        db.joinedload(CopyTradeTransaction.follower),
        db.joinedload(CopyTradeTransaction.base_asset),
        db.joinedload(CopyTradeTransaction.quote_asset)
    ).order_by(CopyTradeTransaction.created_at.desc()).limit(10).all()
    
    return render_template('admin/copy_trading.html',
                         stats=stats,
                         users=users,
                         traders=traders,
                         copy_trades=copy_trades,
                         assets=assets,
                         recent_transactions=recent_transactions)

@admin_bp.route('/create-copy-transaction', methods=['POST'])
@login_required
@admin_required
def create_copy_transaction():
    """Create a single copy trading transaction"""
    try:
        # Get form data
        follower_id = request.form.get('follower_id', type=int)
        trader_id = request.form.get('trader_id', type=int)
        base_asset_id = request.form.get('base_asset_id', type=int)
        quote_asset_id = request.form.get('quote_asset_id', type=int)
        trade_type = request.form.get('trade_type')
        amount = request.form.get('amount', type=float)
        price = request.form.get('price', type=float)
        pnl = request.form.get('pnl', type=float) or 0
        status = request.form.get('status', 'completed')
        remark = request.form.get('remark', '').strip() or None
        
        # Validation
        if not all([follower_id, trader_id, base_asset_id, quote_asset_id, trade_type, amount, price]):
            flash('❌ All required fields must be filled', 'error')
            return redirect(url_for('admin.copy_transactions_admin'))
        
        # Get or create copy trade relationship
        copy_trade = CopyTrade.query.filter_by(
            follower_id=follower_id,
            trader_id=trader_id
        ).first()
        
        if not copy_trade:
            # Create copy trade relationship
            copy_trade = CopyTrade(
                follower_id=follower_id,
                trader_id=trader_id,
                allocation=Decimal('1000.00'),  # Default allocation
                is_active=True
            )
            db.session.add(copy_trade)
            db.session.flush()  # Get the ID
        
        # Calculate PnL percentage
        trade_value = amount * price
        pnl_percentage = (pnl / trade_value * 100) if trade_value > 0 else 0
        
        # Generate external transaction ID
        external_tx_id = f"CT{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
        
        # Create transaction
        transaction = CopyTradeTransaction(
            follower_id=follower_id,
            copy_trade_id=copy_trade.id,
            base_asset_id=base_asset_id,
            quote_asset_id=quote_asset_id,
            trade_type=trade_type,
            amount=Decimal(str(amount)),
            price=Decimal(str(price)),
            pnl=Decimal(str(pnl)),
            pnl_percentage=Decimal(str(round(pnl_percentage, 2))),
            status=status,
            remark=remark,
            external_tx_id=external_tx_id,
            transaction_timestamp=datetime.utcnow(),
            completed_at=datetime.utcnow() if status == 'completed' else None
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        flash('✅ Transaction created successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error creating transaction: {str(e)}', 'error')
        
    return redirect(url_for('admin.copy_transactions_admin'))

@admin_bp.route('/bulk-create-transactions', methods=['POST'])
@login_required
@admin_required
def bulk_create_transactions():
    """Create multiple sample transactions"""
    try:
        count = int(request.form.get('count', 20))
        count = min(count, 100)  # Max 100 at once
        
        # Get required data
        users = User.query.all()
        traders = Trader.query.all()
        btc = Asset.query.filter_by(symbol='btc').first()
        eth = Asset.query.filter_by(symbol='eth').first()
        usdt = Asset.query.filter_by(symbol='usdt').first()
        
        if not users or not traders or not all([btc, eth, usdt]):
            flash('❌ Required data missing. Need users, traders, and BTC/ETH/USDT assets', 'error')
            return redirect(url_for('admin.copy_transactions_admin'))
        
        trading_pairs = [(btc, usdt), (eth, usdt), (eth, btc)]
        created_count = 0
        
        for i in range(count):
            # Random selections
            follower = random.choice(users)
            trader = random.choice(traders)
            base_asset, quote_asset = random.choice(trading_pairs)
            
            # Skip if follower is the trader
            if follower.id == trader.user_id:
                continue
            
            # Get or create copy trade relationship
            copy_trade = CopyTrade.query.filter_by(
                follower_id=follower.id,
                trader_id=trader.id
            ).first()
            
            if not copy_trade:
                copy_trade = CopyTrade(
                    follower_id=follower.id,
                    trader_id=trader.id,
                    allocation=Decimal(str(round(random.uniform(500, 5000), 2))),
                    is_active=True
                )
                db.session.add(copy_trade)
                db.session.flush()
            
            # Generate trade data
            trade_type = random.choice(['buy', 'sell'])
            amount = round(random.uniform(0.001, 1.0), 6)
            
            # Realistic prices
            if base_asset.symbol == 'btc':
                price = round(random.uniform(40000, 70000), 2)
            elif base_asset.symbol == 'eth':
                price = round(random.uniform(2000, 4000), 2)
            else:
                price = round(random.uniform(0.5, 10), 4)
            
            # 70% profitable trades
            is_profitable = random.random() < 0.7
            trade_value = amount * price
            
            if is_profitable:
                pnl_percentage = random.uniform(0.5, 15)
                pnl = trade_value * (pnl_percentage / 100)
            else:
                pnl_percentage = random.uniform(-10, -0.5)
                pnl = trade_value * (pnl_percentage / 100)
            
            # Random timestamp within last 30 days
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            transaction_time = datetime.utcnow() - timedelta(days=days_ago, hours=hours_ago)
            
            external_tx_id = f"CT{transaction_time.strftime('%Y%m%d')}{random.randint(1000, 9999)}"
            
            transaction = CopyTradeTransaction(
                follower_id=follower.id,
                copy_trade_id=copy_trade.id,
                base_asset_id=base_asset.id,
                quote_asset_id=quote_asset.id,
                trade_type=trade_type,
                amount=Decimal(str(amount)),
                price=Decimal(str(price)),
                pnl=Decimal(str(round(pnl, 2))),
                pnl_percentage=Decimal(str(round(pnl_percentage, 2))),
                status='completed',
                external_tx_id=external_tx_id,
                transaction_timestamp=transaction_time,
                completed_at=transaction_time,
                remark=random.choice([None, 'Auto-copied', 'Stop loss', 'Take profit', 'Market order'])
            )
            
            db.session.add(transaction)
            created_count += 1
        
        db.session.commit()
        flash(f'✅ Created {created_count} sample transactions', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error creating transactions: {str(e)}', 'error')
    
    return redirect(url_for('admin.copy_transactions_admin'))

@admin_bp.route('/clear-transactions', methods=['POST'])
@login_required
@admin_required
def clear_transactions():
    """Clear all copy trading transactions"""
    try:
        CopyTradeTransaction.query.delete()
        db.session.commit()
        flash('✅ All copy trading transactions cleared', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error clearing transactions: {str(e)}', 'error')
    
    return redirect(url_for('admin.copy_transactions_admin'))
  