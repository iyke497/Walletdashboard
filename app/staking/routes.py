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
# Update your mining_home route in routes.py to include mining contracts data

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
    
    # --- Fetch Mining Contracts Data ---
    user_mining_positions = []
    total_mining_positions = 0
    active_mining_positions = 0
    
    if current_user.is_authenticated:
        try:
            # Get user's mining contracts
            contracts = MiningContract.query.filter_by(
                user_id=current_user.id
            ).join(MiningPool).join(Asset).order_by(
                MiningContract.created_at.desc()
            ).all()
            
            total_mining_positions = len(contracts)
            active_mining_positions = len([c for c in contracts if c.status.value in ['pending', 'active']])
            
            # Format contracts for template
            for contract in contracts:
                user_mining_positions.append({
                    'id': contract.id,
                    'name': contract.name or f"{contract.pool.asset.symbol} Miner #{contract.id}",
                    'asset_symbol': contract.pool.asset.symbol,
                    'asset_name': contract.pool.asset.name,
                    'asset_image': contract.pool.asset.images.get('small', '') if contract.pool.asset.images else None,
                    'hashrate': f"{contract.hashrate}",
                    'hashrate_unit': contract.hashrate_unit.value,
                    'duration_months': contract.duration_months,
                    'monthly_cost': float(contract.monthly_cost_usd),
                    'total_cost': float(contract.total_cost_usd),
                    'power_consumption': contract.power_consumption_watts,
                    'hardware_type': contract.hardware_type,
                    'status': contract.status.value,
                    'created_at': contract.created_at,
                    'start_date': contract.start_date,
                    'end_date': contract.end_date,
                    'can_pause': contract.status.value == 'active',
                    'can_resume': contract.status.value == 'paused',
                    'can_cancel': contract.status.value in ['pending', 'active', 'paused']
                })
                
        except Exception as e:
            current_app.logger.error(f"Error fetching mining contracts for user {current_user.id}: {e}")
            flash('Could not load your mining contracts at this time.', 'warning')
    
    # For debugging, we'll log the available pools
    current_app.logger.info(f"Loaded {len(paginated_pools.items)} mining pools")
    current_app.logger.info(f"User has {total_mining_positions} mining contracts ({active_mining_positions} active)")
    
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
        difficulties=difficulties,
        # Mining contracts data
        user_mining_positions=user_mining_positions,
        total_mining_positions=total_mining_positions,
        active_mining_positions=active_mining_positions
    )



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

@login_required
def create_mining_contract_old():
    """Create a new mining contract after confirmation"""
    form = MiningContractForm()
    
    current_app.logger.info(f"Contract form submitted with data: pool_id={form.pool_id.data}, package_selection={form.package_selection.data}")
    
    if form.validate_on_submit():
        try:
            # Get form data
            pool_id = form.pool_id.data
            
            # Validate and convert pool ID
            try:
                pool_id = int(pool_id)
            except (ValueError, TypeError):
                flash('Invalid pool ID', 'danger')
                return redirect(url_for('staking.mining_home'))
            
            # Get the pool to validate it exists
            pool = MiningPool.query.get(pool_id)
            if not pool:
                flash('Mining pool not found', 'danger')
                return redirect(url_for('staking.mining_home'))
            
            current_app.logger.info(f"Valid pool found: {pool.id} - {pool.asset.symbol}")
            
            # Handle package selection
            package_id = None
            hashrate = None
            hashrate_unit = None
            
            if form.package_selection.data == 'custom':
                # Custom hashrate selection
                try:
                    hashrate = float(form.custom_hashrate.data)
                    hashrate_unit = form.custom_hashrate_unit.data
                    
                    if hashrate <= 0:
                        flash('Invalid custom hashrate', 'danger')
                        return redirect(url_for('staking.mining_home'))
                        
                    current_app.logger.info(f"Custom hashrate: {hashrate} {hashrate_unit}")
                    
                except (ValueError, TypeError):
                    flash('Invalid custom hashrate value', 'danger')
                    return redirect(url_for('staking.mining_home'))
            else:
                # Predefined package selection
                if form.package_id.data:
                    try:
                        package_id = int(form.package_id.data)
                        package = HashratePackage.query.get(package_id)
                        if package and package.is_active:
                            hashrate = float(package.hashrate)
                            hashrate_unit = package.hashrate_unit.value
                            current_app.logger.info(f"Using package: {package.id} - {package.name}")
                        else:
                            package_id = None
                    except (ValueError, TypeError):
                        package_id = None
                
                # If no valid package ID, create default based on selection
                if not package_id:
                    current_app.logger.info(f"No package ID, using default for {form.package_selection.data}")
                    base_hashrate = float(pool.min_hashrate)
                    hashrate_unit = pool.min_hashrate_unit.value
                    
                    if form.package_selection.data == 'basic':
                        hashrate = base_hashrate
                    elif form.package_selection.data == 'pro':
                        hashrate = base_hashrate * 5
                    elif form.package_selection.data == 'enterprise':
                        hashrate = base_hashrate * 20
                    else:
                        hashrate = base_hashrate
                    
                    current_app.logger.info(f"Using default {form.package_selection.data} package: {hashrate} {hashrate_unit}")
            
            # Validate final hashrate
            if not hashrate or hashrate <= 0:
                flash('Invalid hashrate configuration', 'danger')
                return redirect(url_for('staking.mining_home'))
            
            # Get duration
            try:
                duration_months = int(form.duration.data)
            except (ValueError, TypeError):
                duration_months = 1
            
            # Get contract name
            contract_name = form.contract_name.data or f"{pool.asset.symbol} Miner #{hashrate} {hashrate_unit}"
            
            current_app.logger.info(f"Creating contract: user={current_user.id}, pool={pool_id}, hashrate={hashrate}, duration={duration_months}")
            
            # Create the contract using the service
            contract = MiningService.create_mining_contract(
                user_id=current_user.id,
                pool_id=pool_id,
                hashrate=hashrate,
                duration=duration_months,  # This should match the 'duration' parameter
                package_id=package_id
            )
            
            if contract:
                current_app.logger.info(f"Mining contract created successfully: {contract.id}")
                flash(f'Mining contract created successfully! Your {contract.hashrate} {contract.hashrate_unit.value} miner will start working soon.', 'success')
                return redirect(url_for('staking.mining_contracts'))
            else:
                flash('Failed to create mining contract', 'danger')
                return redirect(url_for('staking.mining_home'))
            
        except Exception as e:
            current_app.logger.error(f"Error creating mining contract: {str(e)}")
            flash(f'Error creating mining contract: {str(e)}', 'danger')
            return redirect(url_for('staking.mining_home'))
    else:
        # Form validation failed
        current_app.logger.warning(f"Form validation failed: {form.errors}")
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", 'danger')
    
    return redirect(url_for('staking.mining_home'))
@staking_bp.route('/mining/create-contract', methods=['POST'])
@login_required
def create_mining_contract():
    """Create a new mining contract after confirmation"""
    form = MiningContractForm()
    
    # Enhanced logging to see what we receive
    current_app.logger.info("=== MINING CONTRACT SUBMISSION DEBUG ===")
    current_app.logger.info(f"Form data received:")
    current_app.logger.info(f"  pool_id: {form.pool_id.data} (type: {type(form.pool_id.data)})")
    current_app.logger.info(f"  package_selection: {form.package_selection.data}")
    current_app.logger.info(f"  package_id: {form.package_id.data} (type: {type(form.package_id.data)})")
    current_app.logger.info(f"  custom_hashrate: {form.custom_hashrate.data}")
    current_app.logger.info(f"  duration: {form.duration.data}")
    
    if form.validate_on_submit():
        try:
            # Get form data and convert pool ID
            try:
                pool_id = int(form.pool_id.data)
            except (ValueError, TypeError):
                current_app.logger.error(f"Invalid pool_id: {form.pool_id.data}")
                flash('Invalid pool ID', 'danger')
                return redirect(url_for('staking.mining_home'))
            
            # Get the pool to validate it exists
            pool = MiningPool.query.get(pool_id)
            if not pool:
                flash('Mining pool not found', 'danger')
                return redirect(url_for('staking.mining_home'))
            
            current_app.logger.info(f"Valid pool found: {pool.id} - {pool.asset.symbol}")
            
            # Handle package selection and hashrate determination
            package_id = None
            hashrate = None
            hashrate_unit = None
            
            if form.package_selection.data == 'custom':
                # Custom hashrate selection
                try:
                    hashrate = float(form.custom_hashrate.data)
                    hashrate_unit = form.custom_hashrate_unit.data
                    
                    if hashrate <= 0:
                        flash('Invalid custom hashrate', 'danger')
                        return redirect(url_for('staking.mining_home'))
                        
                    current_app.logger.info(f"Using custom hashrate: {hashrate} {hashrate_unit}")
                    
                except (ValueError, TypeError):
                    flash('Invalid custom hashrate value', 'danger')
                    return redirect(url_for('staking.mining_home'))
            else:
                # Predefined package selection - FIXED LOGIC
                current_app.logger.info(f"Processing predefined package: {form.package_selection.data}")
                
                # Try to get package from package_id first (from API)
                if form.package_id.data and str(form.package_id.data).strip():
                    try:
                        package_id = int(form.package_id.data)
                        current_app.logger.info(f"Attempting to use package_id: {package_id}")
                        
                        package = HashratePackage.query.get(package_id)
                        if package and package.is_active:
                            hashrate = float(package.hashrate)
                            hashrate_unit = package.hashrate_unit.value
                            current_app.logger.info(f"Found package in DB: {package.id} - {package.name} - {hashrate} {hashrate_unit}")
                        else:
                            current_app.logger.warning(f"Package {package_id} not found or inactive")
                            package_id = None
                    except (ValueError, TypeError) as e:
                        current_app.logger.warning(f"Invalid package_id conversion: {form.package_id.data} - {e}")
                        package_id = None
                
                # If no valid package found, use fallback calculations
                if not package_id:
                    current_app.logger.info(f"No valid package ID, using fallback for {form.package_selection.data}")
                    base_hashrate = float(pool.min_hashrate)
                    hashrate_unit = pool.min_hashrate_unit.value
                    
                    if form.package_selection.data == 'basic':
                        hashrate = base_hashrate
                    elif form.package_selection.data == 'pro':
                        hashrate = base_hashrate * 5
                    elif form.package_selection.data == 'enterprise':
                        hashrate = base_hashrate * 20
                    else:
                        hashrate = base_hashrate
                    
                    current_app.logger.info(f"Using fallback {form.package_selection.data} package: {hashrate} {hashrate_unit}")
            
            # Final validation
            if not hashrate or hashrate <= 0:
                current_app.logger.error(f"Final hashrate validation failed: {hashrate}")
                flash('Invalid hashrate configuration', 'danger')
                return redirect(url_for('staking.mining_home'))
            
            # Get duration and contract name
            try:
                duration_months = int(form.duration.data)
            except (ValueError, TypeError):
                duration_months = 1
            
            contract_name = form.contract_name.data or f"{pool.asset.symbol} Miner #{hashrate} {hashrate_unit}"
            
            # Log final parameters before service call
            current_app.logger.info("=== FINAL CONTRACT PARAMETERS ===")
            current_app.logger.info(f"user_id: {current_user.id}")
            current_app.logger.info(f"pool_id: {pool_id}")
            current_app.logger.info(f"hashrate: {hashrate}")
            current_app.logger.info(f"duration_months: {duration_months}")
            current_app.logger.info(f"package_id: {package_id}")
            current_app.logger.info(f"contract_name: {contract_name}")
            
            # Create the contract using the service
            contract = MiningService.create_mining_contract(
                user_id=current_user.id,
                pool_id=pool_id,
                hashrate=hashrate,
                duration=duration_months,
                package_id=package_id
            )
            
            if contract:
                current_app.logger.info(f"SUCCESS: Mining contract created: {contract.id}")
                flash(f'Mining contract created successfully! Your {contract.hashrate} {contract.hashrate_unit.value} miner will start working soon.', 'success')
                return redirect(url_for('staking.mining_home'))
            else:
                current_app.logger.error("Service returned None - no contract created")
                flash('Failed to create mining contract', 'danger')
                return redirect(url_for('staking.mining_home'))
            
        except Exception as e:
            current_app.logger.error(f"Exception in route: {str(e)}")
            current_app.logger.exception("Full traceback:")
            flash(f'Error creating mining contract: {str(e)}', 'danger')
            return redirect(url_for('staking.mining_home'))
    else:
        # Form validation failed
        current_app.logger.error("=== FORM VALIDATION FAILED ===")
        current_app.logger.error(f"Form errors: {form.errors}")
        for field, errors in form.errors.items():
            for error in errors:
                current_app.logger.error(f"Field '{field}': {error}")
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
    
    # return render_template(
    #     'staking/mining_contracts.html',
    #     contracts=contracts
    # )
    return "Success"


# - -------------------- Contract Actions ------------------------------ -#
# Add these routes to handle mining contract actions

@staking_bp.route('/mining/contract/pause/<int:contract_id>', methods=['POST'])
@login_required
def pause_mining_contract(contract_id):
    """Pause a mining contract"""
    try:
        contract = MiningContract.query.filter_by(
            id=contract_id,
            user_id=current_user.id
        ).first()
        
        if not contract:
            flash('Mining contract not found.', 'danger')
            return redirect(url_for('staking.mining_home'))
        
        if contract.status != MiningContractStatus.ACTIVE:
            flash('Only active contracts can be paused.', 'warning')
            return redirect(url_for('staking.mining_home'))
        
        # Update contract status
        contract.status = MiningContractStatus.PAUSED
        contract.last_active_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'Mining contract "{contract.name}" has been paused.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error pausing mining contract {contract_id}: {str(e)}")
        flash('Error pausing mining contract. Please try again.', 'danger')
    
    return redirect(url_for('staking.mining_home'))

@staking_bp.route('/mining/contract/resume/<int:contract_id>', methods=['POST'])
@login_required
def resume_mining_contract(contract_id):
    """Resume a paused mining contract"""
    try:
        contract = MiningContract.query.filter_by(
            id=contract_id,
            user_id=current_user.id
        ).first()
        
        if not contract:
            flash('Mining contract not found.', 'danger')
            return redirect(url_for('staking.mining_home'))
        
        if contract.status != MiningContractStatus.PAUSED:
            flash('Only paused contracts can be resumed.', 'warning')
            return redirect(url_for('staking.mining_home'))
        
        # Update contract status
        contract.status = MiningContractStatus.ACTIVE
        
        db.session.commit()
        
        flash(f'Mining contract "{contract.name}" has been resumed.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resuming mining contract {contract_id}: {str(e)}")
        flash('Error resuming mining contract. Please try again.', 'danger')
    
    return redirect(url_for('staking.mining_home'))

@staking_bp.route('/mining/contract/cancel', methods=['POST'])
@login_required
def cancel_mining_contract():
    """Cancel a mining contract"""
    try:
        contract_id = request.form.get('contract_id')
        confirm_cancel = request.form.get('confirm_cancel')
        
        if not contract_id or not confirm_cancel:
            flash('Invalid cancellation request.', 'danger')
            return redirect(url_for('staking.mining_home'))
        
        contract = MiningContract.query.filter_by(
            id=int(contract_id),
            user_id=current_user.id
        ).first()
        
        if not contract:
            flash('Mining contract not found.', 'danger')
            return redirect(url_for('staking.mining_home'))
        
        if contract.status not in [MiningContractStatus.PENDING, MiningContractStatus.ACTIVE, MiningContractStatus.PAUSED]:
            flash('This contract cannot be cancelled.', 'warning')
            return redirect(url_for('staking.mining_home'))
        
        # Update contract status
        contract.status = MiningContractStatus.CANCELLED
        contract.end_date = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'Mining contract "{contract.name}" has been cancelled.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cancelling mining contract: {str(e)}")
        flash('Error cancelling mining contract. Please try again.', 'danger')
    
    return redirect(url_for('staking.mining_home'))

# AJAX endpoints for smoother UX
@staking_bp.route('/api/mining/contract/<int:contract_id>/pause', methods=['POST'])
@login_required
def api_pause_mining_contract(contract_id):
    """API endpoint to pause mining contract"""
    try:
        success = MiningService.control_mining_contract(
            current_user.id, 
            contract_id, 
            'pause'
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Contract paused successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to pause contract'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@staking_bp.route('/api/mining/contract/<int:contract_id>/resume', methods=['POST'])
@login_required
def api_resume_mining_contract(contract_id):
    """API endpoint to resume mining contract"""
    try:
        success = MiningService.control_mining_contract(
            current_user.id, 
            contract_id, 
            'resume'
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Contract resumed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to resume contract'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500