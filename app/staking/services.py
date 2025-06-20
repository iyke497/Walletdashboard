from decimal import Decimal
from datetime import datetime, timedelta
from flask import current_app
from app.models import User, Holding, Asset, AssetType, StakingPosition, MiningPool, HashratePackage, MiningContract, Transaction, MiningContractStatus, MiningEarnings, MiningEarningsStatus, MiningDifficulty, MiningAlgorithm    
from app.extensions import db
from sqlalchemy import or_, func


class AssetService:
    @staticmethod
    def get_assets(page=1, per_page=10, search=''):
        """Get assets with pagination and search functionality"""
        #query = Asset.query.filter(Asset.is_active == True)
        #query = Asset.query.filter(Asset.images.isnot(None))
        query = Asset.query.filter(
                                Asset.asset_type == AssetType.CRYPTO,  # Only crypto assets
                                Asset.images.isnot(None))              # Only assets with images
        
        # Add search filter if provided
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    Asset.symbol.ilike(search_filter),
                    Asset.name.ilike(search_filter)
                )
            )
        
        # Order by symbol for consistent results
        query = query.order_by(Asset.id)
        
        # Apply pagination
        paginated_assets = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return paginated_assets
    
    @staticmethod
    def get_all_assets():
        """Get all assets without pagination (for backwards compatibility)"""
        return Asset.query.filter(Asset.is_active == True).all()
    
    @staticmethod
    def get_user_balance(user_id, asset_id):
        """Get user balance for a specific asset"""
        holding = Holding.query.filter_by(
            user_id=user_id,
            asset_id=asset_id
        ).first()
        
        if holding:
            return holding.balance
        return Decimal('0')
    
    @staticmethod
    def get_user_balances(user_id, asset_ids=None):
        """Get user balances for multiple assets or all assets"""
        query = Holding.query.filter_by(user_id=user_id)
        
        if asset_ids:
            query = query.filter(Holding.asset_id.in_(asset_ids))
        
        holdings = query.all()
        
        # Return dict with asset_id as key and balance as value
        balances = {}
        for holding in holdings:
            balances[holding.asset_id] = holding.balance
        
        return balances

class StakingService:
    @staticmethod
    def create_staking_position(user_id, asset_id, amount, period_days=None, apr=None):
        """Create a new staking position"""
        try:
            # Validate user has sufficient balance
            user_balance = AssetService.get_user_balance(user_id, asset_id)
            if user_balance < Decimal(str(amount)):
                return {
                    'success': False,
                    'error': 'Insufficient balance',
                    'message': f'You only have {user_balance} available for staking'
                }
            
            # Get asset info
            asset = Asset.query.get(asset_id)
            if not asset:
                return {
                    'success': False,
                    'error': 'Asset not found',
                    'message': 'The selected asset could not be found'
                }
            
            # Calculate lock period
            locked_until = None
            if period_days and period_days > 0:
                locked_until = datetime.utcnow() + timedelta(days=period_days)
            
            # Determine APR based on period
            if not apr:
                apr_rates = {
                    None: 4.5,    # Flexible
                    30: 5.0,
                    60: 5.5,
                    90: 6.0
                }
                apr = apr_rates.get(period_days, 4.5)
            
            # Create staking position
            staking_position = StakingPosition(
                user_id=user_id,
                asset_id=asset_id,
                amount=Decimal(str(amount)),
                locked_until=locked_until,
                apy=Decimal(str(apr)),
                provider='Internal'
            )
            
            # Update user holding (subtract staked amount from available balance)
            holding = Holding.query.filter_by(
                user_id=user_id,
                asset_id=asset_id
            ).first()
            
            if holding:
                holding.balance -= Decimal(str(amount))
            else:
                # This shouldn't happen if validation passed, but handle it
                return {
                    'success': False,
                    'error': 'Balance error',
                    'message': 'Could not find user balance record'
                }
            
            # Save to database
            db.session.add(staking_position)
            db.session.commit()
            
            return {
                'success': True,
                'staking_position_id': staking_position.id,
                'message': f'Successfully staked {amount} {asset.symbol}',
                'data': {
                    'amount': str(amount),
                    'asset_symbol': asset.symbol,
                    'asset_name': asset.name,
                    'apr': str(apr),
                    'locked_until': locked_until.isoformat() if locked_until else None,
                    'is_flexible': locked_until is None
                }
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating staking position: {str(e)}")
            return {
                'success': False,
                'error': 'System error',
                'message': 'An error occurred while creating the staking position'
            }
    
    @staticmethod
    def get_user_staking_positions_old(user_id):
        """Get all staking positions for a user"""
        positions = StakingPosition.query.filter_by(
            user_id=user_id
        ).join(Asset).all()
        
        result = []
        for position in positions:
            result.append({
                'id': position.id,
                'asset_id': position.asset_id,
                'asset_symbol': position.asset.symbol,
                'asset_name': position.asset.name,
                'asset_image': position.asset.images.get('small', ''),
                'amount': str(position.amount),
                'apr': str(position.apy) if position.apy else '0',
                'locked_until': position.locked_until.isoformat() if position.locked_until else None,
                'is_flexible': position.locked_until is None,
                'created_at': position.created_at.isoformat(),
                
            })
        
        return result
    
    # <-------------------Start----------------->
    @staticmethod
    def get_user_staking_positions(user_id):
        """Get all staking positions for a user with formatted data for the template."""
        positions = StakingPosition.query.filter_by(user_id=user_id).join(Asset).order_by(StakingPosition.created_at.desc()).all()
        now = datetime.utcnow()
        result = []

        for position in positions:
            # Calculate period display (Flexible or X Days)
            period_display = "Flexible"
            if position.locked_until:
                if position.created_at:
                    delta_days = (position.locked_until - position.created_at).days
                    period_display = f"{delta_days} Days" if delta_days > 0 else "Flexible"
                else:
                    period_display = f"Locked until {position.locked_until.strftime('%Y-%m-%d')}"

            # Calculate estimated rewards
            days_staked = (now - position.created_at).days if position.created_at else 0
            estimated_rewards = Decimal('0')
            if position.apy and days_staked > 0:
                daily_rate = position.apy / Decimal('100') / Decimal('365')
                estimated_rewards = position.amount * daily_rate * Decimal(days_staked)

            # Determine status and unstake eligibility
            status = 'active'
            can_unstake = False
            if position.locked_until:
                if position.locked_until > now:
                    status = 'active'  # Still locked
                    can_unstake = False
                else:
                    status = 'completed'  # Lock period ended
                    can_unstake = True
            else:
                can_unstake = True  # Flexible can unstake anytime

            result.append({
                'id': position.id,
                'asset_symbol': position.asset.symbol,
                'asset_name': position.asset.name,
                'asset_image': position.asset.images.get('small', '') if position.asset.images else None,
                'amount': str(position.amount),
                'apr': f"{position.apy:.1f}",  # Format APR as string with one decimal
                'start_date': position.created_at,
                'end_date': position.locked_until,
                'period_display': period_display,
                'estimated_rewards': f"{estimated_rewards.quantize(Decimal('0.00000001'))}",
                'status': status,
                'can_unstake': can_unstake
            })
        return result


    # <------------------End-------------------->
    @staticmethod
    def unstake_position(user_id, position_id):
        """Unstake a position (if it's flexible or lock period has ended)"""
        try:
            position = StakingPosition.query.filter_by(
                id=position_id,
                user_id=user_id
            ).first()
            
            if not position:
                return {
                    'success': False,
                    'error': 'Position not found',
                    'message': 'Staking position not found'
                }
            
            # Check if position can be unstaked
            if position.locked_until and position.locked_until > datetime.utcnow():
                return {
                    'success': False,
                    'error': 'Position locked',
                    'message': f'Position is locked until {position.locked_until.strftime("%Y-%m-%d %H:%M:%S")}'
                }
            
            # Return funds to user's holding
            holding = Holding.query.filter_by(
                user_id=user_id,
                asset_id=position.asset_id
            ).first()
            
            if holding:
                holding.balance += position.amount
            else:
                # Create new holding if it doesn't exist
                holding = Holding(
                    user_id=user_id,
                    asset_id=position.asset_id,
                    balance=position.amount
                )
                db.session.add(holding)
            
            # Remove staking position
            db.session.delete(position)
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Successfully unstaked {position.amount} {position.asset.symbol}',
                'amount': str(position.amount),
                'asset_symbol': position.asset.symbol
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error unstaking position: {str(e)}")
            return {
                'success': False,
                'error': 'System error',
                'message': 'An error occurred while unstaking the position'
            }
    
    @staticmethod
    def get_staking_rewards(position_id):
        """Calculate current rewards for a staking position"""
        position = StakingPosition.query.get(position_id)
        if not position:
            return None
        
        # Calculate days staked
        days_staked = (datetime.utcnow() - position.created_at).days
        if days_staked == 0:
            days_staked = 1  # At least one day for calculation
        
        # Calculate rewards (simple daily compounding)
        if position.apy:
            daily_rate = position.apy / 100 / 365
            rewards = position.amount * daily_rate * days_staked
        else:
            rewards = Decimal('0')
        
        return {
            'position_id': position.id,
            'days_staked': days_staked,
            'rewards': str(rewards),
            'total_value': str(position.amount + rewards)
        }


# Complete the MiningService class in services.py

class MiningService:
    @staticmethod
    def get_available_pools_old(page=1, per_page=10, search='', algorithm='', difficulty=''):
        """Get available mining pools with pagination and filtering"""
        query = MiningPool.query.filter(MiningPool.is_active == True)
        
        # Add search filter
        if search:
            search_filter = f"%{search}%"
            query = query.join(Asset).filter(
                or_(
                    Asset.symbol.ilike(search_filter),
                    Asset.name.ilike(search_filter),
                    MiningPool.name.ilike(search_filter)
                )
            )
        
        # Add algorithm filter
        if algorithm:
            query = query.filter(MiningPool.algorithm == algorithm)
        
        # Add difficulty filter
        if difficulty:
            query = query.filter(MiningPool.difficulty == difficulty)
        
        # Order by estimated earnings (highest first)
        query = query.order_by(MiningPool.estimated_daily_earnings_per_unit.desc())
        
        # Apply pagination
        paginated_pools = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return paginated_pools
    
    @staticmethod
    def get_available_pools(page=1, per_page=10, search='', algorithm='', difficulty=''):
        """
        Get available mining pools with pagination and filtering
        
        Args:
            page (int): Page number
            per_page (int): Items per page
            search (str): Search query for name or symbol
            algorithm (str): Filter by algorithm type
            difficulty (str): Filter by difficulty level
        
        Returns:
            Pagination object containing filtered mining pools
        """
        query = MiningPool.query.filter(MiningPool.is_active == True)
        
        # Always join with Asset to ensure we have access to asset data
        query = query.join(Asset)
        
        # Add search filter
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    Asset.symbol.ilike(search_filter),
                    Asset.name.ilike(search_filter),
                    MiningPool.name.ilike(search_filter)
                )
            )
        
        # Add algorithm filter
        if algorithm:
            # Handle both string values and enum values
            if isinstance(algorithm, str) and algorithm in MiningAlgorithm.__members__:
                algorithm = MiningAlgorithm[algorithm.upper()]
            query = query.filter(MiningPool.algorithm == algorithm)
        
        # Add difficulty filter
        if difficulty:
            # Handle both string values and enum values
            if isinstance(difficulty, str) and difficulty in MiningDifficulty.__members__:
                difficulty = MiningDifficulty[difficulty.upper()]
            query = query.filter(MiningPool.difficulty == difficulty)
        
        # Order by estimated earnings (highest first)
        query = query.order_by(MiningPool.estimated_daily_earnings_per_unit.desc())
        
        # Apply pagination
        paginated_pools = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return paginated_pools


    @staticmethod
    def get_pool_by_id(pool_id):
        """
        Get a specific mining pool by ID with related asset data
        
        Args:
            pool_id (int): The ID of the mining pool
            
        Returns:
            MiningPool: The mining pool or None if not found
        """
        return MiningPool.query.join(Asset).filter(MiningPool.id == pool_id).first()



    @staticmethod
    def get_pool_packages(pool_id):
        """Get hashrate packages for a specific pool"""
        packages = HashratePackage.query.filter_by(
            pool_id=pool_id,
            is_active=True
        ).order_by(HashratePackage.sort_order, HashratePackage.hashrate).all()
        
        return packages
    
    @staticmethod
    def get_user_contracts(user_id, include_inactive=False):
        """Get all mining contracts for a user with formatted data for template"""
        query = MiningContract.query.filter_by(user_id=user_id)
        
        if not include_inactive:
            query = query.filter(
                MiningContract.status.in_([
                    MiningContractStatus.PENDING,
                    MiningContractStatus.ACTIVE,
                    MiningContractStatus.PAUSED
                ])
            )
        
        contracts = query.join(MiningPool).join(Asset).order_by(
            MiningContract.created_at.desc()
        ).all()
        
        result = []
        now = datetime.utcnow()
        
        for contract in contracts:
            # Calculate uptime and status
            if contract.status == MiningContractStatus.ACTIVE:
                hours_since_start = (now - contract.start_date).total_seconds() / 3600 if contract.start_date else 0
                uptime_hours = hours_since_start * (contract.uptime_percentage / 100) if contract.uptime_percentage else 0
                uptime_display = f"{uptime_hours:.1f}h" if uptime_hours < 24 else f"{uptime_hours/24:.1f}d"
            else:
                uptime_display = "N/A"
            
            # Determine if contract can be controlled
            can_pause = contract.status == MiningContractStatus.ACTIVE
            can_resume = contract.status == MiningContractStatus.PAUSED
            can_unstake = contract.status in [MiningContractStatus.ACTIVE, MiningContractStatus.PAUSED]
            
            # Calculate estimated daily earnings
            daily_earnings = contract.estimated_daily_earnings if hasattr(contract, 'estimated_daily_earnings') else 0
            
            result.append({
                'id': contract.id,
                'name': contract.name or f"{contract.pool.asset.symbol} Miner #{contract.id}",
                'asset_symbol': contract.pool.asset.symbol,
                'asset_name': contract.pool.asset.name,
                'asset_image': contract.pool.asset.images.get('small', '') if contract.pool.asset.images else None,
                'hashrate': f"{contract.current_hashrate or contract.hashrate} {contract.hashrate_unit.value}",
                'power_consumption': contract.power_consumption_watts,
                'pool_fee': f"{contract.pool.pool_fee * 100:.1f}%",
                'daily_earnings': f"${daily_earnings:.2f}",
                'status': contract.status.value,
                'uptime_percentage': f"{contract.uptime_percentage:.1f}%",
                'uptime_display': uptime_display,
                'start_date': contract.start_date,
                'end_date': contract.end_date,
                'hardware_type': contract.hardware_type,
                'can_pause': can_pause,
                'can_resume': can_resume,
                'can_unstake': can_unstake,
                'apr': f"{contract.pool.estimated_daily_earnings_per_unit * 365 / 1000:.1f}%"  # Rough APR calculation
            })
        
        return result
    
    @staticmethod
    def get_user_earnings_summary(user_id):
        """Get user's mining earnings summary for the earnings tab"""
        
        now = datetime.utcnow()
        today = now.date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        # Get earnings by time period
        earnings_query = db.session.query(
            func.sum(MiningEarnings.amount_usd).label('total_usd')
        ).join(MiningContract).filter(
            MiningContract.user_id == user_id,
            MiningEarnings.status == 'paid'
        )
        
        # Today's earnings
        today_earnings = earnings_query.filter(
            MiningEarnings.date == today
        ).scalar() or 0
        
        # This week's earnings
        week_earnings = earnings_query.filter(
            MiningEarnings.date >= week_start
        ).scalar() or 0
        
        # This month's earnings
        month_earnings = earnings_query.filter(
            MiningEarnings.date >= month_start
        ).scalar() or 0
        
        # Total earnings
        total_earnings = earnings_query.scalar() or 0
        
        # Get earnings by coin
        earnings_by_coin = db.session.query(
            Asset.symbol,
            Asset.name,
            func.sum(MiningEarnings.amount_mined).label('total_mined'),
            func.sum(MiningEarnings.amount_usd).label('total_usd')
        ).join(MiningContract).join(MiningPool).join(Asset).filter(
            MiningContract.user_id == user_id,
            MiningEarnings.status == 'paid'
        ).group_by(Asset.id, Asset.symbol, Asset.name).all()
        
        # Calculate percentages for coin distribution
        coin_distribution = []
        for coin_data in earnings_by_coin:
            percentage = (coin_data.total_usd / total_earnings * 100) if total_earnings > 0 else 0
            coin_distribution.append({
                'symbol': coin_data.symbol,
                'name': coin_data.name,
                'amount_mined': float(coin_data.total_mined),
                'usd_value': float(coin_data.total_usd),
                'percentage': percentage
            })
        
        # Get recent payouts
        recent_payouts = db.session.query(MiningEarnings).join(
            MiningContract
        ).join(MiningPool).join(Asset).filter(
            MiningContract.user_id == user_id
        ).order_by(MiningEarnings.date.desc()).limit(10).all()
        
        payout_history = []
        for payout in recent_payouts:
            payout_history.append({
                'date': payout.date,
                'asset_symbol': payout.contract.pool.asset.symbol,
                'asset_name': payout.contract.pool.asset.name,
                'amount_mined': float(payout.amount_mined),
                'usd_value': float(payout.amount_usd),
                'status': payout.status.value
            })
        
        return {
            'today_earnings': float(today_earnings),
            'week_earnings': float(week_earnings),
            'month_earnings': float(month_earnings),
            'total_earnings': float(total_earnings),
            'coin_distribution': coin_distribution,
            'recent_payouts': payout_history
        }
    
    @staticmethod
    def can_user_start_contract(user_id, pool_id):
        """Check if user can start a mining contract for this pool"""
        pool = MiningPool.query.get(pool_id)
        if not pool or not pool.is_active:
            return False
        
        # Check if user has any payment method or sufficient balance
        # This would integrate with your payment/balance system
        return True
    
    @staticmethod
    def validate_user_can_pay(user_id, amount):
        """Validate user has sufficient balance to pay for contract"""
        # This should check user's USD balance or payment methods
        # For now, assuming they can pay (implement based on your payment system)
        
        # Example implementation:
        usd_asset_id = 1  # Assuming USD asset ID is 1
        user_balance = AssetService.get_user_balance(user_id, usd_asset_id)
        return user_balance >= Decimal(str(amount))
    
    @staticmethod
    def control_mining_contract(user_id, contract_id, action):
        """Control mining contract (pause, resume, cancel)"""
        try:
            contract = MiningContract.query.filter_by(
                id=contract_id,
                user_id=user_id
            ).first()
            
            if not contract:
                return False
            
            if action == 'pause' and contract.can_pause:
                contract.status = MiningContractStatus.PAUSED
                contract.last_active_at = datetime.utcnow()
                
            elif action == 'resume' and contract.can_resume:
                contract.status = MiningContractStatus.ACTIVE
                
            elif action == 'cancel' and contract.can_cancel:
                contract.status = MiningContractStatus.CANCELLED
                # Optionally process refund logic here
                
            else:
                return False
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error controlling mining contract: {str(e)}")
            return False
    
    @staticmethod
    def get_withdrawable_assets(user_id):
        """Get assets that user can withdraw mining earnings as"""
        # Get assets where user has mining earnings
        assets_with_earnings = db.session.query(Asset).join(
            MiningPool
        ).join(MiningContract).filter(
            MiningContract.user_id == user_id,
            MiningContract.status == MiningContractStatus.ACTIVE
        ).distinct().all()
        
        return assets_with_earnings
    
    @staticmethod
    def get_available_earnings_balance(user_id, asset_id):
        """Get available earnings balance for withdrawal"""
        
        # Sum up all paid earnings for this user and asset
        total_earnings = db.session.query(
            func.sum(MiningEarnings.amount_mined)
        ).join(MiningContract).join(MiningPool).filter(
            MiningContract.user_id == user_id,
            MiningPool.asset_id == asset_id,
            MiningEarnings.status == 'paid'
        ).scalar() or Decimal('0')
        
        # Subtract any previous withdrawals (would need withdrawal tracking)
        # For now, return total earnings
        return total_earnings
    
    @staticmethod
    def get_total_positions(user_id):
        """Get total number of mining positions for user"""
        return MiningContract.query.filter_by(user_id=user_id).count()
    
    @staticmethod
    def get_active_positions(user_id):
        """Get number of active mining positions for user"""
        return MiningContract.query.filter_by(
            user_id=user_id,
            status=MiningContractStatus.ACTIVE
        ).count()
    
    @staticmethod
    def update_contract_performance(contract_id, hashrate, uptime_percentage):
        """Update mining contract performance metrics"""
        try:
            contract = MiningContract.query.get(contract_id)
            if contract:
                contract.current_hashrate = hashrate
                contract.uptime_percentage = uptime_percentage
                contract.last_active_at = datetime.utcnow()
                db.session.commit()
                return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating contract performance: {str(e)}")
        return False
    
    @staticmethod
    def create_daily_earnings(contract_id, date, amount_mined, amount_usd, hashrate_used, uptime_hours=24):
        """Create daily earnings record for a mining contract"""

        try:
            # Check if earnings already exist for this date
            existing = MiningEarnings.query.filter_by(
                contract_id=contract_id,
                date=date
            ).first()
            
            if existing:
                return existing
            
            contract = MiningContract.query.get(contract_id)
            if not contract:
                return None
            
            # Calculate pool fee
            pool_fee_amount = Decimal(str(amount_mined)) * contract.pool.pool_fee
            
            earnings = MiningEarnings(
                contract_id=contract_id,
                date=date,
                amount_mined=amount_mined,
                amount_usd=amount_usd,
                hashrate_used=hashrate_used,
                uptime_hours=uptime_hours,
                pool_fee_amount=pool_fee_amount,
                status=MiningEarningsStatus.PENDING
            )
            
            db.session.add(earnings)
            db.session.commit()
            
            return earnings
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating daily earnings: {str(e)}")
            return None


    #-------------- New functions --------------------------
    @staticmethod
    def get_hashrate_packages(pool_id=None):
        """
        Get available hashrate packages
        
        Args:
            pool_id (int, optional): Filter by pool ID
            
        Returns:
            list: List of HashratePackage objects
        """
        query = HashratePackage.query.filter(HashratePackage.is_active == True)
        
        if pool_id:
            query = query.filter(HashratePackage.pool_id == pool_id)
            
        return query.order_by(HashratePackage.sort_order).all()
    
    @staticmethod
    def create_mining_contract_old(user_id, pool_id, hashrate, duration, package_id=None):
        """
        Create a new mining contract
        
        Args:
            user_id (int): User ID
            pool_id (int): Mining pool ID
            hashrate (float): Purchased hashrate
            duration (int): Contract duration in MONTHS (changed from days)
            package_id (int, optional): Hashrate package ID
            
        Returns:
            MiningContract: The newly created mining contract
        """
        try:
            # Get the pool
            pool = MiningService.get_pool_by_id(pool_id)
            if not pool or not pool.is_active:
                raise ValueError("Mining pool not available")
            
            # Get package if provided
            package = None
            if package_id:
                package = HashratePackage.query.get(package_id)
                if not package or not package.is_active:
                    raise ValueError("Invalid hashrate package")
                
                # Use package hashrate if provided
                hashrate = package.hashrate
            
            # Validate hashrate
            if hashrate < float(pool.min_hashrate):
                raise ValueError(f"Minimum hashrate is {pool.min_hashrate} {pool.min_hashrate_unit.value}")
            
            # Duration is now in months directly
            duration_months = duration
            
            # Use package cost if available, otherwise calculate
            if package:
                monthly_cost = package.monthly_cost_usd
                total_cost = monthly_cost * duration_months
                power_consumption = package.power_consumption_watts
                hardware_type = package.name
            else:
                # Calculate cost based on hashrate (simplified - replace with your pricing logic)
                cost_per_hashrate = 5.0  # $5 per unit per month
                monthly_cost = float(hashrate) * cost_per_hashrate
                total_cost = monthly_cost * duration_months
                power_consumption = None
                hardware_type = f"{pool.asset.symbol} Miner"
            
            # Create contract name if not provided
            contract_name = f"{pool.asset.symbol} Mining - {hashrate} {pool.min_hashrate_unit.value}"
            
            # Create the contract
            contract = MiningContract(
                user_id=user_id,
                pool_id=pool_id,
                package_id=package_id,
                name=contract_name,
                hashrate=hashrate,
                hashrate_unit=pool.min_hashrate_unit,
                duration_months=int(duration_months),
                monthly_cost_usd=monthly_cost,
                total_cost_usd=total_cost,
                status=MiningContractStatus.PENDING,
                power_consumption_watts=power_consumption,
                hardware_type=hardware_type
            )
            
            # Add to database
            db.session.add(contract)
            db.session.commit()
            
            current_app.logger.info(f"Mining contract created: ID={contract.id}, User={user_id}, Pool={pool_id}")
            return contract
            
        except Exception as e:
            current_app.logger.error(f"Failed to create mining contract: {str(e)}")
            db.session.rollback()
            raise e

    # Update your MiningService.create_mining_contract method in services.py

    @staticmethod
    def create_mining_contract(user_id, pool_id, hashrate, duration, package_id=None):
        """
        Create a new mining contract
        
        Args:
            user_id (int): User ID
            pool_id (int): Mining pool ID
            hashrate (float): Purchased hashrate
            duration (int): Contract duration in MONTHS
            package_id (int, optional): Hashrate package ID
            
        Returns:
            MiningContract: The newly created mining contract
        """
        try:
            # Get the pool
            pool = MiningService.get_pool_by_id(pool_id)
            if not pool or not pool.is_active:
                raise ValueError("Mining pool not available")
            
            current_app.logger.info(f"Pool min_hashrate: {pool.min_hashrate} {pool.min_hashrate_unit.value}")
            current_app.logger.info(f"Requested hashrate: {hashrate}")
            
            # Get package if provided
            package = None
            if package_id:
                package = HashratePackage.query.get(package_id)
                if not package or not package.is_active:
                    raise ValueError("Invalid hashrate package")
                
                current_app.logger.info(f"Using package {package.id}: {package.name} - {package.hashrate} {package.hashrate_unit.value}")
                # Use package hashrate if provided
                hashrate = float(package.hashrate)
            
            # FIXED: Better hashrate validation with tolerance for floating point precision
            min_hashrate = float(pool.min_hashrate)
            tolerance = 0.01  # Small tolerance for floating point comparison
            
            current_app.logger.info(f"Validation: {hashrate} >= {min_hashrate} (tolerance: {tolerance})")
            
            if hashrate < (min_hashrate - tolerance):
                current_app.logger.error(f"Hashrate validation failed: {hashrate} < {min_hashrate}")
                raise ValueError(f"Minimum hashrate is {pool.min_hashrate} {pool.min_hashrate_unit.value}")
            else:
                current_app.logger.info(f"Hashrate validation passed: {hashrate} >= {min_hashrate}")
            
            # Duration is now in months directly
            duration_months = duration
            
            # Use package cost if available, otherwise calculate
            if package:
                monthly_cost = float(package.monthly_cost_usd)
                total_cost = monthly_cost * duration_months
                power_consumption = package.power_consumption_watts
                hardware_type = package.name
                current_app.logger.info(f"Using package pricing: ${monthly_cost}/month")
            else:
                # Calculate cost based on hashrate (simplified - replace with your pricing logic)
                cost_per_hashrate = 5.0  # $5 per unit per month
                monthly_cost = float(hashrate) * cost_per_hashrate
                total_cost = monthly_cost * duration_months
                power_consumption = None
                hardware_type = f"{pool.asset.symbol} Miner"
                current_app.logger.info(f"Using default pricing: ${monthly_cost}/month")
            
            # Create contract name if not provided
            contract_name = f"{pool.asset.symbol} Mining - {hashrate} {pool.min_hashrate_unit.value}"
            
            current_app.logger.info(f"Creating contract: {contract_name}")
            current_app.logger.info(f"Cost breakdown: ${monthly_cost}/month x {duration_months} months = ${total_cost}")
            
            # Create the contract
            contract = MiningContract(
                user_id=user_id,
                pool_id=pool_id,
                package_id=package_id,
                name=contract_name,
                hashrate=hashrate,
                hashrate_unit=pool.min_hashrate_unit,
                duration_months=int(duration_months),
                monthly_cost_usd=monthly_cost,
                total_cost_usd=total_cost,
                status=MiningContractStatus.PENDING,
                power_consumption_watts=power_consumption,
                hardware_type=hardware_type
            )
            
            # Add to database
            db.session.add(contract)
            db.session.commit()
            
            current_app.logger.info(f"Mining contract created successfully: ID={contract.id}, User={user_id}, Pool={pool_id}")
            return contract
            
        except Exception as e:
            current_app.logger.error(f"Failed to create mining contract: {str(e)}")
            db.session.rollback()
            raise e    