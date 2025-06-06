from flask import current_app, url_for, render_template_string
from flask_mail import Mail, Message
from app.extensions import mail

import logging


class EmailService:
    
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
            
            # Create message
            msg = Message(
                subject='Verify Your Email Address',
                sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
                recipients=[user.email]
            )
            msg.html = html_body
            
            # Send email
            mail.send(msg)
            
            current_app.logger.info(f'Verification email sent to {user.email}')
            return True
            
        except Exception as e:
            current_app.logger.error(f'Failed to send verification email to {user.email}: {str(e)}')
            return False
        
    @staticmethod
    def send_welcome_email(user):
        """Send welcome email after successful verification"""

        if mail is None:
            current_app.logger.error("EmailService not initialized with mail instance")
            return False

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
            
            msg = Message(
                subject='Welcome! Email Verified Successfully',
                sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
                recipients=[user.email]
            )
            msg.html = html_body
            
            mail.send(msg)
            current_app.logger.info(f'Welcome email sent to {user.email}')
            return True
            
        except Exception as e:
            current_app.logger.error(f'Failed to send welcome email to {user.email}: {str(e)}')
            return False