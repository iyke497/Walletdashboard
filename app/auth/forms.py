from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Optional, Length
from ..models import User, Asset, AssetType

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email    = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm  = PasswordField('Confirm Password',
                             validators=[DataRequired(), EqualTo('password')])
    submit   = SubmitField('Register')
    agree_terms = BooleanField('I agree to privacy policy & terms', validators=[DataRequired()])

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

class LoginForm(FlaskForm):
    email_or_username = StringField('Email or Username', validators=[DataRequired()])
    password          = PasswordField('Password', validators=[DataRequired()])
    remember          = BooleanField('Remember Me')
    submit            = SubmitField('Login')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')
    
    def validate_email(self, field):
        user = User.query.filter_by(email=field.data).first()
        if not user:
            raise ValidationError('No account found with that email address.')
        
class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired()])
    confirm = PasswordField('Confirm New Password', 
                           validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Save Changes')
    
    def __init__(self, current_user, *args, **kwargs):
        super(ChangePasswordForm, self).__init__(*args, **kwargs)
        self.current_user = current_user
    
    def validate_current_password(self, field):
        if not self.current_user.check_password(field.data):
            raise ValidationError('Current password is incorrect.')

class UserSettingsForm(FlaskForm):
    # Basic user info from database
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    
    # Additional profile fields
    first_name = StringField('First Name', validators=[Optional(), Length(max=50)])
    last_name = StringField('Last Name', validators=[Optional(), Length(max=50)])
    phone_number = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    address = StringField('Address', validators=[Optional(), Length(max=200)])
    state = StringField('State', validators=[Optional(), Length(max=50)])
    zip_code = StringField('Zip Code', validators=[Optional(), Length(max=10)])
    
    # Dropdown fields
    country = SelectField('Country', choices=[
        ('', 'Select'),
        ('Australia', 'Australia'),
        ('Bangladesh', 'Bangladesh'),
        ('Belarus', 'Belarus'),
        ('Brazil', 'Brazil'),
        ('Canada', 'Canada'),
        ('China', 'China'),
        ('France', 'France'),
        ('Germany', 'Germany'),
        ('India', 'India'),
        ('Indonesia', 'Indonesia'),
        ('Israel', 'Israel'),
        ('Italy', 'Italy'),
        ('Japan', 'Japan'),
        ('Korea', 'Korea, Republic of'),
        ('Mexico', 'Mexico'),
        ('Philippines', 'Philippines'),
        ('Russia', 'Russian Federation'),
        ('South Africa', 'South Africa'),
        ('Thailand', 'Thailand'),
        ('Turkey', 'Turkey'),
        ('Ukraine', 'Ukraine'),
        ('United Arab Emirates', 'United Arab Emirates'),
        ('United Kingdom', 'United Kingdom'),
        ('United States', 'United States')
    ], validators=[Optional()])
    
    language = SelectField('Language', choices=[
        ('', 'Select Language'),
        ('en', 'English'),
        ('fr', 'French'),
        ('de', 'German'),
        ('pt', 'Portuguese')
    ], validators=[Optional()])
    
    timezone = SelectField('Timezone', choices=[
        ('', 'Select Timezone'),
        ('-12', '(GMT-12:00) International Date Line West'),
        ('-11', '(GMT-11:00) Midway Island, Samoa'),
        ('-10', '(GMT-10:00) Hawaii'),
        ('-9', '(GMT-09:00) Alaska'),
        ('-8', '(GMT-08:00) Pacific Time (US & Canada)'),
        ('-8', '(GMT-08:00) Tijuana, Baja California'),
        ('-7', '(GMT-07:00) Arizona'),
        ('-7', '(GMT-07:00) Chihuahua, La Paz, Mazatlan'),
        ('-7', '(GMT-07:00) Mountain Time (US & Canada)'),
        ('-6', '(GMT-06:00) Central America'),
        ('-6', '(GMT-06:00) Central Time (US & Canada)'),
        ('-6', '(GMT-06:00) Guadalajara, Mexico City, Monterrey'),
        ('-6', '(GMT-06:00) Saskatchewan'),
        ('-5', '(GMT-05:00) Bogota, Lima, Quito, Rio Branco'),
        ('-5', '(GMT-05:00) Eastern Time (US & Canada)'),
        ('-5', '(GMT-05:00) Indiana (East)'),
        ('-4', '(GMT-04:00) Atlantic Time (Canada)'),
        ('-4', '(GMT-04:00) Caracas, La Paz')
    ], validators=[Optional()])
    
    display_currency_id = SelectField('Currency', coerce=lambda x: int(x) if x else None, validators=[Optional()])

    submit = SubmitField('Save Changes')

    def __init__(self, current_user, *args, **kwargs):
        super(UserSettingsForm, self).__init__(*args, **kwargs)
        self.current_user = current_user

        # Populate currency choices from Asset model
        currency_assets = Asset.query.filter_by(asset_type=AssetType.FIAT).all()
        self.display_currency_id.choices = [(None, 'Select Currency')] + [(asset.id, f"{asset.name} ({asset.symbol})") for asset in currency_assets]
    
    def validate_username(self, field):
        if field.data != self.current_user.username:
            if User.query.filter_by(username=field.data).first():
                raise ValidationError('Username already taken.')
    
    def validate_email(self, field):
        if field.data != self.current_user.email:
            if User.query.filter_by(email=field.data).first():
                raise ValidationError('Email already registered.')
            
class EnableTwoFactorForm(FlaskForm):
    submit = SubmitField('Enable Two-Factor Authentication')

class VerifyTwoFactorForm(FlaskForm):
    verification_code = StringField('Verification Code', validators=[
        DataRequired(message='Verification code is required'),
        Length(min=6, max=6, message='Verification code must be 6 digits')
    ], render_kw={
        'placeholder': '000000',
        'maxlength': '6',
        'pattern': '[0-9]{6}',
        'inputmode': 'numeric'
    })
    submit = SubmitField('Verify and Enable')

class DisableTwoFactorForm(FlaskForm):
    verification_code = StringField('Verification Code', validators=[
        DataRequired(),
        Length(min=6, max=6, message='Verification code must be 6 digits')
    ])
    submit = SubmitField('Disable Two-Factor Authentication')