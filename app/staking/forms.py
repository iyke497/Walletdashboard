# app/staking/forms.py
from decimal import Decimal, InvalidOperation
from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, HiddenField, BooleanField, TextAreaField, StringField, RadioField, IntegerField
from wtforms.validators import DataRequired, NumberRange, ValidationError,Optional, Length
from wtforms.widgets import NumberInput
from app.models import Asset, HashratePackage, MiningContract, MiningPool
from app.staking.services import AssetService
from flask_login import current_user

class StakingForm(FlaskForm):
    asset_id = HiddenField('Asset ID', validators=[DataRequired()])
    amount = DecimalField(
        'Amount to Stake',
        validators=[
            DataRequired(message="Please enter an amount"),
            NumberRange(min=0.00000001, message="Amount must be greater than 0")
        ],
        places=8,
        widget=NumberInput(step=0.00000001)
    )
    period = SelectField(
        'Staking Period',
        choices=[
            ('', 'Select staking period'),
            ('flexible', 'Flexible (No lock period - 4.5% APR)'),
            ('30', '30 Days (5.0% APR)'),
            ('60', '60 Days (5.5% APR)'),
            ('90', '90 Days (6.0% APR)')
        ],
        validators=[DataRequired(message="Please select a staking period")]
    )
    agree_terms = BooleanField(
        'I understand the staking terms and conditions',
        validators=[DataRequired(message="You must agree to the terms")]
    )

    def validate_amount(self, field):
        """Custom validator to check if user has sufficient balance"""
        if not field.data:
            return
        
        try:
            asset_id = int(self.asset_id.data)
            user_balance = AssetService.get_user_balance(current_user.id, asset_id)
            
            if field.data > user_balance:
                asset = Asset.query.get(asset_id)
                symbol = asset.symbol if asset else "Unknown"
                raise ValidationError(
                    f'Insufficient balance. Available: {user_balance:.8f} {symbol}'
                )
        except (ValueError, TypeError):
            raise ValidationError('Invalid asset or amount')

    def validate_asset_id(self, field):
        """Validate that the asset exists and is stakeable"""
        if not field.data:
            return
        
        try:
            asset_id = int(field.data)
            asset = Asset.query.get(asset_id)
            if not asset:
                raise ValidationError('Selected asset does not exist')
        except (ValueError, TypeError):
            raise ValidationError('Invalid asset selected')

class QuickStakeForm(FlaskForm):
    """Simplified form for quick staking actions"""
    asset_id = HiddenField('Asset ID', validators=[DataRequired()])
    percentage = SelectField(
        'Quick Amount',
        choices=[
            ('25', '25%'),
            ('50', '50%'),
            ('75', '75%'),
            ('100', '100% (Max)')
        ],
        validators=[DataRequired()]
    )
    period = SelectField(
        'Period',
        choices=[
            ('flexible', 'Flexible'),
            ('30', '30 Days'),
            ('60', '60 Days'),
            ('90', '90 Days')
        ],
        validators=[DataRequired()]
    )

class UnstakeForm(FlaskForm):
    """Form for unstaking positions"""
    position_id = HiddenField('Position ID', validators=[DataRequired()])
    confirm_unstake = BooleanField(
        'I confirm I want to unstake this position',
        validators=[DataRequired(message="Please confirm you want to unstake")]
    )

class MiningPoolSearchForm(FlaskForm):
    """Form for searching and filtering mining pools"""
    search = StringField(
        'Search Pools',
        validators=[Optional(), Length(max=100)],
        render_kw={'placeholder': 'Search by coin or algorithm...'}
    )
    
    algorithm = SelectField(
        'Algorithm',
        choices=[
            ('', 'All Algorithms'),
            ('sha256', 'SHA-256'),
            ('scrypt', 'Scrypt'),
            ('ethash', 'Ethash'),
            ('x11', 'X11'),
            ('equihash', 'Equihash'),
            ('cryptonight', 'CryptoNight'),
            ('blake2b', 'Blake2b'),
            ('randomx', 'RandomX')
        ],
        validators=[Optional()]
    )
    
    difficulty = SelectField(
        'Difficulty',
        choices=[
            ('', 'All Difficulties'),
            ('low', 'Low'),
            ('medium', 'Medium'), 
            ('high', 'High'),
            ('very_high', 'Very High')
        ],
        validators=[Optional()]
    )
    
    per_page = SelectField(
        'Per Page',
        choices=[('5', '5'), ('10', '10'), ('25', '25'), ('50', '50')],
        default='10',
        validators=[Optional()]
    )

# forms.py - Updated MiningContractForm with proper conditional validation

# Update your MiningContractForm class in forms.py

class MiningContractForm(FlaskForm):
    """Main form for creating a mining contract"""
    
    # Hidden fields for pool selection
    pool_id = HiddenField('Pool ID', validators=[DataRequired()])
    
    # Hashrate package selection
    package_selection = RadioField(
        'Hashrate Package',
        choices=[
            ('basic', 'Basic Package'),
            ('pro', 'Pro Package'), 
            ('enterprise', 'Enterprise Package'),
            ('custom', 'Custom Hashrate')
        ],
        validators=[DataRequired(message="Please select a hashrate package")]
    )
    
    # For package-based selection
    package_id = HiddenField('Package ID', validators=[Optional()])
    
    # For custom hashrate
    custom_hashrate = DecimalField(
        'Custom Hashrate',
        validators=[Optional()],  # Only validate conditionally
        places=2,
        render_kw={'placeholder': '0.0', 'step': '0.1', 'min': '0.1'}
    )
    
    custom_hashrate_unit = SelectField(
        'Hashrate Unit',
        choices=[
            ('TH/s', 'TH/s - Terahash per second'),
            ('GH/s', 'GH/s - Gigahash per second'),
            ('MH/s', 'MH/s - Megahash per second')
        ],
        default='TH/s',
        validators=[Optional()]  # Only validate conditionally
    )
    
    # Contract duration
    duration = SelectField(
        'Contract Duration',
        choices=[
            ('1', '1 Month'),
            ('3', '3 Months (5% discount)'),
            ('6', '6 Months (10% discount)'),
            ('12', '12 Months (15% discount)')
        ],
        validators=[DataRequired(message="Please select contract duration")]
    )
    
    # Optional contract naming
    contract_name = StringField(
        'Contract Name (Optional)',
        validators=[Optional(), Length(max=100)],
        render_kw={'placeholder': 'e.g., My BTC Miner #1'}
    )
    
    def validate_custom_hashrate(self, field):
        """Validate custom hashrate when custom package is selected"""
        if self.package_selection.data == 'custom':
            if not field.data or field.data <= 0:
                raise ValidationError('Custom hashrate is required and must be greater than 0')
    
    def validate_custom_hashrate_unit(self, field):
        """Validate custom hashrate unit when custom package is selected"""
        if self.package_selection.data == 'custom':
            valid_units = ['TH/s', 'GH/s', 'MH/s']
            if not field.data or field.data not in valid_units:
                raise ValidationError('Please select a valid hashrate unit')
        # For non-custom selections, we don't validate this field
        # The route will handle getting the hashrate unit from the pool/package
    
    def validate_pool_id(self, field):
        """Validate pool exists and is active"""
        if field.data:
            try:
                pool_id = int(field.data)
                pool = MiningPool.query.get(pool_id)
                if not pool or not pool.is_active:
                    raise ValidationError('Selected mining pool is not available')
            except (ValueError, TypeError):
                raise ValidationError('Invalid pool ID')
    
    def validate_package_id(self, field):
        """Validate package when provided"""
        if field.data and str(field.data).strip():
            try:
                package_id = int(field.data)
                package = HashratePackage.query.get(package_id)
                if not package or not package.is_active:
                    raise ValidationError('Selected package is not available')
            except (ValueError, TypeError):
                raise ValidationError('Invalid package ID format')
class MiningContractConfirmForm(FlaskForm):
    """Confirmation form for mining contract with terms agreement"""
    
    # All the contract details as hidden fields
    pool_id = HiddenField('Pool ID', validators=[DataRequired()])
    package_id = HiddenField('Package ID', validators=[Optional()])
    package_selection = HiddenField('Package Selection', validators=[DataRequired()])
    custom_hashrate = HiddenField('Custom Hashrate', validators=[Optional()])
    custom_hashrate_unit = HiddenField('Custom Hashrate Unit', validators=[Optional()])
    duration = HiddenField('Duration', validators=[DataRequired()])
    contract_name = HiddenField('Contract Name', validators=[Optional()])
    
    # Cost calculation fields (calculated server-side)
    total_cost = HiddenField('Total Cost', validators=[DataRequired()])
    monthly_cost = HiddenField('Monthly Cost', validators=[DataRequired()])
    estimated_daily_earnings = HiddenField('Estimated Daily Earnings', validators=[Optional()])
    
    # Terms agreement
    agree_terms = BooleanField(
        'I understand the mining contract terms and agree to the payment',
        validators=[DataRequired(message="You must agree to the terms to proceed")]
    )
    
    def validate_total_cost(self, field):
        """Validate user can afford the contract"""
        try:
            cost = Decimal(field.data) if field.data else Decimal('0')
            if cost <= 0:
                raise ValidationError('Invalid contract cost')
        except (ValueError, InvalidOperation):
            raise ValidationError('Invalid cost format')
class MinerControlForm(FlaskForm):
    """Form for controlling individual mining contracts"""
    
    contract_id = HiddenField('Contract ID', validators=[DataRequired()])
    action = HiddenField('Action', validators=[DataRequired()])
    
    # For pause/resume actions
    confirm_action = BooleanField(
        'I confirm this action',
        validators=[DataRequired(message="Please confirm the action")]
    )
    
    def validate_contract_id(self, field):
        """Validate contract exists and belongs to current user"""
        
        if field.data:
            contract = MiningContract.query.get(field.data)
            if not contract:
                raise ValidationError('Mining contract not found')
            if contract.user_id != current_user.id:
                raise ValidationError('Unauthorized access to mining contract')
    
    def validate_action(self, field):
        """Validate action is allowed"""
        valid_actions = ['pause', 'resume', 'cancel', 'configure']
        if field.data not in valid_actions:
            raise ValidationError('Invalid action')

class MinerConfigurationForm(FlaskForm):
    """Form for configuring mining contract settings"""
    
    contract_id = HiddenField('Contract ID', validators=[DataRequired()])
    
    # Contract naming
    contract_name = StringField(
        'Contract Name',
        validators=[Optional(), Length(max=100)],
        render_kw={'placeholder': 'e.g., My BTC Miner #1'}
    )
    
    # Power management settings
    power_limit_percentage = IntegerField(
        'Power Limit (%)',
        validators=[
            Optional(),
            NumberRange(min=50, max=100, message="Power limit must be between 50% and 100%")
        ],
        default=100,
        render_kw={'min': '50', 'max': '100', 'step': '5'}
    )
    
    # Temperature management
    temperature_target = IntegerField(
        'Target Temperature (°C)',
        validators=[
            Optional(),
            NumberRange(min=60, max=85, message="Temperature target must be between 60°C and 85°C")
        ],
        default=75,
        render_kw={'min': '60', 'max': '85'}
    )
    
    # Auto-restart settings
    auto_restart_on_failure = BooleanField(
        'Auto-restart on failure',
        default=True
    )
    
    # Notification preferences
    email_notifications = BooleanField(
        'Email notifications for status changes',
        default=True
    )
    
    # Notes
    notes = TextAreaField(
        'Notes',
        validators=[Optional(), Length(max=500)],
        render_kw={'rows': '3', 'placeholder': 'Add any notes about this mining contract...'}
    )

class MinerRemovalForm(FlaskForm):
    """Form for removing/cancelling mining contracts"""
    
    contract_id = HiddenField('Contract ID', validators=[DataRequired()])
    
    # Confirmation options
    understand_consequences = BooleanField(
        'I understand that cancelling this contract may result in forfeiture of remaining contract value',
        validators=[DataRequired(message="You must acknowledge the consequences")]
    )
    
    confirm_removal = BooleanField(
        'I confirm I want to permanently remove this mining contract',
        validators=[DataRequired(message="Please confirm the removal")]
    )
    
    # Reason for cancellation (optional)
    cancellation_reason = SelectField(
        'Reason for Cancellation (Optional)',
        choices=[
            ('', 'Select reason...'),
            ('not_profitable', 'Not profitable'),
            ('technical_issues', 'Technical issues'),
            ('switching_pools', 'Switching to different pool'),
            ('financial_reasons', 'Financial reasons'),
            ('other', 'Other')
        ],
        validators=[Optional()]
    )
    
    additional_notes = TextAreaField(
        'Additional Notes (Optional)',
        validators=[Optional(), Length(max=500)],
        render_kw={'rows': '3', 'placeholder': 'Any additional feedback...'}
    )

class EarningsWithdrawalForm(FlaskForm):
    """Form for withdrawing mining earnings"""
    
    # Amount to withdraw
    amount = DecimalField(
        'Withdrawal Amount',
        validators=[
            DataRequired(message="Amount is required"),
            NumberRange(min=0.00000001, message="Amount must be greater than 0")
        ],
        places=8,
        render_kw={'placeholder': '0.00000000', 'step': '0.00000001'}
    )
    
    # Asset selection
    asset_id = SelectField(
        'Withdraw As',
        validators=[DataRequired(message="Please select withdrawal asset")],
        coerce=int
    )
    
    # Withdrawal address
    withdrawal_address = StringField(
        'Withdrawal Address',
        validators=[
            DataRequired(message="Withdrawal address is required"),
            Length(min=20, max=100, message="Invalid address length")
        ],
        render_kw={'placeholder': 'Enter wallet address...'}
    )
    
    # Network selection
    network = SelectField(
        'Network',
        choices=[
            ('ethereum', 'Ethereum (ERC-20)'),
            ('bitcoin', 'Bitcoin'),
            ('bsc', 'Binance Smart Chain (BEP-20)'),
            ('polygon', 'Polygon (MATIC)'),
            ('tron', 'Tron (TRC-20)')
        ],
        validators=[DataRequired(message="Please select network")]
    )
    
    # 2FA if enabled
    two_factor_code = StringField(
        '2FA Code',
        validators=[Optional(), Length(min=6, max=6)],
        render_kw={'placeholder': '000000', 'autocomplete': 'off'}
    )
    
    def __init__(self, user_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate available assets for withdrawal
        if user_id:
            available_assets = MiningService.get_withdrawable_assets(user_id)
            self.asset_id.choices = [
                (asset.id, f"{asset.symbol} - {asset.name}")
                for asset in available_assets
            ]
    
    def validate_amount(self, field):
        """Validate user has sufficient earnings to withdraw"""
        
        if field.data:
            available_balance = MiningService.get_available_earnings_balance(
                current_user.id, 
                self.asset_id.data
            )
            if field.data > available_balance:
                raise ValidationError(f'Insufficient balance. Available: {available_balance}')
    
    def validate_two_factor_code(self, field):
        """Validate 2FA code if user has 2FA enabled"""
        
        if current_user.two_factor_enabled:
            if not field.data:
                raise ValidationError('2FA code is required')
            if not current_user.verify_totp(field.data):
                raise ValidationError('Invalid 2FA code')

class MiningPoolManagementForm(FlaskForm):
    """Admin form for managing mining pools (if you want admin functionality)"""
    
    asset_id = SelectField(
        'Cryptocurrency',
        validators=[DataRequired()],
        coerce=int
    )
    
    name = StringField(
        'Pool Name',
        validators=[DataRequired(), Length(max=100)],
        render_kw={'placeholder': 'e.g., Bitcoin Mining Pool'}
    )
    
    algorithm = SelectField(
        'Mining Algorithm',
        choices=[
            ('sha256', 'SHA-256'),
            ('scrypt', 'Scrypt'),
            ('ethash', 'Ethash'),
            ('x11', 'X11'),
            ('equihash', 'Equihash'),
            ('cryptonight', 'CryptoNight'),
            ('blake2b', 'Blake2b'),
            ('randomx', 'RandomX')
        ],
        validators=[DataRequired()]
    )
    
    pool_fee = DecimalField(
        'Pool Fee (%)',
        validators=[
            DataRequired(),
            NumberRange(min=0, max=10, message="Pool fee must be between 0% and 10%")
        ],
        places=2,
        render_kw={'step': '0.01', 'placeholder': '1.50'}
    )
    
    difficulty = SelectField(
        'Mining Difficulty',
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('very_high', 'Very High')
        ],
        validators=[DataRequired()]
    )
    
    min_hashrate = DecimalField(
        'Minimum Hashrate',
        validators=[
            DataRequired(),
            NumberRange(min=0.001, message="Minimum hashrate must be greater than 0")
        ],
        places=8
    )
    
    min_hashrate_unit = SelectField(
        'Hashrate Unit',
        choices=[
            ('H/s', 'H/s'),
            ('KH/s', 'KH/s'),
            ('MH/s', 'MH/s'),
            ('GH/s', 'GH/s'),
            ('TH/s', 'TH/s'),
            ('PH/s', 'PH/s')
        ],
        validators=[DataRequired()]
    )
    
    estimated_daily_earnings_per_unit = DecimalField(
        'Estimated Daily Earnings (USD per unit)',
        validators=[
            DataRequired(),
            NumberRange(min=0, message="Earnings must be non-negative")
        ],
        places=8,
        render_kw={'step': '0.00000001'}
    )
    
    description = TextAreaField(
        'Description',
        validators=[Optional(), Length(max=1000)],
        render_kw={'rows': '4'}
    )
    
    is_active = BooleanField('Active', default=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate asset choices
        assets = Asset.query.filter_by(
            asset_type='crypto',
            is_active=True
        ).order_by(Asset.symbol).all()
        
        self.asset_id.choices = [
            (asset.id, f"{asset.symbol} - {asset.name}")
            for asset in assets
        ]