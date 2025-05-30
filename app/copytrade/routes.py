from flask import render_template, request, jsonify, flash, redirect, url_for
from app.copytrade import copytrade_bp
from app.copytrade.services import get_list_of_traders
from app.copytrade.forms import CopyTraderForm
#@copytrade_bp.route('/traders')
def trader_list_old():
    form = CopyTraderForm()
    traders = get_list_of_traders()
    return render_template('copytrade/copy-trading.html', traders=traders, form=form)


@copytrade_bp.route('/copy-trader/<int:trader_id>', methods=['POST'])
def copy_trader(trader_id):
    form = CopyTraderForm()
    if form.validate_on_submit():
        # Process the form data
        investment = form.investment_amount.data
        risk = form.risk_level.data
        leverage = form.leverage.data

        # Add your logic to copy the trader
        # ...

        flash('Successfully started copying this trader!', 'success')
        return redirect(url_for('copytrade.trader_list'))
    # If form doesn't validate, show errors
    flash('Please correct the errors in the form', 'danger')
    return redirect(url_for('copytrade.trader_list'))


# routes.py - Updated trader_list route
@copytrade_bp.route('/traders')
def trader_list():
    form = CopyTraderForm()
    
    # Get request parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', None)
    sort_by = request.args.get('sort_by', 'win_rate')
    sort_order = request.args.get('sort_order', 'desc')
    market = request.args.get('market', 'all')
    time_period = request.args.get('time_period', 'all')

    # Get paginated traders
    pagination = get_list_of_traders(
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page,
        market=market,
        time_period=time_period
    )
    
    return render_template('copytrade/copy-trading.html',
                         traders=pagination.items,
                         pagination=pagination,
                         form=form,
                         current_params=request.args)


@copytrade_bp.route('/trader-profile')
def trader_profile():
    return render_template('copytrade/trader_profile.html')