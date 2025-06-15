# app/staking/routes.py
from decimal import Decimal
from flask import render_template, request, url_for, jsonify, current_app, flash, redirect
from flask_login import login_required, current_user
from app.extensions import db
from app.staking import staking_bp
from app.staking.services import AssetService, StakingService, MiningService
from app.staking.forms import StakingForm, QuickStakeForm, UnstakeForm, MiningPoolSearchForm, MiningContractConfirmForm, MiningContractForm, MinerControlForm
from app.models import Asset, MiningAlgorithm,  MiningDifficulty, HashratePackage, MiningPool, MiningContract

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
    
    # For debugging, we'll log the available pools
    current_app.logger.info(f"Loaded {len(paginated_pools.items)} mining pools")
    for pool in paginated_pools.items:
        current_app.logger.info(f"Pool: {pool.id} - {pool.asset.symbol} - {pool.algorithm.name}")
    
    return render_template(
        'staking/mining_home.html',
        pools=paginated_pools.items,
        pagination=pagination_info,
        search_query=search,
        current_per_page=per_page,
        contract_form=contract_form,
        algorithm_filter=algorithm,
        difficulty_filter=difficulty,
        algorithms=algorithms,
        difficulties=difficulties
    )

@staking_bp.route('/api/mining/packages/<int:pool_id>')
@login_required
def get_mining_packages(pool_id):
    """API endpoint to get hashrate packages for a specific mining pool"""
    current_app.logger.info(f"API request for packages for pool ID: {pool_id}")
    
    # Validate pool_id
    if not pool_id or pool_id <= 0:
        current_app.logger.warning(f"Invalid pool ID requested: {pool_id}")
        return jsonify({
            'success': False,
            'message': 'Invalid pool ID',
            'packages': []
        }), 400
    
    try:
        # Get the pool to validate it exists
        pool = MiningPool.query.get(pool_id)
        if not pool:
            current_app.logger.warning(f"Pool ID {pool_id} not found in database")
            return jsonify({
                'success': False,
                'message': 'Mining pool not found',
                'packages': []
            }), 404
        
        # Get packages for this pool
        packages = HashratePackage.query.filter_by(pool_id=pool_id, is_active=True).order_by(HashratePackage.sort_order).all()
        
        # If no packages specific to this pool, get default packages
        if not packages:
            current_app.logger.info(f"No specific packages for pool {pool_id}, getting defaults")
            # Use sample from each difficulty level
            packages = HashratePackage.query.filter_by(is_active=True).order_by(HashratePackage.hashrate).limit(3).all()
        
        current_app.logger.info(f"Found {len(packages)} packages for pool {pool_id}")
        
        # Serialize the packages for JSON response
        serialized_packages = []
        for package in packages:
            serialized_packages.append({
                'id': package.id,
                'name': package.name,
                'hashrate': float(package.hashrate),
                'hashrateUnit': package.hashrate_unit.value,
                'monthlyCost': float(package.monthly_cost_usd),
                'powerConsumption': package.power_consumption_watts
            })
            current_app.logger.info(f"Package: {package.id} - {package.name} - {package.hashrate} {package.hashrate_unit.value}")
        
        return jsonify({
            'success': True,
            'packages': serialized_packages
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching mining packages: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error fetching packages: {str(e)}',
            'packages': []
        }), 500

@staking_bp.route('/mining/create-contract', methods=['POST'])
@login_required
def create_mining_contract():
    """Create a new mining contract after confirmation"""
    form = MiningContractForm()
    
    current_app.logger.info(f"Contract form submitted with data: pool_id={form.pool_id.data}, package_selection={form.package_selection.data}")
    
    if form.validate_on_submit():
        try:
            # Get form data
            pool_id = form.pool_id.data
            
            # Validate pool ID
            if not pool_id or not isinstance(pool_id, int):
                try:
                    pool_id = int(pool_id) if pool_id and str(pool_id).isdigit() else None
                except (ValueError, TypeError):
                    pool_id = None
            
            if not pool_id:
                flash('Pool ID is required', 'danger')
                return redirect(url_for('staking.mining_home'))
            
            # Get the pool to validate it exists
            pool = MiningPool.query.get(pool_id)
            if not pool:
                flash('Mining pool not found', 'danger')
                return redirect(url_for('staking.mining_home'))
            
            current_app.logger.info(f"Valid pool found: {pool.id} - {pool.asset.symbol}")
            
            package_id = None
            if form.package_selection.data != 'custom' and form.package_id.data:
                try:
                    package_id = int(form.package_id.data) if form.package_id.data and str(form.package_id.data).isdigit() else None
                except (ValueError, TypeError):
                    package_id = None
                
                # Validate package if provided
                if package_id:
                    package = HashratePackage.query.get(package_id)
                    if not package or not package.is_active:
                        current_app.logger.warning(f"Invalid package ID: {package_id}")
                        package_id = None
            
            # Determine hashrate and unit
            hashrate = None
            hashrate_unit = None
            
            if form.package_selection.data == 'custom':
                # For custom selection, both hashrate and unit are required
                try:
                    hashrate = float(form.custom_hashrate.data) if form.custom_hashrate.data else None
                except (ValueError, TypeError):
                    hashrate = None
                
                hashrate_unit = form.custom_hashrate_unit.data
                
                if not hashrate:
                    flash('Custom hashrate is required', 'danger')
                    return redirect(url_for('staking.mining_home'))
                
                if not hashrate_unit:
                    flash('Hashrate unit is required', 'danger')
                    return redirect(url_for('staking.mining_home'))
                
                current_app.logger.info(f"Custom hashrate: {hashrate} {hashrate_unit}")
            else:
                # Get hashrate from package
                if package_id:
                    package = HashratePackage.query.get(package_id)
                    if package:
                        hashrate = float(package.hashrate)
                        hashrate_unit = package.hashrate_unit.value
                        current_app.logger.info(f"Using package: {package.id} - {package.name}")
                else:
                    # Use default package values based on selection
                    if form.package_selection.data == 'basic':
                        hashrate = float(pool.min_hashrate)
                        hashrate_unit = pool.min_hashrate_unit.value
                        current_app.logger.info(f"Using basic package with hashrate: {hashrate} {hashrate_unit}")
                    elif form.package_selection.data == 'pro':
                        hashrate = float(pool.min_hashrate) * 5
                        hashrate_unit = pool.min_hashrate_unit.value
                        current_app.logger.info(f"Using pro package with hashrate: {hashrate} {hashrate_unit}")
                    elif form.package_selection.data == 'enterprise':
                        hashrate = float(pool.min_hashrate) * 20
                        hashrate_unit = pool.min_hashrate_unit.value
                        current_app.logger.info(f"Using enterprise package with hashrate: {hashrate} {hashrate_unit}")
            
            if not hashrate:
                flash('Invalid hashrate specified', 'danger')
                return redirect(url_for('staking.mining_home'))
            
            # Get duration in months
            try:
                duration_months = int(form.duration.data) if form.duration.data else 1
            except (ValueError, TypeError):
                duration_months = 1
            
            current_app.logger.info(f"Duration: {duration_months} months")
            
            # Get contract name
            contract_name = form.contract_name.data or f"{pool.asset.symbol} Miner #{hashrate} {hashrate_unit}"
            
            # Create the contract
            contract = MiningService.create_mining_contract(
                user_id=current_user.id,
                pool_id=pool_id,
                package_id=package_id,
                hashrate=hashrate,
                hashrate_unit=hashrate_unit,
                duration_months=duration_months,
                name=contract_name
            )
            
            flash(f'Mining contract created successfully! Your {contract.hashrate} {contract.hashrate_unit.value} miner will start working soon.', 'success')
            return redirect(url_for('staking.mining_contracts'))
            
        except Exception as e:
            current_app.logger.error(f"Error creating mining contract: {str(e)}")
            flash(f'Error creating mining contract: {str(e)}', 'danger')
            return redirect(url_for('staking.mining_home'))
    else:
        # If form validation failed
        current_app.logger.warning(f"Form validation failed: {form.errors}")
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", 'danger')
    
    return redirect(url_for('staking.mining_home'))

@staking_bp.route('/mining/contracts')
@login_required
def mining_contracts():
    """View user's mining contracts"""
    contracts = MiningContract.query.filter_by(
        user_id=current_user.id
    ).order_by(MiningContract.created_at.desc()).all()
    
    current_app.logger.info(f"Loaded {len(contracts)} mining contracts for user {current_user.id}")
    
    return render_template(
        'staking/mining_contracts.html',
        contracts=contracts
    )