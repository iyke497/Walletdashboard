# app/staking/routes.py
from decimal import Decimal
from flask import render_template, request, url_for, jsonify, current_app, flash, redirect
from flask_login import login_required, current_user
from app.extensions import db
from app.staking import staking_bp
from app.staking.services import AssetService, StakingService, MiningService
from app.staking.forms import StakingForm, QuickStakeForm, UnstakeForm, MiningPoolSearchForm, MiningContractConfirmForm, MiningContractForm, MinerControlForm
from app.models import Asset, MiningAlgorithm,  MiningDifficulty, HashratePackage

# <-----------------------Staking------------------------->
@staking_bp.route('/')
@login_required # Good practice if viewing positions requires login
def staking_home():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int) # Default to 10 per page
    search = request.args.get('search', '', type=str).strip()

    # Get paginated assets for staking
    paginated_assets = AssetService.get_assets(
        page=page,
        per_page=per_page,
        search=search
    )

    serialized_assets = []
    for asset in paginated_assets.items:
        serialized_assets.append({
            'id': asset.id,
            'symbol': asset.symbol,
            'name': asset.name,
            'image': asset.images.get('small', asset.images.get('thumb', '')) if asset.images else None
        })

    # Forms for modals
    staking_form = StakingForm()
    # quick_stake_form = QuickStakeForm() # Keep if used by a modal on this page

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

    # --- Fetch Staking Positions Data ---
    user_staking_positions = []
    total_user_positions = 0
    active_user_positions = 0
    # Pass the UnstakeForm instance needed for the unstake modal in the positions tab
    unstake_form_for_positions_tab = UnstakeForm()

    if current_user.is_authenticated: # Ensure user is logged in
        try:
            positions_data = StakingService.get_user_staking_positions(current_user.id) #
            user_staking_positions = positions_data
            total_user_positions = len(positions_data) #
            active_user_positions = len([p for p in positions_data if p['status'] == 'active']) #
        except Exception as e:
            current_app.logger.error(f"Error fetching staking positions for user {current_user.id}: {e}")
            flash('Could not load your staking positions at this time.', 'warning')
    # --- End Staking Positions Data ---

    return render_template(
        'staking/staking_home.html',
        assets=serialized_assets,
        pagination=pagination_info,
        search_query=search,
        current_per_page=per_page,
        staking_form=staking_form, # For the "Stake Asset" modal
        # quick_stake_form=quick_stake_form,
        # --- Pass positions data to the template ---
        user_positions=user_staking_positions,
        total_positions=total_user_positions, # Renamed for clarity in template
        active_positions=active_user_positions, #
        unstake_form=unstake_form_for_positions_tab # Pass the specific unstake_form instance
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
                return redirect(url_for('staking.staking_home'))
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
    
    return redirect(url_for('staking.staking_home'))

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

# <-----------------------/Staking------------------------->

# <-----------------------Mining------------------------->
#@staking_bp.route('/mining')
@login_required
def mining_home_old():
    # Get pagination and search parameters from request
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '', type=str).strip()
    algorithm = request.args.get('algorithm', '', type=str)
    difficulty = request.args.get('difficulty', '', type=str)
    
    # Get filtered pools based on parameters
    paginated_pools = MiningService.get_available_pools(
        page=page,
        per_page=per_page,
        search=search,
        algorithm=algorithm,
        difficulty=difficulty
    )
    
    # Format assets for the template
    serialized_assets = []
    for pool in paginated_pools.items:
        serialized_assets.append({
            'id': pool.id,
            'name': pool.name,
            'algorithm': pool.algorithm,
            'pool_fee': pool.pool_fee,
            'difficulty': pool.difficulty,
            'apr': 4.5
        })
    
    # Set up pagination info
    pagination_info = {
        'page': paginated_pools.page,
        'pages': paginated_pools.pages,
        'per_page': paginated_pools.per_page,
        'total': paginated_pools.total,
        'has_prev': paginated_pools.has_prev,
        'prev_num': paginated_pools.prev_num,
        'has_next': paginated_pools.has_next,
        'next_num': paginated_pools.next_num,
        'iter_pages': list(paginated_pools.iter_pages(left_edge=1, right_edge=1, left_current=1, right_current=2))
    }
    
    # Forms for modals
    contract_form = MiningContractForm()
    confirm_form = MiningContractConfirmForm()
    
    return render_template(
        'staking/mining_home.html',
        assets=serialized_assets,
        pagination=pagination_info,
        search_query=search,
        current_per_page=per_page,
        contract_form=contract_form,
        confirm_form=confirm_form,
        algorithm_filter=algorithm,
        difficulty_filter=difficulty
    )

@staking_bp.route('/mining')
@login_required
def mining_home():
    # Get pagination and search parameters from request
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '', type=str).strip()
    algorithm = request.args.get('algorithm', '', type=str)
    difficulty = request.args.get('difficulty', '', type=str)
    
    # Get filtered pools based on parameters
    paginated_pools = MiningService.get_available_pools(
        page=page,
        per_page=per_page,
        search=search,
        algorithm=algorithm,
        difficulty=difficulty
    )
    
    # Get enum options for dropdown filters
    algorithms = MiningAlgorithm.__members__.values()
    difficulties = MiningDifficulty.__members__.values()
    

    
    # Forms for modals
    contract_form = MiningContractForm()
    confirm_form = MiningContractConfirmForm()
    
    # Get hashrate packages for active pools
    pool_ids = [pool.id for pool in paginated_pools.items]
    hashrate_packages = []
    if pool_ids:
        hashrate_packages = HashratePackage.query.filter(
            HashratePackage.pool_id.in_(pool_ids),
            HashratePackage.is_active == True
        ).order_by(HashratePackage.sort_order).all()
    
    # Set up pagination info
    pagination_info = {
        'page': paginated_pools.page,
        'pages': paginated_pools.pages,
        'per_page': paginated_pools.per_page,
        'total': paginated_pools.total,
        'has_prev': paginated_pools.has_prev,
        'prev_num': paginated_pools.prev_num,
        'has_next': paginated_pools.has_next,
        'next_num': paginated_pools.next_num,
        'iter_pages': list(paginated_pools.iter_pages(left_edge=1, right_edge=1, left_current=1, right_current=2))
    }
    
    return render_template(
        'staking/mining_home.html',
        pools=paginated_pools.items,  # Pass the entire pool objects instead of serialized data
        pagination=pagination_info,
        search_query=search,
        current_per_page=per_page,
        contract_form=contract_form,
        confirm_form=confirm_form,
        algorithm_filter=algorithm,
        difficulty_filter=difficulty,
        algorithms=algorithms,  # Pass enum values for dropdowns
        difficulties=difficulties,
        packages=hashrate_packages  # Pass packages for the modals
    )

@staking_bp.route('/start-contract', methods=['POST'])
@login_required
def start_mining_contract():
    form = MiningContractForm()
    
    if form.validate_on_submit():
        # Create confirmation form with validated data
        confirm_form = MiningContractConfirmForm()
        
        # Calculate costs server-side
        cost_data = MiningService.calculate_contract_cost(
            package_id=form.package_id.data,
            custom_hashrate=form.custom_hashrate.data,
            duration=int(form.duration.data)
        )
        
        # Pre-populate confirmation form
        confirm_form.pool_id.data = form.pool_id.data
        confirm_form.package_id.data = form.package_id.data
        confirm_form.total_cost.data = str(cost_data['total_cost'])
        # ... populate other fields
        
        # Return JSON for modal transition
        return jsonify({
            'success': True,
            'confirmation_data': {
                'pool_name': pool.name,
                'hashrate': cost_data['hashrate'],
                'total_cost': cost_data['total_cost'],
                'daily_earnings': cost_data['estimated_daily_earnings']
            }
        })
    
    # Return validation errors
    return jsonify({
        'success': False,
        'errors': form.errors
    })

@staking_bp.route('/confirm-contract', methods=['POST'])
@login_required
def confirm_mining_contract():
    form = MiningContractConfirmForm()
    
    if form.validate_on_submit():
        try:
            # Create the mining contract
            contract = MiningService.create_mining_contract(
                user_id=current_user.id,
                form_data=form.data
            )
            
            # Process payment
            MiningService.process_contract_payment(
                user_id=current_user.id,
                contract=contract
            )
            
            flash(f'Mining contract #{contract.id} started successfully!', 'success')
            return redirect(url_for('mining.mining_home') + '#my-miners-tab')
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to create mining contract. Please try again.', 'error')
    
    # Show validation errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{field}: {error}', 'error')
    
    return redirect(url_for('mining.mining_home'))

@staking_bp.route('/control-miner', methods=['POST'])
@login_required
def control_miner():
    form = MinerControlForm()
    
    if form.validate_on_submit():
        contract_id = form.contract_id.data
        action = form.action.data
        
        success = MiningService.control_mining_contract(
            user_id=current_user.id,
            contract_id=contract_id,
            action=action
        )
        
        if success:
            flash(f'Mining contract {action}d successfully!', 'success')
        else:
            flash(f'Failed to {action} mining contract.', 'error')
    
    return redirect(url_for('mining.mining_home') + '#my-miners-tab')