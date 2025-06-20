# app/admin/routes.py
from flask import render_template, flash, redirect, url_for, request
from flask_login import login_required
from . import admin_bp
from app.decorators import admin_required
from app.models import Transaction, TransactionType, TransactionStatus, User, Asset
from app.wallet.services import WalletService
from app.extensions import db

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