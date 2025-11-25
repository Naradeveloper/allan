import logging
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from extensions import mail
import os

logging.basicConfig(level=logging.INFO)

# Use a default secret key if environment variable is not set
secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
s = URLSafeTimedSerializer(secret_key)

def generate_token(email):
    return s.dumps(email, salt='email-verify')

def verify_token(token, expiration=3600):
    try:
        return s.loads(token, salt='email-verify', max_age=expiration)
    except (SignatureExpired, BadSignature):
        return False

def generate_password_token(email):
    return s.dumps(email, salt='password-reset')

def verify_password_token(token, expiration=3600):
    try:
        return s.loads(token, salt='password-reset', max_age=expiration)
    except (SignatureExpired, BadSignature):
        return False

def send_verification_email(user_email, token):
    verify_url = f"http://localhost:5000/verify-email?token={token}"
    
    msg = Message(
        subject="Verify Your Email - Herbs & Spices Store",
        recipients=[user_email],
        html=f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #4CAF50;">Welcome to Herbs & Spices Store!</h2>
            <p>Please verify your email by clicking the button below:</p>
            <a href="{verify_url}" style="background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Verify Email Address
            </a>
            <p style="margin-top: 20px; color: #666;">
                If the button doesn't work, copy and paste this link in your browser:<br>
                {verify_url}
            </p>
            <p>This link will expire in 1 hour.</p>
        </div>
        """
    )
    try:
        mail.send(msg)
        logging.info(f"Verification email sent to {user_email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send verification email: {str(e)}")
        return False

def send_password_reset_email(user_email, token):
    reset_url = f"http://localhost:5000/reset-password?token={token}"
    
    msg = Message(
        subject="Password Reset Request - Herbs & Spices Store",
        recipients=[user_email],
        html=f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #4CAF50;">Password Reset Request</h2>
            <p>You requested to reset your password. Click the button below to proceed:</p>
            <a href="{reset_url}" style="background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Reset Password
            </a>
            <p style="margin-top: 20px; color: #666;">
                If you didn't request this, please ignore this email.<br>
                If the button doesn't work, use this link:<br>
                {reset_url}
            </p>
            <p>This link will expire in 1 hour.</p>
        </div>
        """
    )
    try:
        mail.send(msg)
        logging.info(f"Password reset email sent to {user_email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send password reset email: {str(e)}")
        return False