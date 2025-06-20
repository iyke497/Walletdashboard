from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user, login_required
from app.extensions import login_manager


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


def basic_access_required(f):
    """Decorator for basic features (login required but email verification optional)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        
        return f(*args, **kwargs)
    return decorated_function

def verified_and_admin_required(f):
    """Decorator to require both email verification and admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        
        if not current_user.email_verified:
            flash('Please verify your email address to access this feature.', 'warning')
            return redirect(url_for('auth.verify_email_notice', email=current_user.email))
        
        if not current_user.is_admin:
            flash('Admin privileges required to access this feature.', 'error')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Simple admin check - modify based on your user model"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        
        # Simple check - adjust based on your user model
        # Option 1: Check if user has admin role
        # if hasattr(current_user, 'role') and current_user.role != 'admin':
        #     abort(403)
        
        # Option 2: Check if user is_admin field
        # if not getattr(current_user, 'is_admin', False):
        #     abort(403)
        
        # Option 3: Check specific user IDs
        if current_user.id not in [1, 24, 28]:  # Your admin user IDs
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function