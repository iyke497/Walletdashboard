from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, SelectField, BooleanField
from wtforms.validators import DataRequired, Optional, NumberRange
import json
# app/admin/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, SelectField, BooleanField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange, Length, Email, ValidationError
from app.models import Asset, AssetType
import json


class TraderForm(FlaskForm):
    user_id = SelectField('User', coerce=int, validators=[DataRequired()])
    bio = TextAreaField('Bio', validators=[Optional()])
    tags = StringField('Tags (comma-separated)', validators=[Optional()])
    win_rate = FloatField('Win Rate (%)', validators=[DataRequired(), NumberRange(min=0, max=100)])
    avg_monthly_return = FloatField('Avg Monthly Return (%)', validators=[DataRequired()])
    max_drawdown = FloatField('Max Drawdown (%)', validators=[DataRequired(), NumberRange(min=0, max=100)])
    risk_score = SelectField('Risk Score', choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')])
    is_verified = BooleanField('Verified Trader')
    performance_metrics = TextAreaField('Performance Metrics (JSON)', validators=[Optional()])
    
    def validate_performance_metrics(self, field):
        if field.data:
            try:
                json.loads(field.data)
            except ValueError:
                raise ValueError('Invalid JSON format. Please check your input.')
# Asset Management Forms
class AssetForm(FlaskForm):
    """Main form for creating/editing assets"""
    symbol = StringField(
        'Symbol',
        validators=[
            DataRequired(message='Symbol is required'),
            Length(min=1, max=10, message='Symbol must be 1-10 characters')
        ],
        render_kw={
            'placeholder': 'e.g., BTC, ETH, USDT',
            'class': 'form-control'
        }
    )
    
    name = StringField(
        'Name',
        validators=[
            DataRequired(message='Name is required'),
            Length(min=1, max=64, message='Name must be 1-64 characters')
        ],
        render_kw={
            'placeholder': 'e.g., Bitcoin, Ethereum, Tether',
            'class': 'form-control'
        }
    )
    
    coingecko_id = StringField(
        'CoinGecko ID',
        validators=[
            DataRequired(message='CoinGecko ID is required'),
            Length(min=1, max=50, message='CoinGecko ID must be 1-50 characters')
        ],
        render_kw={
            'placeholder': 'e.g., bitcoin, ethereum, tether',
            'class': 'form-control'
        }
    )
    
    asset_type = SelectField(
        'Asset Type',
        validators=[DataRequired(message='Asset type is required')],
        choices=[(asset_type.value, asset_type.value.title()) for asset_type in AssetType],
        render_kw={'class': 'form-select'}
    )
    
    decimals = IntegerField(
        'Decimals',
        validators=[
            DataRequired(message='Decimals is required'),
            NumberRange(min=0, max=18, message='Decimals must be between 0 and 18')
        ],
        default=8,
        render_kw={'class': 'form-control'}
    )
    
    # JSON fields as text areas for easier editing
    images_json = TextAreaField(
        'Images JSON',
        validators=[Optional()],
        render_kw={
            'placeholder': '{"thumb": "url", "small": "url", "large": "url"}',
            'class': 'form-control',
            'rows': 4
        }
    )
    
    networks_json = TextAreaField(
        'Networks JSON',
        validators=[Optional()],
        render_kw={
            'placeholder': '[{"id": "ethereum", "symbol": "ETH", "deposit_address": "0x..."}]',
            'class': 'form-control',
            'rows': 6
        }
    )
    
    is_active = BooleanField(
        'Active',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    submit = SubmitField(
        'Save Asset',
        render_kw={'class': 'btn btn-primary'}
    )
    
    def validate_images_json(self, field):
        """Validate images JSON format"""
        if field.data and field.data.strip():
            try:
                json.loads(field.data)
            except json.JSONDecodeError:
                raise ValidationError('Invalid JSON format for images')
    
    def validate_networks_json(self, field):
        """Validate networks JSON format"""
        if field.data and field.data.strip():
            try:
                networks = json.loads(field.data)
                if not isinstance(networks, list):
                    raise ValidationError('Networks must be a JSON array')
                
                for network in networks:
                    if not isinstance(network, dict):
                        raise ValidationError('Each network must be a JSON object')
                    if 'id' not in network or 'symbol' not in network:
                        raise ValidationError('Each network must have "id" and "symbol" fields')
            except json.JSONDecodeError:
                raise ValidationError('Invalid JSON format for networks')

class AssetSearchForm(FlaskForm):
    """Form for searching/filtering assets"""
    search = StringField(
        'Search',
        validators=[Optional()],
        render_kw={
            'placeholder': 'Search by symbol, name, or CoinGecko ID...',
            'class': 'form-control'
        }
    )
    
    asset_type = SelectField(
        'Asset Type',
        validators=[Optional()],
        choices=[('', 'All Types')] + [(asset_type.value, asset_type.value.title()) for asset_type in AssetType],
        render_kw={'class': 'form-select'}
    )
    
    status = SelectField(
        'Status',
        validators=[Optional()],
        choices=[
            ('', 'All'),
            ('active', 'Active'),
            ('inactive', 'Inactive')
        ],
        render_kw={'class': 'form-select'}
    )
    
    submit = SubmitField(
        'Search',
        render_kw={'class': 'btn btn-outline-primary'}
    )