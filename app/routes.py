from flask import render_template, request, redirect, url_for, jsonify, flash, current_app, Blueprint
from app import db, cache, bcrypt, mail
from app.models import (
    BinnedCodeDict, 
    UserTicks, 
    ClimberSummary,
    User,
    UserUpload
)
from app.services import DataProcessor
from app.services.pyramid_builder import PyramidBuilder
from app.services.database_service import DatabaseService
from app.services.analytics_service import AnalyticsService
from app.services.climber_summary import ClimberSummaryService, UserInputData
from app.services.ai.api import get_completion, get_climber_context
from app.services.auth.auth_service import generate_reset_token, validate_reset_token
from datetime import date, datetime, timedelta
from functools import wraps
from flask_login import current_user, login_user, logout_user, login_required
import json
from app.services.grade_processor import GradeProcessor
from app.services.pyramid_update_service import PyramidUpdateService
import psutil
import os
from sqlalchemy.sql import text
from flask_mail import Message
from app.forms import LoginForm, RegisterForm
import stripe
from app.services.payment.stripe_handler import (
    handle_checkout_session,
    handle_subscription_update,
    handle_subscription_cancellation,
    handle_payment_failure,
    get_tier_from_subscription
)
import pandas as pd

main_bp = Blueprint('main', __name__)

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        if hasattr(obj, 'value'):  # Handle enum objects
            return obj.value
        return super(CustomJSONEncoder, self).default(obj)

def temp_user_check(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.payment_status == 'temp_account':
            # Add session expiration logic
            if datetime.now() - current_user.created_at > timedelta(hours=24):
                logout_user()
                flash('Temporary session expired', 'warning')
                return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated

# Auth Routes--------------------------------
@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        remember = form.remember_me.data

        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            if user.payment_status == 'active':
                return redirect(next_page or url_for('main.sage_chat'))
            else:
                return redirect(next_page or url_for('main.payment'))
    return render_template('auth/login.html', form=form)

@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.sage_chat'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            with db.session.begin_nested():  # Nested transaction
                profile_url = form.mtn_project_profile_url.data or None
                
                # New check: Prevent using URL belonging to existing non-temp user
                if profile_url:
                    existing_permanent_user = User.query.filter(
                        User.mtn_project_profile_url == profile_url,
                        ~User.username.endswith('_temp')  # Exclude temp users
                    ).first()
                    if existing_permanent_user:
                        flash('This Mountain Project profile is already registered', 'danger')
                        return redirect(url_for('main.login'))

                # Check for existing temp user only if URL is provided
                if profile_url:
                    temp_user = User.query.filter(
                        User.mtn_project_profile_url == profile_url,
                        User.username.endswith('_temp')
                    ).first()
                    if temp_user:
                        db.session.delete(temp_user)
                        db.session.commit()
            
            with db.session.begin_nested():  # Separate transaction
                # Check username uniqueness
                if User.query.filter_by(username=form.username.data).first():
                    flash('Username already taken', 'danger')
                    return redirect(url_for('main.register'))

                # Create new user
                user = User(
                    email=form.email.data,
                    username=form.username.data,
                    mtn_project_profile_url=profile_url,  # Could be None
                    tier='basic',
                    payment_status='unpaid'
                )
                user.set_password(form.password.data)
                db.session.add(user)
                db.session.commit()
            
            login_user(user)

            # Only process profile if URL exists
            if profile_url:
                processor = DataProcessor(db.session)
                processor.process_profile(
                    profile_url=profile_url,
                    user_id=user.id,
                    username=user.username
                )
            
            return redirect(url_for('main.payment'))
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration error: {str(e)}")
            flash('Registration failed. Please try again.', 'danger')
    
    return render_template('auth/register.html', form=form)
        
@main_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@main_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate token
            token = generate_reset_token(user.email)
            
            # Send email
            reset_url = url_for('main.reset_password', token=token, _external=True)
            msg = Message('Password Reset Request',
                        sender='noreply@yourdomain.com',
                        recipients=[user.email])
            msg.body = f'''To reset your password, visit the following link:
    {reset_url}

    This link will expire in 1 hour.
    '''
            mail.send(msg)
            
            flash('Check your email for reset instructions', 'info')
            return redirect(url_for('main.login'))
        
        flash('No account found with that email', 'warning')
        return redirect(url_for('main.reset_password_request'))
    
    return render_template('auth/reset_request.html')

@main_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    # Validate token
    email = validate_reset_token(token)
    if not email:
        flash('Invalid or expired token', 'danger')
        return redirect(url_for('main.reset_password_request'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Invalid user', 'danger')
        return redirect(url_for('main.reset_password_request'))
    
    if request.method == 'POST':
        # Validate passwords match
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords must match', 'danger')
            return redirect(url_for('main.reset_password', token=token))
            
        if len(password) < 8:
            flash('Password must be at least 8 characters', 'danger')
            return redirect(url_for('main.reset_password', token=token))
            
        # Update password
        user.set_password(password)
        db.session.commit()
        
        flash('Password updated successfully', 'success')
        return redirect(url_for('main.login'))
    
    return render_template('auth/reset_password.html', token=token)

# Payment Routes--------------------------------

@main_bp.route('/payment', methods=['GET', 'POST'], endpoint='payment')
@login_required
def payment():
    # Add configuration check
    if not os.getenv('STRIPE_PUBLIC_KEY') or not os.getenv('STRIPE_PRICE_ID_BASIC'):
        current_app.logger.error("Missing Stripe configuration")
        flash('Payment system configuration error', 'danger')
        return redirect(url_for('main.index'))
    
    if current_user.payment_status == 'active':
        return redirect(url_for('main.sage_chat'))

    selected_tier = request.args.get('tier', 'basic')
    
    if request.method == 'POST':
        try:
            price_id = os.getenv(
                'STRIPE_PRICE_ID_PREMIUM' if selected_tier == 'premium' 
                else 'STRIPE_PRICE_ID_BASIC'
            )
            
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{'price': price_id, 'quantity': 1}],
                mode='subscription',
                success_url=url_for('main.payment_success', _external=True),
                cancel_url=url_for('main.payment', _external=True),
                customer_email=current_user.email
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            current_app.logger.error(f"Payment processing error: {str(e)}")
            flash('Payment processing error', 'danger')
            return redirect(url_for('main.payment'))
    
    return render_template('payment/payment.html',
                         selected_tier=selected_tier,
                         stripe_public_key=os.getenv('STRIPE_PUBLIC_KEY'),
                         basic_price=os.getenv('STRIPE_PRICE_ID_BASIC'),
                         premium_price=os.getenv('STRIPE_PRICE_ID_PREMIUM'))

@main_bp.route('/payment/success')
@login_required
def payment_success():
    # Immediately update payment status while waiting for webhook
    if current_user.payment_status in ['unpaid', 'temp_account']:
        current_user.payment_status = 'pending_verification'
        db.session.commit()
    
    return render_template('payment/success.html')

@main_bp.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        current_app.logger.error(f'Webhook error: {str(e)}')
        return jsonify({'error': str(e)}), 400

    # Handle multiple event types
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        if not handle_checkout_session(session):
            current_app.logger.error("Failed to handle checkout session")
            
    # Add grace period for webhook delays        
    elif event['type'] == 'checkout.session.async_payment_succeeded':
        session = event['data']['object']
        handle_checkout_session(session)
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        handle_subscription_update(subscription)
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_subscription_cancellation(subscription)
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        handle_payment_failure(invoice)

    return jsonify({'status': 'success'}), 200

# Landing Page Routes--------------------------------

def extract_username_from_url(url):
    """Improved URL parsing"""
    try:
        # Handle both numeric IDs and vanity URLs
        parts = url.strip('/').split('/')
        if parts[-1].isdigit():
            return "unknown_climber"
        return parts[-1].split('?')[0]  # Remove query params
    except:
        return "unknown_climber"

def generate_temp_email(username):
    """Generates unique temporary email"""
    base_email = f"{username}@temp.sendsage.com"
    counter = 1
    while User.query.filter_by(email=base_email).first():
        base_email = f"{username}{counter}@temp.sendsage.com"
        counter += 1
    return base_email

@main_bp.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        profile_url = request.form.get('profile_url')
        if profile_url:
            return handle_profile_submission(profile_url)
        else:
            flash('Please provide a Mountain Project profile URL', 'danger')
    
    if current_user.is_authenticated:
        return redirect(url_for('main.sage_chat'))
    
    return render_template('index.html', 
                         current_user=current_user,
                         support_count=get_support_count().json['count'])



def handle_profile_submission(profile_url):
    # Modified check: Only look for non-temp users
    existing_permanent_user = User.query.filter(
        User.mtn_project_profile_url == profile_url,
        ~User.username.endswith('_temp')
    ).first()
    if existing_permanent_user:
        flash('Profile already registered. Please login.', 'danger')
        return redirect(url_for('main.login'))

    # Changed logic for existing temp users
    existing_temp = User.query.filter(
        User.mtn_project_profile_url == profile_url,
        User.username.endswith('_temp')
    ).first()

    if existing_temp:
        login_user(existing_temp, remember=False)
        flash('Welcome back! Continuing your session', 'success')
        return redirect(url_for('main.userviz'))

    # Clean and validate URL
    profile_url = profile_url.strip().replace(' ', '%20')
    if 'mountainproject.com/user/' not in profile_url:
        flash('Invalid Mountain Project URL format', 'danger')
        return redirect(url_for('main.index'))

    # Extract username from URL
    username = extract_username_from_url(profile_url)
    if not username or username == 'user':
        flash('Could not extract valid username from URL', 'danger')
        return redirect(url_for('main.index'))

    # Create temporary user
    base_username = username.lower()  # Ensure case insensitivity
    temp_username = f"{base_username}_temp"
    temp_email = generate_temp_email(username)
    temp_user = User(
        username=temp_username,
        email=temp_email,
        mtn_project_profile_url=profile_url,
        tier='basic',
        payment_status='unpaid'
    )
    temp_user.set_password(os.urandom(24).hex())  # Random password
    
    db.session.add(temp_user)
    db.session.commit()

    # Process and save UserTicks FIRST
    processor = DataProcessor(db.session)
    user_ticks_df = processor.process_user_ticks(profile_url, temp_user.id, temp_user.username)
    
    try:
        with db.session.begin():
            DatabaseService._batch_save_dataframe(user_ticks_df, 'user_ticks')
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving user_ticks: {str(e)}")
        flash('An error occurred while saving user ticks. Please try again later.', 'danger')
        return redirect(url_for('main.index'))
    
    # After saving UserTicks
    user_ticks = UserTicks.query.filter_by(user_id=temp_user.id).options(
        db.load_only(UserTicks.id, UserTicks.user_id, UserTicks.route_name, 
                    UserTicks.location, UserTicks.tick_date)
    ).all()

    # Verify IDs exist before pyramid building
    if not user_ticks:
        raise ValueError("No UserTicks found after saving")
    
    print(f"First tick ID: {user_ticks[0].id}")  # Should show actual database ID

    # After fetching UserTicks
    user_ticks_df = pd.DataFrame([{
        'id': t.id,
        'user_id': t.user_id,
        'route_name': t.route_name,
        'location': t.location,
        'tick_date': t.tick_date,
        'route_grade': t.route_grade,
        'binned_code': t.binned_code,
        'discipline': t.discipline,
        'notes': t.notes,
        'send_bool': t.send_bool
    } for t in user_ticks])

    # Explicitly verify columns before pyramid building
    print(f"UserTicks DF columns: {user_ticks_df.columns.tolist()}")

    # Before pyramid building
    required_cols = ['id', 'user_id', 'route_name', 'location']
    if not all(col in user_ticks_df.columns for col in required_cols):
        raise ValueError("UserTicks DataFrame missing critical columns")

    # Now build pyramids with database-fetched ticks
    pyramid_builder = PyramidBuilder()
    sport_pyramid, trad_pyramid, boulder_pyramid = pyramid_builder.build_all_pyramids(
        user_ticks_df,  # Use the database-fetched DF with real IDs
        db.session
    )
    
    # Save pyramids
    DatabaseService.save_calculated_data({
        'sport_pyramid': sport_pyramid,
        'trad_pyramid': trad_pyramid,
        'boulder_pyramid': boulder_pyramid
    })

    login_user(temp_user, remember=False)
    flash('Welcome to Sendsage!', 'success')

    return redirect(url_for('main.userviz'))

@main_bp.route("/api/support-count")
@cache.cached(timeout=3600)  # Cache for one hour (3600 seconds)
def get_support_count():
    return jsonify({"count": db.session.query(User.id).distinct().count()})


# Logbook Connection Routes--------------------------------
@main_bp.route("/logbook-connection", methods=['GET', 'POST'])
def logbook_connection():
    if current_user.is_authenticated:
        return redirect(url_for('main.userviz'))
        
    if request.method == 'POST':
        try:
            profile_url = request.form.get('profile_url')
            if profile_url:
                return handle_profile_submission(profile_url)
            flash('Please provide a Mountain Project profile URL', 'danger')
        except Exception as e:
            current_app.logger.error(f"Logbook connection error: {str(e)}")
            flash('Failed to process profile connection', 'danger')
            
    return render_template('logbook_connection.html')

# Terms and Privacy Routes--------------------------------
@main_bp.route("/terms-privacy")
@cache.cached(timeout=86400) 
def terms_and_privacy():
    return render_template('termsAndPrivacy.html')


# User Viz Routes--------------------------------
@main_bp.route("/userviz")
def userviz():
    if not current_user.is_authenticated:
        return redirect(url_for('main.logbook_connection'))
        
    if not current_user.mtn_project_profile_url:
        flash('No climbing data associated with account', 'warning')
        return redirect(url_for('main.logbook_connection'))
        
    user_id = current_user.id
    
    user = User.query.get(user_id)
    if not user:
        return "User not found", 404
        
    # Get pyramids from database
    pyramids = DatabaseService.get_pyramids_by_user_id(user_id)
    binned_code_dict = BinnedCodeDict.query.all()
    user_ticks = DatabaseService.get_user_ticks_by_id(user_id)

    # Get analytics metrics
    analytics_service = AnalyticsService(db)
    metrics = analytics_service.get_all_metrics(user_id=user_id)

    # Convert to dictionaries and handle serialization
    sport_pyramid_data = [r.as_dict() for r in pyramids['sport']]
    trad_pyramid_data = [r.as_dict() for r in pyramids['trad']]
    boulder_pyramid_data = [r.as_dict() for r in pyramids['boulder']]
    binned_code_dict_data = [r.as_dict() for r in binned_code_dict]
    user_ticks_data = [r.as_dict() for r in user_ticks]

    # Pre-serialize the data using the custom encoder
    encoder = CustomJSONEncoder()
    sport_pyramid_json = json.loads(encoder.encode(sport_pyramid_data))
    trad_pyramid_json = json.loads(encoder.encode(trad_pyramid_data))
    boulder_pyramid_json = json.loads(encoder.encode(boulder_pyramid_data))
    user_ticks_json = json.loads(encoder.encode(user_ticks_data))
    binned_code_dict_json = json.loads(encoder.encode(binned_code_dict_data))
    
    return render_template('viz/userviz.html', 
                         user_id=user_id,
                         username=user.username,
                         sport_pyramid=sport_pyramid_json,
                         trad_pyramid=trad_pyramid_json,
                         boulder_pyramid=boulder_pyramid_json,
                         user_ticks=user_ticks_json,
                         binned_code_dict=binned_code_dict_json,
                         **metrics)

@main_bp.route("/performance-pyramid")
def performance_pyramid():
    user_id = current_user.id
    # Get user data
    user = UserTicks.query.filter_by(user_id=user_id).first()
    if not user:
        return "User not found", 404

    # Get pyramids directly from database
    pyramids = DatabaseService.get_pyramids_by_user_id(user_id)
    binned_code_dict = BinnedCodeDict.query.all()
    user_ticks = DatabaseService.get_user_ticks_by_id(user_id)

    # Convert to dictionaries and handle serialization
    sport_pyramid_data = [r.as_dict() for r in pyramids['sport']]
    trad_pyramid_data = [r.as_dict() for r in pyramids['trad']]
    boulder_pyramid_data = [r.as_dict() for r in pyramids['boulder']]
    user_ticks_data = [r.as_dict() for r in user_ticks]
    binned_code_dict_data = [r.as_dict() for r in binned_code_dict]

    # Pre-serialize the data using the custom encoder
    encoder = CustomJSONEncoder()
    sport_pyramid_json = json.loads(encoder.encode(sport_pyramid_data))
    trad_pyramid_json = json.loads(encoder.encode(trad_pyramid_data))
    boulder_pyramid_json = json.loads(encoder.encode(boulder_pyramid_data))
    user_ticks_json = json.loads(encoder.encode(user_ticks_data))
    binned_code_dict_json = json.loads(encoder.encode(binned_code_dict_data))

    return render_template('performancePyramid.html',
                         user_id=user_id,
                         username=user.username,
                         sport_pyramid=sport_pyramid_json,
                         trad_pyramid=trad_pyramid_json,
                         boulder_pyramid=boulder_pyramid_json,
                         user_ticks=user_ticks_json,
                         binned_code_dict=binned_code_dict_json)

@main_bp.route("/base-volume")
def base_volume():
    user_id = current_user.id

    # Get user data
    user = UserTicks.query.filter_by(user_id=user_id).first()
    if not user:
        return "User not found", 404

    user_ticks = DatabaseService.get_user_ticks_by_id(user_id)
    binned_code_dict = BinnedCodeDict.query.all()

    # Convert to dictionaries and handle serialization
    user_ticks_data = [r.as_dict() for r in user_ticks]
    binned_code_dict_data = [r.as_dict() for r in binned_code_dict]

    # Pre-serialize the data using the custom encoder
    encoder = CustomJSONEncoder()
    user_ticks_json = json.loads(encoder.encode(user_ticks_data))
    binned_code_dict_json = json.loads(encoder.encode(binned_code_dict_data))

    return render_template('baseVolume.html',
                         user_id=user_id,
                         username=user.username,
                         user_ticks=user_ticks_json,
                         binned_code_dict=binned_code_dict_json)

@main_bp.route("/progression")
def progression():
    user_id = current_user.id

    # Get user data
    user = UserTicks.query.filter_by(user_id=user_id).first()
    if not user:
        return "User not found", 404

    user_ticks = DatabaseService.get_user_ticks_by_id(user_id)
    binned_code_dict = BinnedCodeDict.query.all()

    return render_template('progression.html',
                         user_id=user_id,
                         username=user.username,
                         user_ticks=json.dumps([r.as_dict() for r in user_ticks], cls=CustomJSONEncoder),
                         binned_code_dict=json.dumps([r.as_dict() for r in binned_code_dict], cls=CustomJSONEncoder))

@main_bp.route("/when-where")
def when_where():
    user_id = current_user.id
    # Get user data
    user = UserTicks.query.filter_by(user_id=user_id).first()
    if not user:
        return "User not found", 404

    user_ticks = DatabaseService.get_user_ticks_by_id(user_id)

    return render_template('whenWhere.html',
                         user_id=user_id,
                         username=user.username,
                         user_ticks=json.dumps([r.as_dict() for r in user_ticks], cls=CustomJSONEncoder))

@main_bp.route("/pyramid-input", methods=['GET', 'POST'])
def pyramid_input():
    user_id = current_user.id

    # Get user data
    user = UserTicks.query.filter_by(user_id=user_id).first()
    if not user:
        flash('User not found.')
        return redirect(url_for('main.index'))
    # Initialize grade processor
    grade_processor = GradeProcessor()
    if request.method == 'POST':
        try:
            # Get the changes data from the form
            changes_data = request.form.get('changes_data')
            if changes_data:
                changes = json.loads(changes_data)
                current_app.logger.info(f"Received changes data: {changes}")
                
                # Process the changes directly to pyramid tables
                update_service = PyramidUpdateService()
                update_service.process_changes(user_id=user_id, changes=changes)
                
                return redirect(url_for('main.performance_characteristics', user_id=user_id))
            else:
                flash('No changes were submitted.', 'warning')
                return redirect(url_for('main.pyramid_input', user_id=user_id))
            
        except Exception as e:
            current_app.logger.error(f"Error processing changes: {str(e)}")
            flash('An error occurred while saving changes.', 'error')
            return redirect(url_for('main.pyramid_input', user_id=user_id))

    # GET request - show the form
    pyramids = DatabaseService.get_pyramids_by_user_id(user_id)
    routes_grade_list = grade_processor.routes_grade_list
    boulders_grade_list = grade_processor.boulders_grade_list
    
    return render_template('pyramidInputs.html',
                         user_id=user_id,
                         username=user.username,
                         sport_pyramid=pyramids['sport'],
                         trad_pyramid=pyramids['trad'],
                         boulder_pyramid=pyramids['boulder'],
                         routes_grade_list=routes_grade_list,
                         boulders_grade_list=boulders_grade_list)

@main_bp.route("/performance-characteristics")
def performance_characteristics():
    user_id = current_user.id

    # Get user data
    user = UserTicks.query.filter_by(user_id=user_id).first()
    if not user:
        return "User not found", 404

    # Get pyramids directly from database
    pyramids = DatabaseService.get_pyramids_by_user_id(user_id)
    binned_code_dict = BinnedCodeDict.query.all()

    # Convert to dictionaries and handle serialization
    sport_pyramid_data = [r.as_dict() for r in pyramids['sport']]
    trad_pyramid_data = [r.as_dict() for r in pyramids['trad']]
    boulder_pyramid_data = [r.as_dict() for r in pyramids['boulder']]
    binned_code_dict_data = [r.as_dict() for r in binned_code_dict]

    # Pre-serialize the data using the custom encoder
    encoder = CustomJSONEncoder()
    sport_pyramid_json = json.loads(encoder.encode(sport_pyramid_data))
    trad_pyramid_json = json.loads(encoder.encode(trad_pyramid_data))
    boulder_pyramid_json = json.loads(encoder.encode(boulder_pyramid_data))
    binned_code_dict_json = json.loads(encoder.encode(binned_code_dict_data))

    return render_template('performanceCharacteristics.html',
                         user_id=user_id,
                         username=user.username,
                         sport_pyramid=sport_pyramid_json,
                         trad_pyramid=trad_pyramid_json,
                         boulder_pyramid=boulder_pyramid_json,
                         binned_code_dict=binned_code_dict_json)

@main_bp.route("/delete-tick/<int:tick_id>", methods=['DELETE'])
def delete_tick(tick_id):
    try:
        # Get user info before deletion for pyramid rebuild
        user_tick = UserTicks.query.get(tick_id)
        if not user_tick:
            return jsonify({
                'success': False, 
                'error': 'Tick not found'
            }), 404
            
        user_id = user_tick.user_id
        current_app.logger.info(f"Deleting tick {tick_id} for user {user_id}")
        
        # Delete the tick and rebuild pyramids
        success = DatabaseService.delete_user_tick(tick_id)
        
        if success:
            # Get the fresh pyramid data to return
            pyramids = DatabaseService.get_pyramids_by_user_id(user_id)
            pyramid_data = {
                'sport': [r.as_dict() for r in pyramids['sport']],
                'trad': [r.as_dict() for r in pyramids['trad']],
                'boulder': [r.as_dict() for r in pyramids['boulder']]
            }
            
            # Log pyramid data sizes
            current_app.logger.info(f"Returning pyramid data - Sport: {len(pyramid_data['sport'])}, Trad: {len(pyramid_data['trad'])}, Boulder: {len(pyramid_data['boulder'])}")
            
            # Convert dates to strings
            for discipline in pyramid_data.values():
                for item in discipline:
                    if 'tick_date' in item:
                        item['tick_date'] = item['tick_date'].strftime('%Y-%m-%d')
            
            return jsonify({
                'success': True,
                'pyramids': pyramid_data
            })
        else:
            current_app.logger.error(f"Failed to delete tick {tick_id}")
            return jsonify({
                'success': False, 
                'error': 'Error deleting tick'
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Error deleting tick {tick_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Server error while deleting tick'
        }), 500

@main_bp.route("/refresh-data", methods=['POST'])
def refresh_data():
    user_id = current_user.id
    try:
        # Get user data
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            return jsonify({
                'error': 'User not found'
            }), 404

        # Get the profile URL from user data
        profile_url = user.mtn_project_profile_url
        if not profile_url:
            return jsonify({
                'error': 'Profile URL not found'
            }), 404

        # Clear existing data
        DatabaseService.clear_user_data(user_id=user_id)
        
        # Process the profile
        processor = DataProcessor(db.session)
        sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks = processor.process_profile(profile_url)


        # Update the calculated data using DatabaseService
        DatabaseService.save_calculated_data({
            'sport_pyramid': sport_pyramid,
            'trad_pyramid': trad_pyramid,
            'boulder_pyramid': boulder_pyramid,
            'user_ticks': user_ticks
        })

        return redirect(url_for('main.userviz', user_id=user_id))

    except Exception as e:
        current_app.logger.error(f"Error refreshing data for user {user_id}: {str(e)}")
        return jsonify({
            'error': 'An error occurred while refreshing your data. Please try again.'
        }), 500


# Chat Routes--------------------------------
REQUIRED_FIELDS = ['climbing_goals']

@main_bp.route("/sage-chat")
@login_required
@temp_user_check
def sage_chat():
    user_id = current_user.id
    current_app.logger.info(f"Sage chat request for user_id: {user_id}")
    
    # First check if user exists in UserTicks
    user = UserTicks.query.filter_by(user_id=user_id).first()
    if not user:
        current_app.logger.error(f"User not found in UserTicks: {user_id}")
        return "User not found", 404

    try:
        # Get or create ClimberSummary using the service
        summary_service = ClimberSummaryService(user_id=user_id, username=user.username)
        summary = ClimberSummary.query.get(user_id)
        
        if not summary:
            current_app.logger.info(f"Creating new ClimberSummary for user: {user_id}")
            # This will create a complete summary with all available data
            summary = summary_service.update_summary()
        else:
            # Update existing summary to ensure all fields are populated
            summary = summary_service.update_summary()
        
        current_app.logger.info(f"Found/created climber summary for user: {summary.username}")
        data_complete = check_data_completeness(summary)
        current_app.logger.info(f"Data completeness check: {data_complete}")
        
        # Initialize grade processor for grade lists
        grade_processor = GradeProcessor()
        routes_grade_list = grade_processor.routes_grade_list
        boulders_grade_list = grade_processor.boulders_grade_list
        
        # Convert summary to dictionary
        summary_dict = {}
        for column in summary.__table__.columns:
            value = getattr(summary, column.name)
            # Handle enum values
            if hasattr(value, 'name'):
                summary_dict[column.name] = value.name
            else:
                summary_dict[column.name] = value
        
        return render_template('sageChat.html', 
                             initial_summary=summary_dict,
                             user_id=user_id,
                             initial_data_complete=data_complete,
                             message_view=data_complete,
                             routes_grade_list=routes_grade_list,
                             boulders_grade_list=boulders_grade_list)
    except Exception as e:
        current_app.logger.error(f"Error in sage_chat route: {str(e)}")
        db.session.rollback()
        raise

@main_bp.route("/sage-chat/onboard", methods=['POST'])
@login_required
@temp_user_check
def sage_chat_onboard(user_id):
    summary = ClimberSummary.query.get_or_404(user_id)
    
    try:
        # Create UserInputData from form data
        user_input = UserInputData(
            # Core progression metrics
            highest_sport_grade_tried=request.form.get('highest_sport_grade_tried'),
            highest_trad_grade_tried=request.form.get('highest_trad_grade_tried'),
            highest_boulder_grade_tried=request.form.get('highest_boulder_grade_tried'),
            total_climbs=int(request.form.get('total_climbs')) if request.form.get('total_climbs') else None,
            favorite_discipline=request.form.get('favorite_discipline'),
            years_climbing_outside=int(request.form.get('years_climbing_outside')) if request.form.get('years_climbing_outside') else None,
            preferred_crag_last_year=request.form.get('preferred_crag_last_year'),
            
            # Training context
            training_frequency=request.form.get('training_frequency'),
            typical_session_length=request.form.get('typical_session_length'),
            has_hangboard=request.form.get('has_hangboard', '').lower() == 'true',
            has_home_wall=request.form.get('has_home_wall', '').lower() == 'true',
            goes_to_gym=request.form.get('goes_to_gym', '').lower() == 'true',
            
            # Performance metrics
            highest_grade_sport_sent_clean_on_lead=request.form.get('highest_grade_sport_sent_clean_on_lead'),
            highest_grade_tr_sent_clean=request.form.get('highest_grade_tr_sent_clean'),
            highest_grade_trad_sent_clean_on_lead=request.form.get('highest_grade_trad_sent_clean_on_lead'),
            highest_grade_boulder_sent_clean=request.form.get('highest_grade_boulder_sent_clean'),
            onsight_grade_sport=request.form.get('onsight_grade_sport'),
            onsight_grade_trad=request.form.get('onsight_grade_trad'),
            flash_grade_boulder=request.form.get('flash_grade_boulder'),
            
            # Injury history and limitations
            current_injuries=request.form.get('current_injuries'),
            injury_history=request.form.get('injury_history'),
            physical_limitations=request.form.get('physical_limitations'),
            
            # Goals and preferences
            climbing_goals=request.form.get('climbing_goals'),
            willing_to_train_indoors=request.form.get('willing_to_train_indoors', '').lower() == 'true',
            
            # Recent activity
            sends_last_30_days=int(request.form.get('sends_last_30_days')) if request.form.get('sends_last_30_days') else None,
            
            # Style preferences
            favorite_angle=request.form.get('favorite_angle'),
            favorite_hold_types=request.form.get('favorite_hold_types'),
            weakest_style=request.form.get('weakest_style'),
            strongest_style=request.form.get('strongest_style'),
            favorite_energy_type=request.form.get('favorite_energy_type'),
            
            # Lifestyle
            sleep_score=request.form.get('sleep_score'),
            nutrition_score=request.form.get('nutrition_score'),
            
            # Additional notes
            additional_notes=request.form.get('additional_notes')
        )
        
        # Validate required fields
        if not user_input.climbing_goals:
            return jsonify({"error": "climbing_goals is required"}), 400
            
        # Use service to update summary
        summary_service = ClimberSummaryService(user_id=user_id, username=summary.username)
        summary = summary_service.update_summary(user_input=user_input)
        
        # Return success with reset_chat flag to trigger frontend reset
        return jsonify({
            "success": True,
            "reset_chat": True  # Add this flag to indicate chat should be reset
        })
    except Exception as e:
        current_app.logger.error(f"Error in sage_chat_onboard: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "Failed to update profile"}), 400

@main_bp.route("/sage-chat/message", methods=['POST'])
@login_required
@temp_user_check
def sage_chat_message(user_id):
    summary = ClimberSummary.query.get_or_404(user_id)
    
    # Check daily message limit for basic tier users
    if current_user.tier == 'basic':
        from datetime import date
        today = date.today()
        
        # Reset counter if it's a new day
        if current_user.last_message_date != today:
            current_user.daily_message_count = 0
            current_user.last_message_date = today
            
        # Check if user has reached daily limit
        if current_user.daily_message_count >= 25:
            return jsonify({"error": "Daily message limit reached. Upgrade to premium for unlimited messages."}), 429
            
        # Increment message count
        current_user.daily_message_count += 1
        db.session.commit()
    
    data = request.get_json()
    user_prompt = data.get('user_prompt')
    if not user_prompt:
        return jsonify({"error": "Message cannot be empty"}), 400
        
    is_first_message = data.get('is_first_message', False)
    conversation_history = data.get('conversation_history', [])
    use_reasoner = data.get('use_reasoner', False)
    
    # For first message with reasoner, get the context
    initial_user_message = None
    if is_first_message and use_reasoner:
        additional_context = get_climber_context(user_id)
        context_str = "\n".join(f"- {k}: {v}" for k, v in additional_context.items())
        initial_user_message = f"Here is my climbing context:\n\n{context_str}\n\n{user_prompt}"
    
    ai_response = get_completion(
        user_prompt, 
        climber_id=user_id, 
        is_first_message=is_first_message,
        messages=conversation_history,
        use_reasoner=use_reasoner
    )

    # Prepare response data
    response_data = {}
    if use_reasoner:
        response_data["response"] = ai_response[0]
        response_data["reasoning"] = ai_response[1]
        if initial_user_message:
            response_data["initial_user_message"] = initial_user_message
    else:
        response_data["response"] = ai_response
        response_data["reasoning"] = None

    # Add context for first message (only for regular chat)
    if is_first_message and not use_reasoner:
        additional_context = get_climber_context(user_id)
        context_str = "\n".join(f"- {k}: {v}" for k, v in additional_context.items())
        response_data["context"] = f"Here is your climbing context that I'll reference throughout our conversation:\n\n{context_str}"
        response_data["context_role"] = "assistant"
    
    return jsonify(response_data)

@main_bp.route('/upload', methods=['POST'])
@login_required
@temp_user_check
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400
        
    # Check file size based on user tier
    max_size = 10_000_000 if current_user.tier == 'premium' else 1_000_000  # 10MB for premium, 1MB for basic
    if file.content_length > max_size:
        return jsonify({"error": f"File size exceeds {max_size/1_000_000}MB limit for your tier"}), 413
        
    # Check file type (only allow txt and csv)
    allowed_extensions = {'txt', 'csv'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if file_ext not in allowed_extensions:
        return jsonify({"error": "Only .txt and .csv files are allowed"}), 400
        
    try:
        content = file.read().decode('utf-8')
        upload = UserUpload(
            user_id=current_user.id,
            filename=file.filename,
            file_size=len(content),
            file_type=file_ext,
            content=content
        )
        db.session.add(upload)
        db.session.commit()
        return jsonify({"success": True, "message": "File uploaded successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error uploading file: {str(e)}"}), 500

def check_data_completeness(summary):
    required_fields = [
        'climbing_goals',  # Goals and preferences
        'favorite_discipline',  # Core progression
        'typical_session_length',  # Training context
        'favorite_angle',  # Style preferences
        'favorite_hold_types',  # Style preferences
        'weakest_style',  # Style preferences
        'strongest_style',  # Style preferences
        'favorite_energy_type',  # Style preferences
        'sleep_score',  # Lifestyle
        'nutrition_score'  # Lifestyle
    ]
    for field in required_fields:
        if getattr(summary, field) in [None, '']:
            return False
    return True





# Health Check Routes--------------------------------
@main_bp.route("/health")
def health_check():
    """Health check endpoint that includes database connection and memory status"""
    try:
        # Test database connection
        db.session.execute(text('SELECT 1'))
        db_status = "healthy"
        
        # Get memory usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return jsonify({
            'status': 'healthy',
            'database': {
                'status': db_status
            },
            'memory': {
                'rss': memory_info.rss / 1024 / 1024,  # RSS in MB
                'vms': memory_info.vms / 1024 / 1024,  # VMS in MB
                'percent': process.memory_percent()
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        current_app.logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
    

# Add new route for demo login
@main_bp.route("/demo-login", methods=['POST'])
def demo_login():
    demo_user = User.query.get(1)
    
    if not demo_user:
        # Create user
        demo_user = User(
            id=1,
            username='demo_user',
            email='demo@sendsage.com',
            tier='premium',
            payment_status='active',
            mtn_project_profile_url='https://www.mountainproject.com/demo'
        )
        demo_user.set_password(os.urandom(24).hex())
        db.session.add(demo_user)
        db.session.commit()
        
        # Process data ONLY for new users
        processor = DataProcessor(db.session)
        processor.process_demo_data(demo_user.id, demo_user.username)
    else:
        db.session.expire_all()

    login_user(demo_user)
    return redirect(url_for('main.userviz'))



