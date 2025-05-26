from decimal import Decimal
from datetime import datetime, timedelta
from flask import current_app
from app.models import User, Holding, Asset, AssetType, StakingPosition
from app.extensions import db
from sqlalchemy import or_


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
