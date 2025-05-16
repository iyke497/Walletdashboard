# app/wallet/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, IntegerField, SubmitField
from wtforms.validators import DataRequired, NumberRange

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
