from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from .forms import DepositForm, WithdrawForm, TradeForm, StakeForm
from .services import (
    record_deposit, record_withdraw, execute_trade, record_stake
)

bp = Blueprint('wallet', __name__, url_prefix='/wallet')

@bp.route('/deposit', methods=['GET','POST'])
@login_required
def deposit():
    form = DepositForm()
    if form.validate_on_submit():
        record_deposit(current_user.id, form.asset.data, form.amount.data)
        flash('Deposit successful', 'success')
        return redirect(url_for('dashboard.index'))
    return render_template('wallet/deposit.html', form=form)
# ... similarly for /withdraw, /trade, /stake