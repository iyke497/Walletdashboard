from decimal import Decimal
from flask_wtf import FlaskForm
from wtforms import SelectField, DecimalField, SubmitField, RadioField, HiddenField
from wtforms.validators import DataRequired, NumberRange, ValidationError
from wtforms.widgets import NumberInput
from app.models import Asset, AssetType
from .services import CryptoSwapService

class MarketOrderForm(FlaskForm):
    base_asset   = SelectField('Asset Pair', validators=[DataRequired()])
    side         = RadioField('Side',
                              choices=[('buy','Buy'),('sell','Sell')],
                              default='buy', validators=[DataRequired()])
    amount       = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0.00000001)])
    submit       = SubmitField('Send Market Order')

class LimitOrderForm(FlaskForm):
    base_asset   = SelectField('Asset Pair', validators=[DataRequired()])
    side         = RadioField('Side',
                              choices=[('buy','Buy'),('sell','Sell')],
                              default='buy', validators=[DataRequired()])
    amount       = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0.00000001)])
    price        = DecimalField('Limit Price', validators=[DataRequired(), NumberRange(min=0.00000001)])
    submit       = SubmitField('Place Limit Order')

def coerce_int_or_none(value):
    """Custom coerce function that handles empty strings"""
    if value == '' or value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


class SwapForm(FlaskForm):
    """Form for crypto swapping"""
    
    from_asset_id = SelectField(
        'From Asset',
        coerce=coerce_int_or_none,
        validators=[DataRequired(message="Please select an asset to swap from")],
        render_kw={'class': 'form-select'}
    )
    
    to_asset_id = SelectField(
        'To Asset',
        coerce=coerce_int_or_none,
        validators=[DataRequired(message="Please select an asset to swap to")],
        render_kw={'class': 'form-select'}
    )
    
    from_amount = DecimalField(
        'Amount',
        validators=[
            DataRequired(message="Please enter amount to swap"),
            NumberRange(min=0.00000001, message="Amount must be greater than 0")
        ],
        widget=NumberInput(step="any"),
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00000000',
            'step': 'any',
            'min': '0'
        }
    )
    
    # Hidden field for confirmation step
    confirm_swap = HiddenField()
    
    # Action buttons
    preview_swap = SubmitField(
        'Preview Swap',
        render_kw={'class': 'btn btn-sm btn-outline-primary me-2'}
    )
    
    execute_swap = SubmitField(
        'Execute Swap',
        render_kw={'class': 'btn btn-sm btn-outline-primary me-2'}
    )
    
    def __init__(self, user_id=None, *args, **kwargs):
        super(SwapForm, self).__init__(*args, **kwargs)
        self.user_id = user_id
        self._populate_asset_choices()
    
    def _populate_asset_choices(self):
        """Populate asset choices for dropdowns"""
        # Get all active crypto assets for "to" dropdown
        all_assets = Asset.query.filter(
            Asset.is_active == True,
            Asset.asset_type == AssetType.CRYPTO
        ).order_by(Asset.symbol).all()
        
        all_asset_choices = [(asset.id, f"{asset.symbol} - {asset.name}") for asset in all_assets]
        
        # For "from" dropdown, only show assets user has holdings for
        if self.user_id:
            user_holdings = CryptoSwapService.get_user_crypto_holdings(self.user_id)
            from_asset_choices = [
                (asset.id, f"{asset.symbol.upper()} - {asset.name}")
                for holding, asset in user_holdings
            ]
        else:
            from_asset_choices = all_asset_choices
        
        # Use None instead of empty string for the default choice
        self.from_asset_id.choices = [(None, 'Select asset to swap from')] + from_asset_choices
        self.to_asset_id.choices = [(None, 'Select asset to receive')] + all_asset_choices
    
    def validate_from_asset_id(self, field):
        """Validate from_asset selection"""
        if field.data is None:
            raise ValidationError("Please select an asset to swap from")
        
        asset = Asset.query.get(field.data)
        if not asset or not asset.is_active:
            raise ValidationError("Selected asset is not available for trading")
    
    def validate_to_asset_id(self, field):
        """Validate to_asset selection"""
        if field.data is None:
            raise ValidationError("Please select an asset to receive")
        
        if field.data == self.from_asset_id.data:
            raise ValidationError("Cannot swap asset to itself")
        
        asset = Asset.query.get(field.data)
        if not asset or not asset.is_active:
            raise ValidationError("Selected asset is not available for trading")
    
    def validate_from_amount(self, field):
        """Validate swap amount against user balance"""
        if not field.data or field.data <= 0:
            raise ValidationError("Amount must be greater than 0")
        
        if self.user_id and self.from_asset_id.data is not None:
            user_balance = CryptoSwapService.get_user_balance(
                self.user_id, self.from_asset_id.data
            )
            
            if field.data > user_balance:
                asset = Asset.query.get(self.from_asset_id.data)
                asset_symbol = asset.symbol if asset else "asset"
                raise ValidationError(
                    f"Insufficient balance. Available: {user_balance} {asset_symbol}"
                )

