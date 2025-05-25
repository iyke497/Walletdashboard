# app/staking/forms.py
from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, HiddenField, BooleanField
from wtforms.validators import DataRequired, NumberRange, ValidationError
from wtforms.widgets import NumberInput
from app.models import Asset
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
