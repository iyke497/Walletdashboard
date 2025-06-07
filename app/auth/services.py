from flask import current_app, url_for, render_template_string
from flask_mail import Mail, Message
from app.extensions import mail

import logging


class EmailService:
    
    @staticmethod
    def send_email(recipient_email, subject, html_body, sender=None):
        """Generic method to send any email"""
        try:
            if mail is None:
                current_app.logger.error("EmailService: mail instance not initialized")
                return False
            
            # Use provided sender or default from config
            sender_email = sender or current_app.config.get('MAIL_DEFAULT_SENDER')
            
            if not sender_email:
                current_app.logger.error("No sender email configured")
                return False
            
            # Create message
            msg = Message(
                subject=subject,
                sender=sender_email,
                recipients=[recipient_email]
            )
            msg.html = html_body
            
            # Send email
            mail.send(msg)
            
            current_app.logger.info(f'Email sent successfully to {recipient_email} with subject: {subject}')
            return True
            
        except Exception as e:
            current_app.logger.error(f'Failed to send email to {recipient_email}: {str(e)}')
            return False
    
    @staticmethod
    def send_verification_email(user):
        """Send verification email to user"""
        try:
            # Generate verification token
            token = user.generate_verification_token()
            
            # Create verification URL
            verification_url = url_for('auth.verify_email', 
                                    token=token, 
                                    _external=True)
            
            # Email template
            email_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Verify Your Email</title>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                    .header { background-color: #f8f9fa; padding: 20px; border-radius: 5px; text-align: center; }
                    .content { padding: 20px 0; }
                    .button { display: inline-block; padding: 12px 24px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; }
                    .footer { font-size: 12px; color: #666; margin-top: 20px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Verify Your Email Address</h1>
                    </div>
                    <div class="content">
                        <p>Hello {{ username }},</p>
                        <p>Thank you for registering! Please verify your email address by clicking the button below:</p>
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{{ verification_url }}" class="button">Verify Email Address</a>
                        </p>
                        <p>Or copy and paste this link into your browser:</p>
                        <p style="word-break: break-all; background-color: #f8f9fa; padding: 10px; border-radius: 3px;">
                            {{ verification_url }}
                        </p>
                        <p>This link will expire in 24 hours.</p>
                    </div>
                    <div class="footer">
                        <p>If you didn't create an account, please ignore this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Render template with user data
            html_body = render_template_string(email_template, 
                                            username=user.username,
                                            verification_url=verification_url)
            
            # Use the generic send_email method
            result = EmailService.send_email(
                recipient_email=user.email,
                subject='Verify Your Email Address',
                html_body=html_body
            )
            
            return result
            
        except Exception as e:
            current_app.logger.error(f'Failed to prepare verification email for {user.email}: {str(e)}')
            return False
        
    @staticmethod
    def send_welcome_email(user):
        """Send welcome email after successful verification"""
        try:
            welcome_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Welcome!</title>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                    .header { background-color: #28a745; color: white; padding: 20px; border-radius: 5px; text-align: center; }
                    .content { padding: 20px 0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Welcome to Our Platform!</h1>
                    </div>
                    <div class="content">
                        <p>Hello {{ username }},</p>
                        <p>Your email has been successfully verified! Welcome to our platform.</p>
                        <p>You can now access all features of your account.</p>
                        <p>Thank you for joining us!</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            html_body = render_template_string(welcome_template, username=user.username)
            
            # Use the generic send_email method
            result = EmailService.send_email(
                recipient_email=user.email,
                subject='Welcome! Email Verified Successfully',
                html_body=html_body
            )
            
            return result
            
        except Exception as e:
            current_app.logger.error(f'Failed to prepare welcome email for {user.email}: {str(e)}')
            return False

    @staticmethod
    def send_password_reset_email(user, reset_url=None):
        """Send password reset email to user"""
        try:
            # If no reset_url provided, generate token and URL
            if reset_url is None:
                token = user.generate_password_reset_token()
                reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            current_app.logger.info(f'Reset URL generated: {reset_url}')
            
            # Email template
            reset_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Reset Your Password</title>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                    .header { background-color: #dc3545; color: white; padding: 20px; border-radius: 5px; text-align: center; }
                    .content { padding: 20px 0; }
                    .button { display: inline-block; padding: 12px 24px; background-color: #dc3545; color: white; text-decoration: none; border-radius: 5px; }
                    .footer { font-size: 12px; color: #666; margin-top: 20px; }
                    .warning { background-color: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 15px; border-radius: 5px; margin: 20px 0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔒 Password Reset Request</h1>
                    </div>
                    <div class="content">
                        <p>Hello {{ username }},</p>
                        <p>You requested to reset your password. Click the button below to set a new password:</p>
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{{ reset_url }}" class="button">Reset Password</a>
                        </p>
                        <div class="warning">
                            <strong>⏰ Important:</strong> This link will expire in 1 hour for security reasons.
                        </div>
                        <p>Or copy and paste this link into your browser:</p>
                        <p style="word-break: break-all; background-color: #f8f9fa; padding: 10px; border-radius: 3px;">
                            {{ reset_url }}
                        </p>
                    </div>
                    <div class="footer">
                        <p><strong>🛡️ Security Note:</strong> If you didn't request this password reset, please ignore this email. Your password will remain unchanged.</p>
                        <p>For security questions, contact our support team.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Render template with user data
            html_body = render_template_string(reset_template, 
                                            username=user.username,
                                            reset_url=reset_url)
            
            # Use the generic send_email method
            result = EmailService.send_email(
                recipient_email=user.email,
                subject='Reset Your Password',
                html_body=html_body
            )
            
            return result
            
        except Exception as e:
            current_app.logger.error(f'Failed to prepare password reset email for {user.email}: {str(e)}')
            return False

    @staticmethod
    def send_password_changed_notification(user):
        """Send notification email when password is successfully changed"""
        try:
            notification_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Password Changed</title>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                    .header { background-color: #28a745; color: white; padding: 20px; border-radius: 5px; text-align: center; }
                    .content { padding: 20px 0; }
                    .security-note { background-color: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; padding: 15px; border-radius: 5px; margin: 20px 0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>✅ Password Successfully Changed</h1>
                    </div>
                    <div class="content">
                        <p>Hello {{ username }},</p>
                        <p>Your password has been successfully changed. You can now log in with your new password.</p>
                        <div class="security-note">
                            <strong>🔐 Security Alert:</strong> If you didn't make this change, please contact our support team immediately.
                        </div>
                        <p>For your security, we recommend:</p>
                        <ul>
                            <li>Using a unique, strong password</li>
                            <li>Not sharing your password with others</li>
                            <li>Logging out from shared devices</li>
                        </ul>
                    </div>
                </div>
            </body>
            </html>
            """
            
            html_body = render_template_string(notification_template, username=user.username)
            
            # Use the generic send_email method
            result = EmailService.send_email(
                recipient_email=user.email,
                subject='Password Successfully Changed',
                html_body=html_body
            )
            
            return result
            
        except Exception as e:
            current_app.logger.error(f'Failed to send password change notification to {user.email}: {str(e)}')
            return False