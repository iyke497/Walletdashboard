from flask_wtf import FlaskForm
from wtforms import SelectField, DecimalField, SubmitField, RadioField
from wtforms.validators import DataRequired, NumberRange

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
