from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length


class ContactForm(FlaskForm):
    full_name = StringField(
        'Full Name',
        validators=[
            DataRequired(message='Full name is required'),
            Length(min=2, max=100, message='Name must be between 2 and 100 characters')
        ],
        render_kw={'placeholder': 'john', 'class': 'form-control'}
    )
    
    email = StringField(
        'Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Please enter a valid email address')
        ],
        render_kw={'placeholder': 'johndoe@gmail.com', 'class': 'form-control'}
    )
    
    message = TextAreaField(
        'Message',
        validators=[
            DataRequired(message='Message is required'),
            Length(min=10, max=1000, message='Message must be between 10 and 1000 characters')
        ],
        render_kw={
            'placeholder': 'Write a message',
            'class': 'form-control',
            'rows': 7
        }
    )
    
    submit = SubmitField(
        'Send inquiry',
        render_kw={'class': 'btn btn-primary'}
    )