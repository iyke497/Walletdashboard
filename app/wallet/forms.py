# app/wallet/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, IntegerField, SelectField, TextAreaField, SubmitField, ValidationError
from wtforms.validators import DataRequired, Email, NumberRange, Length, Optional
from app.models import User, Asset, Holding
from flask_login import current_user
from decimal import Decimal

class DepositForm(FlaskForm):
    asset = StringField('Asset', validators=[DataRequired()])
    network = StringField('Network', validators=[DataRequired()])
    amount = DecimalField('Amount', 
        validators=[DataRequired(), NumberRange(min=0.00000001, message="Must be positive")])
    submit = SubmitField('Deposit')

class WithdrawForm(FlaskForm):
    asset = StringField('Asset', validators=[DataRequired()])
    amount = DecimalField('Amount', 
        validators=[DataRequired(), NumberRange(min=0.00000001, message="Must be positive")])
    submit = SubmitField('Withdraw')

class TradeForm(FlaskForm):
    from_asset = StringField('From Asset', validators=[DataRequired()])
    to_asset   = StringField('To Asset',   validators=[DataRequired()])
    amount     = DecimalField('Amount', 
        validators=[DataRequired(), NumberRange(min=0.00000001, message="Must be positive")])
    submit     = SubmitField('Trade')

class StakeForm(FlaskForm):
    asset    = StringField('Asset', validators=[DataRequired()])
    amount   = DecimalField('Amount', 
        validators=[DataRequired(), NumberRange(min=0.00000001, message="Must be positive")])
    duration = IntegerField('Duration (days)', 
        validators=[DataRequired(), NumberRange(min=1, message="Must be ≥1 day")])
    submit   = SubmitField('Stake')

class TransferForm(FlaskForm):
    # Recipient selection
    recipient_email = StringField(
        'Recipient Email',
        validators=[
            DataRequired(message='Recipient email is required'),
            Email(message='Please enter a valid email address'),
            Length(max=120, message='Email must be less than 120 characters')
        ],
        render_kw={
            'placeholder': 'Enter recipient\'s email address',
            'class': 'form-control'
        }
    )
    
    # Asset selection (will be populated dynamically)
    asset = SelectField(
        'Select Asset',
        validators=[DataRequired(message='Please select an asset to transfer')],
        choices=[],
        render_kw={'class': 'form-select'}
    )
    
    # Transfer amount
    amount = DecimalField(
        'Amount',
        validators=[
            DataRequired(message='Amount is required'),
            NumberRange(min=0.00000001, message='Amount must be greater than 0')
        ],
        places=8,
        render_kw={
            'placeholder': '0.00000000',
            'class': 'form-control',
            'step': '0.00000001',
            'min': '0.00000001'
        }
    )
    
    # Optional note/memo
    note = TextAreaField(
        'Note (Optional)',
        validators=[
            Optional(),
            Length(max=500, message='Note must be less than 500 characters')
        ],
        render_kw={
            'placeholder': 'Add a note for this transfer (optional)',
            'class': 'form-control',
            'rows': 3
        }
    )
    
    submit = SubmitField(
    'Transfer Funds',
    render_kw={'class': 'btn btn-sm btn-outline-primary w-100'})  # Removed conflicting classes)
    
    def __init__(self, *args, **kwargs):
        super(TransferForm, self).__init__(*args, **kwargs)
        
        # Populate asset choices with user's holdings
        if current_user.is_authenticated:
            holdings = Holding.query.filter(
                Holding.user_id == current_user.id,
                Holding.balance > 0
            ).join(Asset).filter(Asset.is_active == True).all()
            
            self.asset.choices = [
                (str(holding.asset.id), f"{holding.asset.symbol.upper()} - Available: {holding.balance}")
                for holding in holdings
            ]
            
            if not self.asset.choices:
                self.asset.choices = [('', 'No assets available for transfer')]
    
    def validate_recipient_email(self, field):
        """Validate that recipient exists and is not the current user"""
        if current_user.is_authenticated:
            if field.data.lower() == current_user.email.lower():
                raise ValidationError('You cannot transfer funds to yourself')
        
        recipient = User.query.filter_by(email=field.data.lower()).first()
        if not recipient:
            raise ValidationError('Recipient email not found. Please check the email address.')
        
        if not recipient.is_active:
            raise ValidationError('Recipient account is not active')
        
        if not recipient.email_verified:
            raise ValidationError('Recipient must verify their email before receiving transfers')
    
    def validate_amount(self, field):
        """Validate that user has sufficient balance"""
        if current_user.is_authenticated and self.asset.data:
            try:
                asset_id = int(self.asset.data)
                holding = Holding.query.filter_by(
                    user_id=current_user.id,
                    asset_id=asset_id
                ).first()
                
                if not holding:
                    raise ValidationError('You do not have any balance for this asset')
                
                if field.data > holding.balance:
                    raise ValidationError(f'Insufficient balance. Available: {holding.balance}')
                    
            except (ValueError, TypeError):
                raise ValidationError('Invalid asset selected')
    
    def validate_asset(self, field):
        """Validate that the asset exists and user has balance"""
        if field.data:
            try:
                asset_id = int(field.data)
                asset = Asset.query.get(asset_id)
                if not asset or not asset.is_active:
                    raise ValidationError('Invalid asset selected')
            except (ValueError, TypeError):
                raise ValidationError('Invalid asset selected')


class TransferConfirmationForm(FlaskForm):
    """Simple form for transfer confirmation"""
    confirm = SubmitField(
        'Confirm Transfer',
        render_kw={'class': 'btn btn-success btn-lg'}
    )
    
    cancel = SubmitField(
        'Cancel',
        render_kw={'class': 'btn btn-outline-secondary btn-lg'}
    )