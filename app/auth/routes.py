from flask import (
    render_template, redirect, url_for, flash, request, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from .services import EmailService
from app.auth.background_tasks import queue_verification_email, queue_welcome_email
from . import auth_bp
from .forms import RegistrationForm, LoginForm
from ..extensions import db, login_manager
from ..models import User
from functools import wraps

@auth_bp.route('/register', methods=['GET','POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data)
        )
        db.session.add(user)
        db.session.commit()

        # Try to send verification email in background (non-blocking)
        try:
            # You can replace this with background task later
            queue_verification_email(user.id)
        except Exception as e:
            current_app.logger.error(f'Failed to send verification email: {str(e)}')
            # Continue anyway - user can still use the app
        
        # Log the user in immediately
        login_user(user)
        
        flash('Welcome! Your account has been created successfully. Please check your email to verify your account for full access to all features.', 'success')
        return redirect(url_for('dashboard.show_portfolio'))
    else:
        if form.username.errors and "already taken" in form.username.errors[0]:
            flash("Username already exists", "account_error")
        if form.email.errors and "already registered" in form.email.errors[0]:
            flash("Email already registered", "account_error")

    return render_template('auth/register.html', form=form)

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # allow login by email or username
        user = User.query.filter(
            (User.email == form.email_or_username.data) |
            (User.username == form.email_or_username.data)
        ).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            
            # Show appropriate message based on verification status
            if not user.email_verified:
                flash('Welcome back! Please verify your email for full access to all features.', 'info')
            else:
                flash('Welcome back!', 'success')
            
            next_page = request.args.get('next') or url_for('dashboard.show_portfolio')
            return redirect(next_page)
        flash('Invalid credentials.', 'danger')
    return render_template('auth/login.html', form=form)

@auth_bp.route('/verify-email-notice')
def verify_email_notice():
    """Show email verification notice page"""
    email = request.args.get('email', '')
    return render_template('auth/verify-email.html', email=email)

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """Verify user's email with token"""
    user = User.query.filter_by(email_verification_token=token).first()
    
    if not user:
        flash('Invalid or expired verification link.', 'danger')
        return redirect(url_for('auth.login'))
    
    if user.email_verified:
        flash('Email already verified. You now have full access!', 'info')
        return redirect(url_for('dashboard.show_portfolio'))
    
    if not user.is_verification_token_valid(token):
        flash('Verification link has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.resend_verification', email=user.email))
    
    # Verify the email
    user.verify_email()
    db.session.commit()
    
    # Send welcome email
    try:
        queue_welcome_email(user.id)
    except Exception as e:
        current_app.logger.error(f'Failed to send welcome email: {str(e)}')
    
    flash('🎉 Email verified successfully! You now have full access to all features.', 'success')
    
    # If user is logged in, redirect to dashboard, otherwise to login
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.show_portfolio'))
    else:
        return redirect(url_for('auth.login'))

@auth_bp.route('/resend-verification')
def resend_verification():
    """Resend verification email"""

    email = request.args.get('email')
    # If no email provided, try to use current user's email
    if not email and current_user.is_authenticated:
        email = current_user.email
    
    if not email:
        flash('Email address is required.', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('No account found with that email address.', 'danger')
        return redirect(url_for('auth.login'))
    
    if user.email_verified:
        flash('Email is already verified.', 'info')
        return redirect(url_for('dashboard.show_portfolio'))
    
    try:
        EmailService.send_verification_email(user)
        db.session.commit()
        flash('Verification email sent! Please check your inbox.', 'success')
    except Exception as e:
        current_app.logger.error(f'Failed to send verification email: {str(e)}')
        flash('Failed to send verification email. Please try again later.', 'danger')
    
    return redirect(url_for('auth.verify_email_notice', email=email))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You\'ve been logged out.', 'info')
    return redirect(url_for('auth.login'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Decorator for features that require email verification
def email_verified_required(f):
    """Decorator to require email verification for specific features"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        
        if not current_user.email_verified:
            flash('Please verify your email address to access this feature.', 'warning')
            return redirect(url_for('auth.verify_email_notice', email=current_user.email))
        
        return f(*args, **kwargs)
    return decorated_function

# Decorator for basic features (login required but email verification optional)
def basic_access_required(f):
    """Decorator for features available to unverified users"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        return f(*args, **kwargs)
    return decorated_function