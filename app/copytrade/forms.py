from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, SubmitField, BooleanField
from wtforms.validators import DataRequired, NumberRange

class CopyTraderForm(FlaskForm):
    investment_amount = DecimalField('Investment Amount', 
                                  validators=[
                                      DataRequired(),
                                      NumberRange(min=10, message="Minimum investment is $10")
                                  ])
    take_profit = DecimalField('Take profit >')
    stop_loss = DecimalField('Stop loss')
    risk_level = SelectField('Risk Level', 
                           choices=[
                               ('conservative', 'Conservative'),
                               ('moderate', 'Moderate'),
                               ('aggressive', 'Aggressive')
                           ],
                           validators=[DataRequired()])
    leverage = SelectField('Leverage',
                         choices=[
                             ('1', '1x'),
                             ('2', '2x'),
                             ('5', '5x')
                         ],
                         validators=[DataRequired()])
    agree_terms = BooleanField('Agree terms')
    submit = SubmitField('Confirm Copy')