# app/staking/routes.py
from decimal import Decimal
from flask import render_template, request, url_for, jsonify, current_app, flash, redirect
from flask_login import login_required, current_user
from app.staking import staking_bp
from app.staking.services import AssetService, StakingService
from app.staking.forms import StakingForm, QuickStakeForm, UnstakeForm
from app.models import Asset

@staking_bp.route('/')
def staking_home():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '', type=str).strip()

    # Get paginated assets with search
    paginated_assets = AssetService.get_assets(
        page=page, 
        per_page=per_page, 
        search=search
    )

    # Serialize assets for template
    serialized_assets = []
    for asset in paginated_assets.items:
        serialized_assets.append({
            'id': asset.id,
            'symbol': asset.symbol,
            'name': asset.name,
            'image': asset.images.get('small', asset.images.get('thumb', '')) if asset.images else None
        })

    # Create form instances for modal
    staking_form = StakingForm()
    quick_stake_form = QuickStakeForm()

    # Pagination info for template
    pagination_info = {
        'page': paginated_assets.page,
        'pages': paginated_assets.pages,
        'per_page': paginated_assets.per_page,
        'total': paginated_assets.total,
        'has_prev': paginated_assets.has_prev,
        'prev_num': paginated_assets.prev_num,
        'has_next': paginated_assets.has_next,
        'next_num': paginated_assets.next_num,
        'iter_pages': list(paginated_assets.iter_pages(left_edge=1, right_edge=1, left_current=1, right_current=2))
    }

    return render_template(
        'staking/staking_home.html', 
        assets=serialized_assets,
        pagination=pagination_info,
        search_query=search,
        current_per_page=per_page,
        staking_form=staking_form,
        quick_stake_form=quick_stake_form
    )

@staking_bp.route('/stake', methods=['POST'])
@login_required
def stake_asset():
    """Handle staking form submission with proper validation"""
    form = StakingForm()
    
    if form.validate_on_submit():
        try:
            # Convert period to days
            period_days = None
            if form.period.data != 'flexible':
                period_days = int(form.period.data)
            
            # Create staking position
            result = StakingService.create_staking_position(
                user_id=current_user.id,
                asset_id=int(form.asset_id.data),
                amount=form.amount.data,
                period_days=period_days
            )
            
            if result['success']:
                asset = Asset.query.get(form.asset_id.data)
                flash(
                    f'Successfully staked {form.amount.data:.8f} {asset.symbol}!',
                    'success'
                )
                return redirect(url_for('staking.staking_positions'))
            else:
                flash(result.get('error', 'Failed to create staking position'), 'error')
                
        except Exception as e:
            flash(f'Error processing staking request: {str(e)}', 'error')
    
    # If form validation failed, redirect back with errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{field.title()}: {error}', 'error')
    
    return redirect(url_for('staking.staking_home'))

@staking_bp.route('/quick-stake', methods=['POST'])
@login_required
def quick_stake():
    """Handle quick staking with percentage-based amounts"""
    form = QuickStakeForm()
    
    if form.validate_on_submit():
        try:
            # Get user balance
            balance = AssetService.get_user_balance(
                current_user.id, 
                int(form.asset_id.data)
            )
            
            # Calculate amount based on percentage
            percentage = int(form.percentage.data)
            amount = (balance * percentage) / 100
            
            if amount <= 0:
                flash('Insufficient balance for quick stake', 'error')
                return redirect(url_for('staking.staking_home'))
            
            # Convert period to days
            period_days = None
            if form.period.data != 'flexible':
                period_days = int(form.period.data)
            
            # Create staking position
            result = StakingService.create_staking_position(
                user_id=current_user.id,
                asset_id=int(form.asset_id.data),
                amount=amount,
                period_days=period_days
            )
            
            if result['success']:
                asset = Asset.query.get(form.asset_id.data)
                flash(
                    f'Successfully quick-staked {amount:.8f} {asset.symbol} ({percentage}% of balance)!',
                    'success'
                )
                return redirect(url_for('staking.staking_positions'))
            else:
                flash(result.get('error', 'Failed to create staking position'), 'error')
                
        except Exception as e:
            flash(f'Error processing quick stake: {str(e)}', 'error')
    
    # Handle form errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{error}', 'error')
    
    return redirect(url_for('staking.staking_home'))

@staking_bp.route('/api/balance/<int:asset_id>')
@login_required
def get_asset_balance(asset_id):
    """API endpoint to get user's balance for a specific asset"""
    try:
        balance = AssetService.get_user_balance(current_user.id, asset_id)
        asset = Asset.query.get(asset_id)
        
        if not asset:
            return jsonify({
                'success': False,
                'error': 'Asset not found'
            }), 404
        
        return jsonify({
            'success': True,
            'balance': str(balance),
            'asset_id': asset_id,
            'asset_symbol': asset.symbol,
            'can_stake': balance > 0
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to fetch balance'
        }), 500

@staking_bp.route('/api/validate-stake', methods=['POST'])
@login_required
def validate_stake_ajax():
    """AJAX endpoint for real-time form validation"""
    form = StakingForm()
    
    if form.validate():
        return jsonify({
            'success': True,
            'valid': True
        })
    else:
        return jsonify({
            'success': True,
            'valid': False,
            'errors': form.errors
        })

@staking_bp.route('/positions')
@login_required
def staking_positions():
    """Page to view user's staking positions"""
    try:
        positions = StakingService.get_user_staking_positions(current_user.id)
        unstake_form = UnstakeForm()
        
        # Calculate total staked value
        total_positions = len(positions)
        active_positions = len([p for p in positions if p['status'] == 'active'])
        
        return render_template(
            'staking/staking_positions.html',
            positions=positions,
            total_positions=total_positions,
            active_positions=active_positions,
            unstake_form=unstake_form
        )
    
    except Exception as e:
        flash('Error loading staking positions', 'error')
        return redirect(url_for('staking.staking_home'))

@staking_bp.route('/unstake', methods=['POST'])
@login_required
def unstake_position():
    """Handle unstaking with form validation"""
    form = UnstakeForm()
    
    if form.validate_on_submit():
        try:
            result = StakingService.unstake_position(
                current_user.id, 
                int(form.position_id.data)
            )
            
            if result['success']:
                flash('Position unstaked successfully!', 'success')
            else:
                flash(result.get('error', 'Failed to unstake position'), 'error')
                
        except Exception as e:
            flash(f'Error processing unstake request: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{error}', 'error')
    
    return redirect(url_for('staking.staking_positions'))

# Keep the API endpoints for backwards compatibility or AJAX functionality
@staking_bp.route('/api/stake', methods=['POST'])
@login_required
def create_stake_api():
    """API endpoint - now validates using Flask-WTF behind the scenes"""
    try:
        data = request.get_json()
        
        # Create form instance with JSON data
        form = StakingForm(data=data)
        
        if form.validate():
            period_days = None
            if form.period.data != 'flexible':
                period_days = int(form.period.data)
            
            result = StakingService.create_staking_position(
                user_id=current_user.id,
                asset_id=int(form.asset_id.data),
                amount=form.amount.data,
                period_days=period_days
            )
            
            return jsonify(result), 201 if result['success'] else 400
        else:
            return jsonify({
                'success': False,
                'error': 'Validation failed',
                'errors': form.errors
            }), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@staking_bp.route('/api/unstake/<int:position_id>', methods=['POST'])
@login_required
def unstake_position_api(position_id):
    """API endpoint for unstaking"""
    try:
        # Create form with position_id
        form = UnstakeForm(data={'position_id': position_id, 'confirm_unstake': True})
        
        if form.validate():
            result = StakingService.unstake_position(current_user.id, position_id)
            return jsonify(result), 200 if result['success'] else 400
        else:
            return jsonify({
                'success': False,
                'error': 'Validation failed',
                'errors': form.errors
            }), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to unstake position'
        }), 500
