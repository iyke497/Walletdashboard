from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import current_user, login_required
from app.models import CopyTrade
from app.extensions import db
from app.copytrade import copytrade_bp
from app.copytrade.services import get_list_of_traders, get_trader_by_id
from app.copytrade.forms import CopyTraderForm
from app.dashboard.services import PortfolioService


@copytrade_bp.route('/copy-trader/<int:trader_id>', methods=['POST'])
@login_required
def copy_trader(trader_id):
    form = CopyTraderForm()
    if form.validate_on_submit():

        # Get the trader to ensure they exist
        trader = get_trader_by_id(trader_id)
        if not trader:
            flash('Trader not found', 'danger')
            return redirect(url_for('copytrade.trader_list'))
        
        # Check if user already follows this trader
        existing_copy = CopyTrade.query.filter_by(
            follower_id=current_user.id,
            trader_id=trader_id,
            is_active=True
        ).first()

        if existing_copy:
            # Update existing copy settings
            existing_copy.allocation = form.investment_amount.data
            db.session.commit()
            flash('Copy settings updated successfully!', 'success')
        else:
            # Create new copy trade record
            new_copy = CopyTrade(
                follower_id=current_user.id,
                trader_id=trader_id,
                allocation=form.investment_amount.data,
                is_active=True
            )

            # Add and commit the new record
            db.session.add(new_copy)
            db.session.commit()
            
            flash('Successfully started copying this trader!', 'success')
        
        # Return to the trader list page
        return redirect(url_for('copytrade.trader_list'))
    
    # If form validation fails, show errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{getattr(form, field).label.text}: {error}", 'danger')

    return redirect(url_for('copytrade.trader_list'))


@copytrade_bp.route('/stop-copy-trader/<int:trader_id>', methods=['POST'])
@login_required
def stop_copy_trader(trader_id):
    """Stop copying a trader"""
    # Find the copy trade relationship
    copy_trade = CopyTrade.query.filter_by(
        follower_id=current_user.id,
        trader_id=trader_id,
        is_active=True
    ).first()
    
    if copy_trade:
        # Deactivate rather than delete
        copy_trade.is_active = False
        db.session.commit()
        flash('Successfully stopped copying this trader', 'success')
    else:
        flash('You are not currently copying this trader', 'warning')
    
    return redirect(url_for('copytrade.trader_list'))

# routes.py - Updated trader_list route
@copytrade_bp.route('/traders')
@login_required
def trader_list():
    form = CopyTraderForm()

    portfolio_value = PortfolioService.get_portfolio_value(current_user.id, current_user.display_currency_id)

    # Get copy trading statistics
    active_traders_count = CopyTrade.query.filter_by(
        follower_id=current_user.id, 
        is_active=True
    ).count()
    
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
                         current_params=request.args,
                         portfolio_value=portfolio_value,
                         active_traders_count=active_traders_count)


@copytrade_bp.route('/trader-profile/<int:trader_id>')
@login_required
def trader_profile(trader_id):
    # Get the specific trader by ID
    trader = get_trader_by_id(trader_id)

    # Handle case where trader doesn't exist
    if not trader:
        flash('Trader not found', 'error')
        return redirect(url_for('copytrade.trader_list'))

    # You can add additional data processing here
    # For example, get trader's recent trades, performance history, etc.
    # recent_trades = get_trader_recent_trades(trader_id)
    # performance_data = get_trader_performance_data(trader_id)
    # portfolio_data = get_trader_portfolio(trader_id)
    
    return render_template('copytrade/trader_profile.html', 
                        trader=trader)
                        # recent_trades=recent_trades,
                        # performance_data=performance_data,
                        # portfolio_data=portfolio_data)

    return render_template('copytrade/trader_profile.html')