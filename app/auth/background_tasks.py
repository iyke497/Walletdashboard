# app/auth/background_tasks.py (Optional - for true background processing)
# Create this file if you want to move email sending to background threads

import threading
import time
from flask import current_app, url_for
from app.auth.services import EmailService
from app.models import User
from app.extensions import db

def send_email_in_background(app, user_id, email_type='verification', extra_data=None):
    """Send email in background thread"""
    with app.app_context():
        try:
            user = User.query.get(user_id)
            if not user:
                current_app.logger.error(f'User with ID {user_id} not found')
                return
            
            if email_type == 'verification':
                if user.email_verified:
                    current_app.logger.info(f'User {user.email} already verified, skipping email')
                    return
                
                current_app.logger.info(f'Background thread: Sending verification email to {user.email}')
                result = EmailService.send_verification_email(user)
                
                if result:
                    db.session.commit()
                    current_app.logger.info(f'✅ Background verification email sent to {user.email}')
                else:
                    current_app.logger.error(f'❌ Background verification email failed for {user.email}')
                    
            elif email_type == 'welcome':
                current_app.logger.info(f'Background thread: Sending welcome email to {user.email}')
                result = EmailService.send_welcome_email(user)
                
                if result:
                    current_app.logger.info(f'✅ Background welcome email sent to {user.email}')
                else:
                    current_app.logger.error(f'❌ Background welcome email failed for {user.email}')
            
            elif email_type == 'password_reset':
                current_app.logger.info(f'Background thread: Sending password reset email to {user.email}')
                
                # Generate token first
                token = user.generate_password_reset_token()
                db.session.commit()  # Save the token to database first
                
                # Create the reset URL with the actual token
                reset_url = url_for('auth.reset_password', token=token, _external=True)
                
                result = EmailService.send_password_reset_email(user, reset_url)
                
                if result:
                    current_app.logger.info(f'✅ Background password reset email sent to {user.email}')
                else:
                    current_app.logger.error(f'❌ Background password reset email failed for {user.email}')
            
            elif email_type == 'password_changed':
                current_app.logger.info(f'Background thread: Sending password change notification to {user.email}')
                result = EmailService.send_password_changed_notification(user)
                
                if result:
                    current_app.logger.info(f'✅ Background password change notification sent to {user.email}')
                else:
                    current_app.logger.error(f'❌ Background password change notification failed for {user.email}')
                    
        except Exception as e:
            current_app.logger.error(f'Background email thread failed: {str(e)}')

def queue_verification_email(user_id):
    """Queue verification email to be sent in background"""
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=send_email_in_background,
        args=(app, user_id, 'verification'),
        daemon=True
    )
    thread.start()
    current_app.logger.info(f'Queued verification email for user ID {user_id}')

def queue_welcome_email(user_id):
    """Queue welcome email to be sent in background"""
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=send_email_in_background,
        args=(app, user_id, 'welcome'),
        daemon=True
    )
    thread.start()
    current_app.logger.info(f'Queued welcome email for user ID {user_id}')

def queue_password_reset_email(user_id):
    """Queue password reset email to be sent in background"""
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=send_email_in_background,
        args=(app, user_id, 'password_reset'),
        daemon=True
    )
    thread.start()
    current_app.logger.info(f'Queued password reset email for user ID {user_id}')

def queue_password_changed_notification(user_id):
    """Queue password change notification to be sent in background"""
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=send_email_in_background,
        args=(app, user_id, 'password_changed'),
        daemon=True
    )
    thread.start()
    current_app.logger.info(f'Queued password change notification for user ID {user_id}')