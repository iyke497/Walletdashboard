from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, SelectField, BooleanField
from wtforms.validators import DataRequired, Optional, NumberRange
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