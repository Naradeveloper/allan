import os
import secrets
import requests
import base64
import json
import hmac
import hashlib
from cryptography.fernet import Fernet
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from flask_migrate import Migrate
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, SelectField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Length, NumberRange, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
from PIL import Image
import io
from dotenv import load_dotenv

load_dotenv()

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()

# Configuration
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///herbs_store.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Email Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', 'mugambiallan@gmail.com')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', 'amunene188,')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'mugambiallan@gmail.com')
    
    # File Upload
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'static/uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16777216))
    
    # M-Pesa Configuration
    MPESA_CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY', 'O9B4B4x4Ank2GjzlyAx1lIggvzq36HmkdLjhTlZ458TPGoFT')
    MPESA_CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET','AmTA9Cv6OaKTOAWbYdLFLPev9gYl3IwAtTnSpU4hlCSBA9GNL9q1KOhnwLQfWJ5a ')
    MPESA_SHORTCODE = os.getenv('MPESA_SHORTCODE', '174379')
    MPESA_PASSKEY = os.getenv('MPESA_PASSKEY', 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919')
    MPESA_CALLBACK_URL = os.getenv('MPESA_CALLBACK_URL', 'https://your-ngrok-url.ngrok.io/mpesa-callback')
    MPESA_ENVIRONMENT = os.getenv('MPESA_ENVIRONMENT', 'sandbox')
    
    # Product Categories
    CATEGORIES = [
        'Herbal Roots', 'Powdered Spices', 'Dried Herbs', 'Seeds', 'Spices', 'Flowers'
    ]

# Create app
app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'products'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'users'), exist_ok=True)

# Initialize extensions with app
db.init_app(app)
login_manager.init_app(app)
mail.init_app(app)
migrate.init_app(app, db)

login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Serializer for tokens
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# M-Pesa Service Class
class MpesaService:
    def __init__(self):
        self.consumer_key = app.config['MPESA_CONSUMER_KEY']
        self.consumer_secret = app.config['MPESA_CONSUMER_SECRET']
        self.business_shortcode = app.config['MPESA_SHORTCODE']
        self.passkey = app.config['MPESA_PASSKEY']
        self.environment = app.config['MPESA_ENVIRONMENT']
        
        if self.environment == 'production':
            self.base_url = 'https://api.safaricom.co.ke'
        else:
            self.base_url = 'https://sandbox.safaricom.co.ke'
    
    def get_access_token(self):
        """Get M-Pesa access token"""
        try:
            url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
            auth_string = f"{self.consumer_key}:{self.consumer_secret}"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_auth}'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data.get('access_token')
        except Exception as e:
            app.logger.error(f"Error getting access token: {str(e)}")
            return None
    
    def generate_password(self):
        """Generate Lipa Na M-Pesa Online password"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        data_to_encode = f"{self.business_shortcode}{self.passkey}{timestamp}"
        encoded_string = base64.b64encode(data_to_encode.encode()).decode()
        return encoded_string, timestamp
    
    def stk_push(self, phone_number, amount, account_reference, description):
        """Initiate STK Push request"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {'error': 'Failed to get access token'}, 500
            
            password, timestamp = self.generate_password()
            
            # FIXED: Better phone number formatting
            # Remove any non-digit characters first
            phone_number = ''.join(filter(str.isdigit, phone_number))
            
            # Format phone number for M-Pesa
            if phone_number.startswith('0'):
                phone_number = '254' + phone_number[1:]
            elif phone_number.startswith('+254'):
                phone_number = phone_number[1:]  # Remove the +
            elif phone_number.startswith('254'):
                phone_number = phone_number  # Already correct
            elif len(phone_number) == 9:
                phone_number = '254' + phone_number  # 712345678 -> 254712345678
            else:
                return {'success': False, 'error': 'Invalid phone number format'}, 400
            
            # Validate phone number length
            if len(phone_number) != 12 or not phone_number.startswith('254'):
                return {'success': False, 'error': 'Phone number must be 12 digits starting with 254'}, 400
            
            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": phone_number,
                "PartyB": self.business_shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": app.config['MPESA_CALLBACK_URL'],
                "AccountReference": account_reference,
                "TransactionDesc": description
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response_data = response.json()
            
            app.logger.info(f"M-Pesa STK Push Response: {response_data}")
            
            if response.status_code == 200:
                if 'ResponseCode' in response_data and response_data['ResponseCode'] == '0':
                    return {
                        'success': True,
                        'checkout_request_id': response_data.get('CheckoutRequestID'),
                        'customer_message': response_data.get('CustomerMessage'),
                        'merchant_request_id': response_data.get('MerchantRequestID'),
                        'response_code': response_data.get('ResponseCode')
                    }, 200
                else:
                    error_msg = response_data.get('CustomerMessage', 'Payment request failed')
                    if 'Invalid PhoneNumber' in error_msg:
                        error_msg = 'Invalid phone number format. Please use format: 0712345678 or 254712345678'
                    return {
                        'success': False,
                        'error': error_msg,
                        'response_code': response_data.get('ResponseCode')
                    }, 400
            else:
                error_msg = response_data.get('errorMessage', 'Payment request failed')
                return {
                    'success': False,
                    'error': error_msg
                }, response.status_code
                
        except Exception as e:
            app.logger.error(f"Error in STK Push: {str(e)}")
            return {'success': False, 'error': 'An unexpected error occurred'}, 500

# Create global instance
mpesa_service = MpesaService()

# Forms
class RegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    is_seller = BooleanField('I want to sell products')
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[DataRequired()])
    price = DecimalField('Price (KSh)', validators=[DataRequired(), NumberRange(min=0)])
    category = SelectField('Category', choices=[], validators=[DataRequired()])
    stock = IntegerField('Stock Quantity', validators=[DataRequired(), NumberRange(min=0)])
    image = FileField('Product Image', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')])
    submit = SubmitField('List Product')
    
    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        self.category.choices = [(cat, cat) for cat in Config.CATEGORIES]

class CheckoutForm(FlaskForm):
    phone_number = StringField('M-Pesa Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    shipping_address = TextAreaField('Shipping Address', validators=[DataRequired()])
    notes = TextAreaField('Order Notes (Optional)')
    submit = SubmitField('Complete Order')

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    verified = db.Column(db.Boolean, default=False)
    is_seller = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(255), default='default-product.jpg')
    stock = db.Column(db.Integer, default=0)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    featured = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    seller = db.relationship('User', backref=db.backref('products', lazy=True))

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('cart_items', lazy=True))
    product = db.relationship('Product', backref=db.backref('in_carts', lazy=True))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending')
    payment_status = db.Column(db.String(50), default='pending')
    phone_number = db.Column(db.String(20), nullable=False)
    shipping_address = db.Column(db.Text)
    notes = db.Column(db.Text)
    order_items = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('orders', lazy=True))

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    
    order = db.relationship('Order', backref=db.backref('items', lazy=True))
    product = db.relationship('Product', backref=db.backref('order_items', lazy=True))

class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref=db.backref('password_resets', lazy=True))

class MpesaPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    merchant_request_id = db.Column(db.String(100))
    checkout_request_id = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    amount = db.Column(db.Float)
    receipt_number = db.Column(db.String(50))
    transaction_date = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='pending')
    result_code = db.Column(db.Integer)
    result_desc = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    order = db.relationship('Order', backref=db.backref('mpesa_payments', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Utility Functions
def save_image(image_file, folder='products'):
    """Save uploaded image and return filename"""
    if image_file and image_file.filename:
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(image_file.filename)
        filename = random_hex + f_ext.lower()
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], folder, filename)
        
        try:
            output_size = (800, 800)
            i = Image.open(image_file)
            i.thumbnail(output_size, Image.Resampling.LANCZOS)
            
            if i.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', i.size, (255, 255, 255))
                background.paste(i, mask=i.split()[-1])
                i = background
            
            i.save(filepath, 'JPEG' if f_ext.lower() in ['.jpg', '.jpeg'] else 'PNG')
            return filename
        except Exception as e:
            print(f"Error saving image: {e}")
            return None
    return 'default-product.jpg'

def get_product_image(product_name):
    """Helper function to get product image path based on product name"""
    image_mapping = {
        'Turmeric Powder': 'images/Turmeric-Powder.jpg',
        'Ashwagandha Root': 'images/Ashwagandha-Root.jpg',
        'Ginger Powder': 'images/Ginger-Powder.jpg',
        'Dried Mint Leaves': 'images/Dried-Mint-Leaves.jpg',
        'Moringa Powder': 'images/Moringa-Powder.jpg',
        'Cinnamon Sticks': 'images/Cinnamon-Sticks.jpg',
        'Holy Basil (Tulsi)': 'images/Holy-Basil.jpg',
        'Licorice Root': 'images/Licorice-Root.jpg',
        'Fenugreek Seeds': 'images/Fenugreek-Seeds.jpg',
        'Cloves': 'images/Cloves.jpg',
        'Cardamom Pods': 'images/Cardamom-Pods.jpg',
        'Echinacea Root': 'images/Echinacea-Root.jpg',
        'Dandelion Root': 'images/Dandelion-Root.jpg',
        'Burdock Root': 'images/Burdock-Root.jpg',
        'Chamomile Flowers': 'images/Chamomile-Flowers.jpg',
        'Peppermint Leaves': 'images/Peppermint-Leaves.jpg',
        'Nettle Leaves': 'images/Nettle-Leaves.jpg',
        'Sage Leaves': 'images/Sage-Leaves.jpg',
        'Thyme Leaves': 'images/Thyme-Leaves.jpg',
    }
    
    image_file = image_mapping.get(product_name, 'images/placeholder.jpg')
    return url_for('static', filename=image_file)

# M-Pesa Utility Functions
def get_mpesa_access_token():
    """Get M-Pesa OAuth access token"""
    consumer_key = app.config['MPESA_CONSUMER_KEY']
    consumer_secret = app.config['MPESA_CONSUMER_SECRET']
    
    if app.config['MPESA_ENVIRONMENT'] == 'sandbox':
        url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    else:
        url = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    
    try:
        response = requests.get(
            url,
            auth=(consumer_key, consumer_secret),
            timeout=30
        )
        response.raise_for_status()
        return response.json()['access_token']
    except Exception as e:
        print(f"Error getting M-Pesa access token: {e}")
        return None

def generate_mpesa_password():
    """Generate M-Pesa API password"""
    shortcode = app.config['MPESA_SHORTCODE']
    passkey = app.config['MPESA_PASSKEY']
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    data = f"{shortcode}{passkey}{timestamp}"
    password = base64.b64encode(data.encode()).decode()
    return password, timestamp

def initiate_stk_push(phone_number, amount, order_id, description):
    """Initiate M-Pesa STK Push payment"""
    print(f"🚀 INITIATING STK PUSH...")
    
    # Debug the request first
    print(f"🔍 DEBUG: Phone: {phone_number}, Amount: {amount}, Order: {order_id}")
    
    # FIXED: Phone number formatting
    original_phone = phone_number
    phone_number = ''.join(filter(str.isdigit, phone_number))
    
    if phone_number.startswith('0') and len(phone_number) == 10:
        phone_number = '254' + phone_number[1:]
    elif len(phone_number) == 9:
        phone_number = '254' + phone_number
    elif phone_number.startswith('254') and len(phone_number) == 12:
        phone_number = phone_number
    else:
        return None, f"Invalid phone number format: {original_phone} -> {phone_number}"
    
    print(f"🔍 DEBUG: Formatted Phone: {phone_number}")
    
    access_token = get_mpesa_access_token()
    if not access_token:
        print("❌ Failed to get access token")
        return None, "Failed to get access token"
    
    print(f"✅ Access token obtained")
    
    password, timestamp = generate_mpesa_password()
    
    if app.config['MPESA_ENVIRONMENT'] == 'sandbox':
        url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
    else:
        url = 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
    
    payload = {
        "BusinessShortCode": app.config['MPESA_SHORTCODE'],
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone_number,
        "PartyB": app.config['MPESA_SHORTCODE'],
        "PhoneNumber": phone_number,
        "CallBackURL": app.config['MPESA_CALLBACK_URL'],
        "AccountReference": f"ORDER{order_id}",
        "TransactionDesc": description
    }
    
    print(f"📦 Payload: {json.dumps(payload)}")
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        print(f"🌐 Sending request to M-Pesa...")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response_data = response.json()
        
        print(f"📡 Response: {json.dumps(response_data)}")
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            if 'ResponseCode' in response_data and response_data['ResponseCode'] == '0':
                print("✅ STK Push initiated successfully!")
                payment = MpesaPayment(
                    order_id=order_id,
                    merchant_request_id=response_data.get('MerchantRequestID'),
                    checkout_request_id=response_data.get('CheckoutRequestID'),
                    phone_number=phone_number,
                    amount=amount,
                    status='pending'
                )
                db.session.add(payment)
                db.session.commit()
                return response_data, None
            else:
                error_msg = response_data.get('CustomerMessage', 'Payment request failed')
                print(f"❌ STK Push failed: {error_msg}")
                return None, error_msg
        else:
            error_msg = response_data.get('errorMessage', 'Unknown error')
            print(f"❌ HTTP Error: {error_msg}")
            return None, error_msg
            
    except Exception as e:
        print(f"💥 Exception: {str(e)}")
        return None, str(e)

def send_verification_email(user_email, token):
    """Send email verification link"""
    verify_url = url_for('verify_email', token=token, _external=True)
    
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
        return True
    except Exception as e:
        print(f"Failed to send verification email: {e}")
        return False

def send_order_confirmation(order, user_email):
    """Send order confirmation email"""
    order_items = json.loads(order.order_items)
    
    items_html = ""
    for item in order_items:
        items_html += f"""
        <tr>
            <td>{item['product_name']}</td>
            <td>{item['quantity']}</td>
            <td>KSh {item['price']:.2f}</td>
            <td>KSh {item['quantity'] * item['price']:.2f}</td>
        </tr>
        """
    
    msg = Message(
        subject=f"Order Confirmation - #{order.id}",
        recipients=[user_email],
        html=f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #4CAF50;">Order Confirmed!</h2>
            <p>Thank you for your order. Here are your order details:</p>
            
            <div style="background: #f9f9f9; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Order #{order.id}</h3>
                <p><strong>Total Amount:</strong> KSh {order.total_amount:.2f}</p>
                <p><strong>Status:</strong> {order.status.title()}</p>
                <p><strong>Order Date:</strong> {order.created_at.strftime('%Y-%m-%d %H:%M')}</p>
                <p><strong>Shipping Address:</strong><br>{order.shipping_address}</p>
            </div>
            
            <h3>Order Items</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: #4CAF50; color: white;">
                        <th style="padding: 10px; text-align: left;">Product</th>
                        <th style="padding: 10px; text-align: center;">Qty</th>
                        <th style="padding: 10px; text-align: right;">Price</th>
                        <th style="padding: 10px; text-align: right;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html}
                </tbody>
                <tfoot>
                    <tr style="border-top: 2px solid #4CAF50;">
                        <td colspan="3" style="padding: 10px; text-align: right; font-weight: bold;">Total:</td>
                        <td style="padding: 10px; text-align: right; font-weight: bold;">KSh {order.total_amount:.2f}</td>
                    </tr>
                </tfoot>
            </table>
            
            <p>We'll notify you when your order ships.</p>
            <p>Thank you for choosing Herbs & Spices Store!</p>
        </div>
        """
    )
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Failed to send order confirmation: {e}")
        return False

# Make the function available to templates
app.jinja_env.globals['get_product_image'] = get_product_image

# Routes
@app.route('/')
def index():
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')
    
    query = Product.query.filter_by(active=True)
    
    if category != 'all':
        query = query.filter_by(category=category)
    
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))
    
    products = query.order_by(Product.created_at.desc()).all()
    featured_products = Product.query.filter_by(featured=True, active=True).limit(8).all()
    
    print(f"DEBUG: Loading {len(products)} products from database")
    for product in products:
        print(f"  - {product.name} (Active: {product.active})")
    
    return render_template('index.html', 
                         products=products,
                         categories=Config.CATEGORIES,
                         selected_category=category,
                         search_query=search,
                         featured_products=featured_products)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered. Please login.', 'danger')
            return redirect(url_for('login'))
        
        user = User(
            email=form.email.data,
            password=generate_password_hash(form.password.data),
            name=form.name.data,
            phone=form.phone.data,
            is_seller=form.is_seller.data
        )
        
        db.session.add(user)
        db.session.commit()
        
        token = s.dumps(user.email, salt='email-verify')
        if send_verification_email(user.email, token):
            flash('Registration successful! Please check your email to verify your account.', 'success')
        else:
            flash('Registration successful! But we could not send verification email. Please contact support.', 'warning')
        
        return redirect(url_for('login'))
    
    return render_template('auth/register.html', form=form)

@app.route('/verify-email/<token>')
def verify_email(token):
    try:
        email = s.loads(token, salt='email-verify', max_age=3600)
    except:
        flash('Invalid or expired verification link.', 'danger')
        return redirect(url_for('register'))
    
    user = User.query.filter_by(email=email).first()
    if user and not user.verified:
        user.verified = True
        db.session.commit()
        flash('Email verified successfully! You can now login.', 'success')
    else:
        flash('Email already verified or user not found.', 'info')
    
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and check_password_hash(user.password, form.password.data):
            if not user.verified:
                flash('Please verify your email before logging in.', 'warning')
                return redirect(url_for('login'))
            
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login failed. Please check your email and password.', 'danger')
    
    return render_template('auth/login.html', form=form)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = s.dumps(user.email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            
            try:
                msg = Message(
                    'Password Reset Request - Herbs & Spices Store',
                    recipients=[user.email],
                    html=f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #4CAF50;">Password Reset Request</h2>
                        <p>You requested to reset your password. Click the button below to create a new password:</p>
                        <a href="{reset_url}" style="background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                            Reset Password
                        </a>
                        <p style="margin-top: 20px; color: #666;">
                            If the button doesn't work, copy and paste this link in your browser:<br>
                            {reset_url}
                        </p>
                        <p>This link will expire in 1 hour.</p>
                        <p>If you didn't request this reset, please ignore this email.</p>
                    </div>
                    """
                )
                mail.send(msg)
                flash('Password reset instructions have been sent to your email.', 'info')
            except Exception as e:
                flash('Error sending email. Please try again later.', 'danger')
                print(f"Email error: {e}")
        else:
            flash('If that email exists in our system, reset instructions will be sent.', 'info')
        
        return redirect(url_for('login'))
    
    return render_template('auth/forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('Invalid or expired reset link. Please request a new one.', 'danger')
        return redirect(url_for('forgot_password'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Invalid reset link.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or not confirm_password:
            flash('Please fill in all fields.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        user.password = generate_password_hash(password)
        db.session.commit()
        
        flash('Your password has been reset successfully! You can now login with your new password.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/reset_password.html', token=token)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/products/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.active:
        flash('Product not available.', 'danger')
        return redirect(url_for('index'))
    
    related_products = Product.query.filter(
        Product.category == product.category,
        Product.id != product.id,
        Product.active == True
    ).limit(4).all()
    
    return render_template('products/detail.html', 
                         product=product, 
                         related_products=related_products)

@app.route('/add-to-cart/<int:product_id>')
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    
    if not product.active:
        flash('Product is not available.', 'danger')
        return redirect(request.referrer or url_for('index'))
    
    cart_item = Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    
    if cart_item:
        if cart_item.quantity < product.stock:
            cart_item.quantity += 1
            flash(f'Added another {product.name} to cart!', 'success')
        else:
            flash(f'Cannot add more {product.name}. Only {product.stock} left in stock.', 'warning')
    else:
        cart_item = Cart(user_id=current_user.id, product_id=product_id, quantity=1)
        db.session.add(cart_item)
        flash(f'{product.name} added to cart!', 'success')
    
    db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/cart')
@login_required
def cart():
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    
    for item in cart_items:
        if item.quantity > item.product.stock:
            if item.product.stock == 0:
                db.session.delete(item)
                flash(f'{item.product.name} is out of stock and has been removed from your cart.', 'warning')
            else:
                item.quantity = item.product.stock
                flash(f'Updated {item.product.name} quantity to available stock ({item.product.stock}).', 'warning')
    
    db.session.commit()
    
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/update-cart/<int:cart_id>', methods=['POST'])
@login_required
def update_cart(cart_id):
    cart_item = Cart.query.get_or_404(cart_id)
    
    if cart_item.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    quantity = int(request.form.get('quantity', 1))
    
    if quantity <= 0:
        db.session.delete(cart_item)
        message = 'Item removed from cart.'
    elif quantity <= cart_item.product.stock:
        cart_item.quantity = quantity
        message = 'Cart updated successfully.'
    else:
        return jsonify({'success': False, 'message': f'Only {cart_item.product.stock} available.'})
    
    db.session.commit()
    
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    item_total = cart_item.product.price * cart_item.quantity if quantity > 0 else 0
    
    return jsonify({
        'success': True,
        'message': message,
        'item_total': item_total,
        'cart_total': total,
        'cart_count': len(cart_items)
    })

# ADDED: Remove from cart function
@app.route('/remove-from-cart/<int:cart_id>')
@login_required
def remove_from_cart(cart_id):
    cart_item = Cart.query.get_or_404(cart_id)
    
    if cart_item.user_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('cart'))
    
    product_name = cart_item.product.name
    db.session.delete(cart_item)
    db.session.commit()
    flash(f'{product_name} removed from cart.', 'success')
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    
    if not cart_items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('cart'))
    
    for item in cart_items:
        if item.quantity > item.product.stock:
            flash(f'Only {item.product.stock} {item.product.name} available. Please update your cart.', 'danger')
            return redirect(url_for('cart'))
    
    total = sum(item.product.price * item.quantity for item in cart_items)
    form = CheckoutForm()
    
    if form.validate_on_submit():
        order_items = []
        for item in cart_items:
            order_items.append({
                'product_id': item.product_id,
                'product_name': item.product.name,
                'quantity': item.quantity,
                'price': float(item.product.price)
            })
        
        order = Order(
            user_id=current_user.id,
            total_amount=total,
            phone_number=form.phone_number.data,
            shipping_address=form.shipping_address.data,
            notes=form.notes.data,
            order_items=json.dumps(order_items),
            payment_status='pending'
        )
        
        db.session.add(order)
        db.session.flush()
        
        description = f"Herbs & Spices Order #{order.id}"
        mpesa_response, error = initiate_stk_push(
            phone_number=form.phone_number.data,
            amount=total,
            order_id=order.id,
            description=description
        )
        
        if mpesa_response and mpesa_response.get('ResponseCode') == '0':
            for item in cart_items:
                product = Product.query.get(item.product_id)
                product.stock -= item.quantity
                
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    price=item.product.price
                )
                db.session.add(order_item)
            
            Cart.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()
            
            flash('M-Pesa payment request sent to your phone. Please complete the payment to confirm your order.', 'info')
            return redirect(url_for('payment_pending', order_id=order.id))
        else:
            db.session.rollback()
            error_msg = error or 'Failed to initiate M-Pesa payment. Please try again.'
            flash(f'Payment Error: {error_msg}', 'danger')
            return render_template('checkout.html', form=form, cart_items=cart_items, total=total)
    
    return render_template('checkout.html', form=form, cart_items=cart_items, total=total)

@app.route('/payment-pending/<int:order_id>')
@login_required
def payment_pending(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    
    return render_template('payment_pending.html', order=order)

@app.route('/mpesa-callback', methods=['POST'])
def mpesa_callback():
    """Handle M-Pesa payment callback"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'ResultCode': 1, 'ResultDesc': 'Invalid data'})
        
        callback_metadata = data.get('Body', {}).get('stkCallback', {})
        checkout_request_id = callback_metadata.get('CheckoutRequestID')
        result_code = callback_metadata.get('ResultCode')
        result_desc = callback_metadata.get('ResultDesc')
        
        payment = MpesaPayment.query.filter_by(checkout_request_id=checkout_request_id).first()
        if not payment:
            return jsonify({'ResultCode': 1, 'ResultDesc': 'Payment not found'})
        
        payment.result_code = result_code
        payment.result_desc = result_desc
        
        if result_code == 0:
            payment.status = 'completed'
            payment.transaction_date = datetime.utcnow()
            
            callback_items = callback_metadata.get('CallbackMetadata', {}).get('Item', [])
            for item in callback_items:
                if item.get('Name') == 'MpesaReceiptNumber':
                    payment.receipt_number = item.get('Value')
                elif item.get('Name') == 'TransactionDate':
                    trans_date = str(item.get('Value'))
                    if trans_date:
                        payment.transaction_date = datetime.strptime(trans_date, '%Y%m%d%H%M%S')
            
            order = payment.order
            order.payment_status = 'paid'
            order.status = 'processing'
            
            send_order_confirmation(order, order.user.email)
            
        else:
            payment.status = 'failed'
            order = payment.order
            order.payment_status = 'failed'
        
        db.session.commit()
        
        return jsonify({'ResultCode': 0, 'ResultDesc': 'Success'})
        
    except Exception as e:
        print(f"Error processing M-Pesa callback: {e}")
        return jsonify({'ResultCode': 1, 'ResultDesc': 'Error processing callback'})

@app.route('/check-payment-status/<int:order_id>')
@login_required
def check_payment_status(order_id):
    """Check payment status via AJAX"""
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    payment = MpesaPayment.query.filter_by(order_id=order_id).order_by(MpesaPayment.created_at.desc()).first()
    
    if not payment:
        return jsonify({'success': False, 'message': 'No payment record found'})
    
    return jsonify({
        'success': True,
        'payment_status': payment.status,
        'order_status': order.status,
        'receipt_number': payment.receipt_number
    })

@app.route('/order-confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id and not current_user.is_admin:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    
    order_items = json.loads(order.order_items)
    return render_template('order_confirmation.html', order=order, order_items=order_items)

@app.route('/orders')
@login_required
def user_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('orders.html', orders=orders)

@app.route('/sell', methods=['GET', 'POST'])
@login_required
def sell():
    if not current_user.is_seller:
        current_user.is_seller = True
        db.session.commit()
        flash('You are now registered as a seller!', 'success')
    
    form = ProductForm()
    
    if form.validate_on_submit():
        image_filename = save_image(form.image.data) if form.image.data else 'default-product.jpg'
        
        product = Product(
            name=form.name.data,
            description=form.description.data,
            price=float(form.price.data),
            category=form.category.data,
            stock=form.stock.data,
            image_url=image_filename,
            seller_id=current_user.id
        )
        
        db.session.add(product)
        db.session.commit()
        
        flash('Product listed successfully!', 'success')
        return redirect(url_for('product_detail', product_id=product.id))
    
    return render_template('products/sell.html', form=form)

@app.route('/my-products')
@login_required
def my_products():
    if not current_user.is_seller:
        flash('You need to be a seller to view products.', 'warning')
        return redirect(url_for('sell'))
    
    products = Product.query.filter_by(seller_id=current_user.id).order_by(Product.created_at.desc()).all()
    return render_template('products/my_products.html', products=products)

@app.route('/edit-product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if product.seller_id != current_user.id and not current_user.is_admin:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    
    form = ProductForm(obj=product)
    
    if form.validate_on_submit():
        product.name = form.name.data
        product.description = form.description.data
        product.price = float(form.price.data)
        product.category = form.category.data
        product.stock = form.stock.data
        
        if form.image.data:
            product.image_url = save_image(form.image.data)
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('product_detail', product_id=product.id))
    
    return render_template('products/edit_product.html', form=form, product=product)

# Admin Routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    
    total_users = User.query.count()
    total_products = Product.query.filter_by(active=True).count()
    total_orders = Order.query.count()
    total_revenue = db.session.query(db.func.sum(Order.total_amount)).filter(Order.payment_status == 'paid').scalar() or 0
    
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    low_stock = Product.query.filter(Product.stock < 10, Product.active == True).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_products=total_products,
                         total_orders=total_orders,
                         total_revenue=total_revenue,
                         recent_orders=recent_orders,
                         recent_users=recent_users,
                         low_stock=low_stock)

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/products')
@login_required
def admin_products():
    if not current_user.is_admin:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('admin/products.html', products=products)

@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/analytics')
@login_required
def admin_analytics():
    if not current_user.is_admin:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    
    total_sales = db.session.query(db.func.sum(Order.total_amount)).filter(Order.payment_status == 'paid').scalar() or 0
    total_orders_count = Order.query.count()
    average_order_value = total_sales / total_orders_count if total_orders_count > 0 else 0
    
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    
    top_products = db.session.query(
        Product.name,
        db.func.sum(OrderItem.quantity).label('total_sold'),
        db.func.sum(OrderItem.quantity * OrderItem.price).label('revenue')
    ).join(OrderItem, OrderItem.product_id == Product.id
    ).join(Order, Order.id == OrderItem.order_id
    ).group_by(Product.id, Product.name
    ).order_by(db.desc('total_sold')).limit(10).all()
    
    return render_template('admin/analytics.html',
                         total_sales=total_sales,
                         total_orders_count=total_orders_count,
                         average_order_value=average_order_value,
                         recent_orders=recent_orders,
                         top_products=top_products)

@app.route('/admin/toggle-product/<int:product_id>')
@login_required
def admin_toggle_product(product_id):
    if not current_user.is_admin:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    
    product = Product.query.get_or_404(product_id)
    product.active = not product.active
    db.session.commit()
    
    status = "activated" if product.active else "deactivated"
    flash(f'Product {product.name} has been {status}.', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/update-order-status/<int:order_id>', methods=['POST'])
@login_required
def admin_update_order_status(order_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    order = Order.query.get_or_404(order_id)
    new_status = request.json.get('status')
    
    if new_status in ['pending', 'processing', 'shipped', 'delivered', 'cancelled']:
        order.status = new_status
        db.session.commit()
        return jsonify({'success': True, 'message': f'Order status updated to {new_status}'})
    
    return jsonify({'success': False, 'message': 'Invalid status'})

# API Routes
@app.route('/api/cart-count')
@login_required
def api_cart_count():
    count = Cart.query.filter_by(user_id=current_user.id).count()
    return jsonify({'count': count})

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ADDED: Missing routes for file handling and testing
@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'images/favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/default-product.jpg')
def default_product_image():
    return send_from_directory('static', 'images/default-product.jpg')

@app.route('/test-payment')
def test_payment_page():
    """Test page for M-Pesa payments"""
    return render_template('test-payment.html')

@app.route('/api/mpesa/payment', methods=['POST'])
def initiate_mpesa_payment():
    """Initiate real M-Pesa payment"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['phone_number', 'amount', 'order_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        phone_number = data['phone_number']
        amount = data['amount']
        order_id = data['order_id']
        description = data.get('description', 'Herbs & Spices Purchase')
        
        # Validate amount
        try:
            amount = float(amount)
            if amount < 1:  # Minimum amount for M-Pesa
                return jsonify({
                    'success': False,
                    'error': 'Amount must be at least KES 1'
                }), 400
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid amount format'
            }), 400
        
        # Initiate real STK Push
        result, status_code = mpesa_service.stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=f"ORDER_{order_id}",
            description=description
        )
        
        return jsonify(result), status_code
        
    except Exception as e:
        app.logger.error(f"Error in M-Pesa payment: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/mpesa/transaction/<checkout_request_id>', methods=['GET'])
def get_transaction_status(checkout_request_id):
    """Check real transaction status"""
    transaction = MpesaPayment.query.filter_by(
        checkout_request_id=checkout_request_id
    ).first()
    
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    return jsonify({
        'success': True,
        'transaction': {
            'id': transaction.id,
            'checkout_request_id': transaction.checkout_request_id,
            'phone_number': transaction.phone_number,
            'amount': transaction.amount,
            'status': transaction.status,
            'mpesa_receipt_number': transaction.receipt_number,
            'transaction_date': transaction.transaction_date.isoformat() if transaction.transaction_date else None,
            'created_at': transaction.created_at.isoformat()
        }
    }), 200

# Dark Mode Route
@app.route('/toggle-dark-mode', methods=['POST'])
def toggle_dark_mode():
    """Toggle dark mode setting"""
    try:
        # Toggle dark mode in session
        session['dark_mode'] = not session.get('dark_mode', False)
        
        # Mark that user has manually set theme preference
        session['theme_set'] = True
        
        return jsonify({
            'success': True,
            'dark_mode': session['dark_mode']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# Initialize database with sample data
def init_db():
    with app.app_context():
        db.create_all()
        
        admin_user = User.query.filter_by(email='admin@herbsstore.com').first()
        if not admin_user:
            admin_user = User(
                email='admin@herbsstore.com',
                password=generate_password_hash('admin123'),
                name='Admin User',
                phone='+254700000000',
                verified=True,
                is_admin=True,
                is_seller=True
            )
            db.session.add(admin_user)
            db.session.commit()
        
        # Only add sample products if none exist
        if Product.query.count() == 0:
            sample_products = [
                {
                    'name': 'Ashwagandha Root', 'category': 'Herbal Roots', 'price': 450,
                    'description': 'Pure organic ashwagandha root known for reducing stress and anxiety. Sourced directly from certified organic farms. Known as Indian ginseng, it helps improve brain function, lower blood sugar levels, and reduce cortisol.',
                    'stock': 50, 'featured': True, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Turmeric Powder', 'category': 'Powdered Spices', 'price': 320,
                    'description': 'High-curcumin turmeric powder perfect for cooking and wellness. Anti-inflammatory properties. Contains curcuminoids that fight inflammation and boost antioxidant capacity in the body.',
                    'stock': 45, 'featured': True, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Dried Mint Leaves', 'category': 'Dried Herbs', 'price': 150,
                    'description': 'Organic dried mint leaves ideal for tea and cooking. Aids digestion and freshens breath. Rich in antioxidants and can help relieve indigestion and irritable bowel syndrome.',
                    'stock': 72, 'featured': False, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Cinnamon Sticks', 'category': 'Herbal Roots', 'price': 280,
                    'description': 'Premium Ceylon cinnamon sticks for cooking and tea. Natural blood sugar regulator. Contains powerful antioxidants and has anti-inflammatory properties.',
                    'stock': 35, 'featured': True, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Ginger Powder', 'category': 'Powdered Spices', 'price': 220,
                    'description': 'Organic ginger powder perfect for cooking, tea, and wellness. Aids digestion and reduces inflammation. Contains gingerol which has powerful medicinal properties.',
                    'stock': 60, 'featured': False, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Moringa Powder', 'category': 'Powdered Spices', 'price': 380,
                    'description': 'Nutrient-rich moringa powder from dried leaves. Packed with vitamins, minerals, and antioxidants. Supports brain health, bone health, and contains anti-inflammatory compounds.',
                    'stock': 40, 'featured': True, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Holy Basil (Tulsi)', 'category': 'Dried Herbs', 'price': 270,
                    'description': 'Sacred basil leaves known for adaptogenic properties. Reduces stress and supports immune function. Rich in antioxidants and helps combat infections.',
                    'stock': 55, 'featured': False, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Licorice Root', 'category': 'Herbal Roots', 'price': 310,
                    'description': 'Sweet-tasting licorice root for digestive health. Soothes stomach issues and supports adrenal function. Contains glycyrrhizin which has various health benefits.',
                    'stock': 30, 'featured': False, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Fenugreek Seeds', 'category': 'Seeds', 'price': 180,
                    'description': 'Aromatic fenugreek seeds for cooking and wellness. Supports milk production in nursing mothers and helps control blood sugar levels. Rich in fiber and various minerals.',
                    'stock': 65, 'featured': False, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Cloves', 'category': 'Spices', 'price': 240,
                    'description': 'Whole cloves with strong aromatic flavor. Rich in antioxidants and has antimicrobial properties. Helps improve liver health and regulate blood sugar.',
                    'stock': 48, 'featured': False, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Cardamom Pods', 'category': 'Spices', 'price': 420,
                    'description': 'Green cardamom pods with exquisite aroma. Aids digestion and contains antioxidants. May help lower blood pressure and improve breathing.',
                    'stock': 32, 'featured': True, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Echinacea Root', 'category': 'Herbal Roots', 'price': 350,
                    'description': 'Immune-boosting echinacea root. Helps prevent and treat common colds. Contains compounds that may reduce inflammation and fight infections.',
                    'stock': 28, 'featured': False, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Dandelion Root', 'category': 'Herbal Roots', 'price': 190,
                    'description': 'Detoxifying dandelion root for liver health. Supports digestion and acts as a natural diuretic. Rich in vitamins A, C, and K.',
                    'stock': 42, 'featured': False, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Burdock Root', 'category': 'Herbal Roots', 'price': 230,
                    'description': 'Blood-purifying burdock root. Supports skin health and contains antioxidants. Traditionally used to detoxify blood and clear skin conditions.',
                    'stock': 36, 'featured': False, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Chamomile Flowers', 'category': 'Flowers', 'price': 260,
                    'description': 'Calming chamomile flowers for relaxation tea. Promotes sleep and reduces anxiety. Contains antioxidants that may help with sleep quality and digestion.',
                    'stock': 58, 'featured': True, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Peppermint Leaves', 'category': 'Dried Herbs', 'price': 170,
                    'description': 'Refreshing peppermint leaves for digestive health. Relieves IBS symptoms and headaches. Contains menthol which has a calming effect on the body.',
                    'stock': 63, 'featured': False, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Nettle Leaves', 'category': 'Dried Herbs', 'price': 210,
                    'description': 'Nutrient-dense nettle leaves for allergies. Reduces inflammation and supports prostate health. Rich in vitamins, minerals, and amino acids.',
                    'stock': 39, 'featured': False, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Sage Leaves', 'category': 'Dried Herbs', 'price': 195,
                    'description': 'Aromatic sage leaves for cognitive health. Supports memory and contains antioxidants. Traditionally used to treat sore throat and digestive issues.',
                    'stock': 44, 'featured': False, 'active': True, 'seller_id': admin_user.id
                },
                {
                    'name': 'Thyme Leaves', 'category': 'Dried Herbs', 'price': 175,
                    'description': 'Fragrant thyme leaves with antimicrobial properties. Supports respiratory health and boosts immunity. Contains thymol which has powerful antioxidant properties.',
                    'stock': 51, 'featured': False, 'active': True, 'seller_id': admin_user.id
                }
            ]
            
            for product_data in sample_products:
                product = Product(**product_data)
                db.session.add(product)
            
            db.session.commit()
            print(f"✅ Added {len(sample_products)} products to database!")
            print("📦 ALL 19 products are now active and available!")
        else:
            print("✅ Database already has products, skipping sample data creation.")
        
        print("🔄 Restart your app to see all products on the website!")

if __name__ == '__main__':
    print("🚀 Starting Herbs & Spices Store...")
    init_db()
    print("🌐 Website: http://localhost:5000")
    print("⚙️  Admin Panel: http://localhost:5000/admin/dashboard")
    print("📊 Analytics: http://localhost:5000/admin/analytics")
    print("🔑 Admin Login: admin@herbsstore.com / admin123")
    print("💰 M-Pesa Integration: Enabled")
    print("🌙 Dark Mode: Enabled")
    app.run(debug=True, port=5000)