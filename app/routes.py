from flask import render_template, request, redirect, url_for, jsonify, flash, current_app, Blueprint
from app import db, cache, bcrypt, mail
import logging
from flask_wtf import FlaskForm
import json
from uuid import UUID
from functools import wraps
from flask_login import current_user, login_user, logout_user, login_required
import stripe
import os
from flask_wtf.csrf import CSRFProtect
from app.models import (
    BinnedCodeDict, 
    UserTicks, 
    ClimberSummary,
    User,
    UserUpload,
    PerformancePyramid,
    ClimbingDiscipline,
    CruxAngle,
    CruxEnergyType,
    HoldType,
    SleepScore,
    NutritionScore,
    SessionLength,
)
from app.services import DataProcessor, DataProcessingError
from app.services.database_service import DatabaseService
from app.services.analytics_service import AnalyticsService
from app.services.climber_summary import ClimberSummaryService, UserInputData
from app.services.ai.old_code.api import get_completion, get_climber_context
from app.services.auth.auth_service import generate_reset_token, validate_reset_token
from app.services.user.user_service import UserService, UserCreationError, UserType
from datetime import date, datetime, timedelta
from app.services.grade_processor import GradeProcessor
from app.services.pyramid_update_service import PyramidUpdateService
import psutil
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError
from flask_mail import Message
from app.forms import LoginForm, RegisterForm, LogbookConnectionForm, ClimberSummaryForm
from app.services.payment.stripe_handler import (
    handle_checkout_session,
    handle_subscription_update,
    handle_subscription_cancellation,
    handle_payment_failure,
    get_tier_from_subscription,
    handle_invoice_payment_succeeded,
    handle_subscription_created
)
from app.services.ai.chat.orchestrator import ChatOrchestrator
from app.services.ai.model_wrappers.v3_client import DeepseekV3Client
from app.services.ai.model_wrappers.r1_client import R1Client
from app.services.context.context_formatter import ContextFormatter
from app.services.context.data_integrator import DataIntegrator
import enum

logger = logging.getLogger(__name__)

# Create the Blueprint with CSRF exempt views
main_bp = Blueprint('main', __name__)
main_bp.view_decorators = []  # Clear any existing decorators

# Custom Jinja2 filters
@main_bp.app_template_filter('datetime')
def format_datetime(value):
    """Format a datetime object to a readable string."""
    if not value:
        return ''
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            return value
    return value.strftime('%b %d, %Y')

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        if hasattr(obj, 'value'):  # Handle enum objects
            return obj.value
        if isinstance(obj, UUID):  # Add UUID handling
            return str(obj)
        return super(CustomJSONEncoder, self).default(obj)

def temp_user_check(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.username.endswith('_temp'):
            logout_user()
            flash('Temporary session expired', 'warning')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated

# Add at the top with other constants
VALID_TIERS = {'basic', 'premium'}
VALID_PAYMENT_STATUSES = {'unpaid', 'pending', 'active'}
BASIC_TIER_DAILY_MESSAGE_LIMIT = 25

def payment_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('main.login', next=request.url))
            
        if current_user.payment_status not in VALID_PAYMENT_STATUSES:
            current_app.logger.warning(f"Invalid payment status for user {current_user.id}: {current_user.payment_status}")
            current_user.payment_status = 'unpaid'
            db.session.commit()
            
        if current_user.payment_status != 'active' and request.endpoint != 'main.payment':
            flash('Please complete your payment to access this feature.', 'warning')
            return redirect(url_for('main.payment'))
            
        if current_user.tier not in VALID_TIERS:
            current_app.logger.error(f"Invalid tier for user {current_user.id}: {current_user.tier}")
            current_user.tier = 'basic'  # Reset to default tier
            db.session.commit()
            
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
            user_service = UserService(db.session)
            profile_url = form.mtn_project_profile_url.data.strip() if form.mtn_project_profile_url.data else None
            
            # Create user with profile URL
            user = user_service.create_permanent_user(
                email=form.email.data,
                username=form.username.data,
                password=form.password.data,
                profile_url=profile_url
            )
            
            # Log user in and redirect immediately
            login_user(user)
            flash('Account created successfully! Please select a payment plan to continue.', 'success')
            response = redirect(url_for('main.payment'))
            
            # Process Mountain Project data after response if URL provided
            if profile_url:
                try:
                    # Capture the current application instance
                    app = current_app._get_current_object()
                    
                    @response.call_on_close
                    def process_mountain_project_data():
                        with app.app_context():
                            try:
                                processor = DataProcessor(db.session)
                                logger.info(f"Processing Mountain Project data for new user {user.id}")
                                performance_pyramid, processed_ticks = processor.process_profile(
                                    user_id=str(user.id),
                                    profile_url=profile_url
                                )
                                logger.info(f"Successfully processed Mountain Project data for user {user.id}")
                            except DataProcessingError as e:
                                logger.error(f"Error processing Mountain Project data: {str(e)}")
                            except Exception as e:
                                logger.error(f"Unexpected error processing Mountain Project data: {str(e)}", exc_info=True)
                except Exception as e:
                    logger.error(f"Error setting up Mountain Project data processing: {str(e)}")
            
            return response
            
        except UserCreationError as e:
            logger.error(f"User creation error: {str(e)}")
            flash(str(e), 'danger')
            return render_template('auth/register.html', form=form)
        except Exception as e:
            logger.error(f"Registration error: {str(e)}", exc_info=True)
            flash('Registration failed. Please try again.', 'danger')
            return render_template('auth/register.html', form=form)
            
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
            # Get the appropriate price ID based on the selected tier
            if selected_tier == 'premium':
                price_id = os.getenv('STRIPE_PRICE_ID_PREMIUM')
                current_app.logger.debug(f"Selected premium tier with price_id: {price_id}")
            else:
                price_id = os.getenv('STRIPE_PRICE_ID_BASIC')
                current_app.logger.debug(f"Selected basic tier with price_id: {price_id}")
            
            if not price_id:
                raise ValueError(f"No price ID found for tier: {selected_tier}")
            
            # Create Stripe checkout session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1
                }],
                mode='subscription',
                success_url=url_for('main.payment_success', _external=True),
                cancel_url=url_for('main.payment', _external=True),
                customer_email=current_user.email
            )
            
            current_app.logger.debug(f"Created checkout session: {checkout_session.id}")
            return redirect(checkout_session.url, code=303)
            
        except Exception as e:
            current_app.logger.error(f"Payment processing error: {str(e)}")
            flash('Payment processing error. Please try again.', 'danger')
            return redirect(url_for('main.payment'))
    
    # GET request - show payment page
    prices = {
        'basic': {
            'price': '$9.99',
            'features': [
                'Everything in Free Tier',
                'AI Coaching Chat (25 Daily Messages)',
                'Enhanced Performance Analysis',
                '1MB File Uploads'
            ]
        },
        'premium': {
            'price': '$29.99',
            'features': [
                'Everything in Basic Tier',
                'Unlimited AI Coaching Chat',
                'Advanced Reasoning, Analysis, and Recommendations',
                '10MB File Uploads'
            ]
        }
    }
    
    return render_template('payment/payment.html',
                         selected_tier=selected_tier,
                         stripe_public_key=os.getenv('STRIPE_PUBLIC_KEY'),
                         prices=prices)

@main_bp.route('/payment/success')
@login_required
def payment_success():
    # Immediately update payment status while waiting for webhook
    if current_user.payment_status in ['unpaid', 'temp_account']:
        current_user.payment_status = 'pending_verification'
        db.session.commit()
    
    return render_template('payment/success.html')

@main_bp.route("/stripe-webhook", methods=['POST'])
def stripe_webhook():
    """Stripe webhook endpoint - CSRF protection is disabled for this route"""
    current_app.logger.debug("Entering stripe_webhook handler")
    current_app.logger.debug(f"Request headers: {dict(request.headers)}")
    current_app.logger.debug(f"Request method: {request.method}")
    current_app.logger.debug(f"Request endpoint: {request.endpoint}")
    current_app.logger.debug(f"Blueprint name: {request.blueprint}")
    
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        current_app.logger.debug(f"Successfully constructed Stripe event: {event.type}")
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        current_app.logger.error(f'Webhook error: {str(e)}')
        return jsonify({'error': str(e)}), 400

    # Handle multiple event types
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        if not handle_checkout_session(session):
            current_app.logger.error("Failed to handle checkout session")
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
    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        handle_invoice_payment_succeeded(invoice)
    elif event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        handle_subscription_created(subscription)

    return jsonify({'status': 'success'}), 200

# Landing Page Routes--------------------------------

@main_bp.route("/", methods=['GET'])
def index():
    if current_user.is_authenticated:
        # Check payment status
        if current_user.payment_status not in VALID_PAYMENT_STATUSES or current_user.payment_status != 'active':
            current_user.payment_status = 'unpaid'
            db.session.commit()
            return redirect(url_for('main.payment'))
            
        if current_user.tier not in VALID_TIERS:
            current_user.tier = 'basic'
            db.session.commit()
            
        return redirect(url_for('main.sage_chat'))
    
    return render_template('index.html', 
                         current_user=current_user,
                         support_count=get_support_count().json['count'])

@main_bp.route("/api/support-count")
@cache.cached(timeout=3600)  # Cache for one hour (3600 seconds)
def get_support_count():
    return jsonify({"count": db.session.query(User.id).distinct().count()})


# Logbook Connection Routes--------------------------------
@main_bp.route("/logbook-connection", methods=['GET', 'POST'])
def logbook_connection():
    if current_user.is_authenticated and current_user.mtn_project_profile_url:
        return redirect(url_for('main.userviz'))
        
    form = LogbookConnectionForm()
    
    if request.method == 'POST':
        if not form.validate_on_submit():
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{field}: {error}", 'danger')
            return render_template('logbook_connection.html', form=form)
            
        try:
            profile_url = form.profile_url.data.strip()
            user_service = UserService(db.session)
            
            # Step 1: Determine user type and get/create user
            user_type = user_service.determine_user_type(profile_url)
            logger.info(f"Determined user type: {user_type} for URL: {profile_url}")
            
            if user_type == UserType.EXISTING_PERMANENT:
                # Handle existing permanent user
                user = user_service.get_existing_user(profile_url)
                flash('This Mountain Project profile is already registered. Please log in.', 'warning')
                return redirect(url_for('main.login'))
                
            elif user_type == UserType.EXISTING_TEMP:
                # Handle existing temporary user - just log them in and redirect
                user = user_service.get_temp_user(profile_url)
                logger.info(f"Retrieved existing temp user: {user.username}")
                user_service.login_user_if_needed(user)
                flash('Welcome back! Your climbing data is ready to view.', 'success')
                return redirect(url_for('main.userviz'))
                
            else:  # UserType.NEW_TEMP
                # Create new temporary user
                user = user_service.create_temp_user(profile_url)
                logger.info(f"Created new temp user: {user.username}")
                
                # Process climbing data for new temp user
                try:
                    processor = DataProcessor(db.session)
                    performance_pyramid, processed_ticks = processor.process_profile(
                        user_id=str(user.id),
                        profile_url=profile_url
                    )
                    
                    # Log user in
                    user_service.login_user_if_needed(user)
                    
                    flash('Welcome to Sendsage! Your climbing data has been processed.', 'success')
                    return redirect(url_for('main.userviz'))
                    
                except DataProcessingError as e:
                    logger.error(f"Data processing error for user {user.id}: {str(e)}")
                    # Clean up the temp user if data processing failed
                    db.session.delete(user)
                    db.session.commit()
                    flash(f'Failed to process climbing data: {str(e)}', 'danger')
                    return render_template('logbook_connection.html', form=form)
                
        except UserCreationError as e:
            logger.error(f"User creation/retrieval error: {str(e)}")
            flash(str(e), 'danger')
            return render_template('logbook_connection.html', form=form)
            
        except Exception as e:
            logger.error(f"Unexpected error in logbook connection: {str(e)}", exc_info=True)
            flash('An unexpected error occurred. Please try again.', 'danger')
            return render_template('logbook_connection.html', form=form)
    
    return render_template('logbook_connection.html', form=form)

# Terms and Privacy Routes--------------------------------
@main_bp.route("/terms-privacy")
@cache.cached(timeout=86400) 
def terms_and_privacy():
    return render_template('termsAndPrivacy.html')


# User Viz Routes--------------------------------
class RefreshDataForm(FlaskForm):
    pass

@main_bp.route("/userviz")
def userviz():
    if not current_user.is_authenticated:
        return redirect(url_for('main.logbook_connection'))
        
    if not current_user.mtn_project_profile_url:
        flash('No climbing data associated with account', 'warning')
        return redirect(url_for('main.logbook_connection'))
        
    user_id = current_user.id
    form = RefreshDataForm()
    
    try:
        # Get user and verify existence
        user = User.query.get(user_id)

        if not user or not user.mtn_project_profile_url:
            logger.error(f"User not found: {user_id}")
            return "User not found", 404

        # Get analytics metrics
        analytics_service = AnalyticsService(db)
        metrics = analytics_service.get_all_metrics(user_id=user_id)
        
        logger.info(f"Successfully fetched visualization data for user: {user_id}")
        
        return render_template('viz/userviz.html',
                             user_id=user_id,
                             username=user.username,
                             metrics=metrics,
                             form=form)
                             
    except Exception as e:
        logger.error(f"Error fetching visualization data: {str(e)}", exc_info=True)
        flash('Error loading visualization data. Please try again.', 'danger')
        return redirect(url_for('main.index'))

@main_bp.route("/performance-pyramid")
@login_required
def performance_pyramid():
    try:
        # Get user data
        user = User.query.get(current_user.id)
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('main.index'))

        # Get pyramids and user ticks data using DatabaseService
        pyramids = DatabaseService.get_pyramids_by_user_id(user.id)
        user_ticks = DatabaseService.get_user_ticks_by_id(user.id)
        binned_code_dict = BinnedCodeDict.query.all()

        # Convert to dicts and handle date serialization
        user_ticks_data = [r.as_dict() for r in user_ticks]
        binned_code_dict_data = [r.as_dict() for r in binned_code_dict]

        # Convert dates to strings in user_ticks_data
        for tick in user_ticks_data:
            if 'tick_date' in tick:
                tick['tick_date'] = tick['tick_date'].strftime('%Y-%m-%d')

        # The pyramids data is already properly structured by discipline from DatabaseService
        sport_pyramid_data = pyramids.get('sport', [])
        trad_pyramid_data = pyramids.get('trad', [])
        boulder_pyramid_data = pyramids.get('boulder', [])

        return render_template('viz/performancePyramid.html',
                             user_id=str(user.id),
                             username=user.username,
                             sport_pyramid=sport_pyramid_data,
                             trad_pyramid=trad_pyramid_data,
                             boulder_pyramid=boulder_pyramid_data,
                             user_ticks=user_ticks_data,
                             binned_code_dict=binned_code_dict_data)
                             
    except Exception as e:
        logger.error(f"Error loading performance pyramid data: {str(e)}", exc_info=True)
        flash('Error loading visualization data. Please try again.', 'danger')
        return redirect(url_for('main.index'))

@main_bp.route("/base-volume")
@login_required
def base_volume():
    user_id = current_user.id

    try:
        # Get user data
        user = User.query.get(user_id)
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('main.index'))

        user_ticks = DatabaseService.get_user_ticks_by_id(user_id)
        binned_code_dict = BinnedCodeDict.query.all()

        # Convert to dicts and handle date serialization
        user_ticks_data = [r.as_dict() for r in user_ticks]
        binned_code_dict_data = [r.as_dict() for r in binned_code_dict]

        # Convert dates to strings
        for tick in user_ticks_data:
            if 'tick_date' in tick:
                tick['tick_date'] = tick['tick_date'].strftime('%Y-%m-%d')

        return render_template('viz/baseVolume.html',
                             user_id=str(user_id),
                             username=user.username,
                             user_ticks=user_ticks_data,
                             binned_code_dict=binned_code_dict_data)
                             
    except Exception as e:
        logger.error(f"Error loading base volume data: {str(e)}", exc_info=True)
        flash('Error loading visualization data. Please try again.', 'danger')
        return redirect(url_for('main.index'))

@main_bp.route("/progression")
@login_required
def progression():
    user_id = current_user.id

    try:
        # Get user data
        user = User.query.get(user_id)
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('main.index'))

        user_ticks = DatabaseService.get_user_ticks_by_id(user_id)
        binned_code_dict = BinnedCodeDict.query.all()

        # Convert to dicts and handle date serialization
        user_ticks_data = [r.as_dict() for r in user_ticks]
        binned_code_dict_data = [r.as_dict() for r in binned_code_dict]

        # Convert dates to strings
        for tick in user_ticks_data:
            if 'tick_date' in tick:
                tick['tick_date'] = tick['tick_date'].strftime('%Y-%m-%d')

        return render_template('viz/progression.html',
                             user_id=str(user_id),
                             username=user.username,
                             user_ticks=user_ticks_data,
                             binned_code_dict=binned_code_dict_data)
                             
    except Exception as e:
        logger.error(f"Error loading progression data: {str(e)}", exc_info=True)
        flash('Error loading visualization data. Please try again.', 'danger')
        return redirect(url_for('main.index'))

@main_bp.route("/when-where")
@login_required
def when_where():
    user_id = current_user.id

    try:
        # Get user data
        user = User.query.get(user_id)
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('main.index'))

        user_ticks = DatabaseService.get_user_ticks_by_id(user_id)

        # Convert to dicts and handle date serialization
        user_ticks_data = [r.as_dict() for r in user_ticks]

        # Convert dates to strings
        for tick in user_ticks_data:
            if 'tick_date' in tick:
                tick['tick_date'] = tick['tick_date'].strftime('%Y-%m-%d')

        return render_template('viz/whenWhere.html',
                             user_id=str(user_id),
                             username=user.username,
                             user_ticks=user_ticks_data)
                             
    except Exception as e:
        logger.error(f"Error loading location data: {str(e)}", exc_info=True)
        flash('Error loading visualization data. Please try again.', 'danger')


@main_bp.route("/pyramid-input", methods=['GET', 'POST'])
@login_required
def pyramid_input():
    logger = logging.getLogger(__name__)
    
    try:
        if not current_user.is_authenticated:
            logger.warning("User not authenticated, redirecting to login")
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('main.login'))

        user_id = current_user.id
        logger.info(f"Processing pyramid input request for user {user_id}")

        user = User.query.get(user_id)
        if not user:
            logger.warning(f"User not found for id: {user_id}")
            flash('User not found. Please log in again.', 'warning')
            return redirect(url_for('main.login'))

        grade_processor = GradeProcessor()
        logger.info("Grade processor initialized")

        if request.method == 'POST':
            try:
                form_data = request.get_json()
                if not form_data:
                    logger.error("No form data received in POST request")
                    return jsonify({
                        'success': False,
                        'message': 'No data received'
                    }), 400

                logger.debug(f"Received form data: {form_data}")
                
                update_service = PyramidUpdateService(db.session)
                
                # Process changes for each discipline
                for discipline in ['sport', 'trad', 'boulder']:
                    if discipline_data := form_data.get(discipline):
                        logger.info(f"Processing {discipline} discipline data")
                        logger.debug(f"{discipline} data: {discipline_data}")
                        
                        # Use the discipline_data directly as it already has the correct structure
                        changes = {
                            'removed': discipline_data.get('removed', []),
                            discipline: discipline_data
                        }
                        
                        logger.debug(f"Transformed changes for {discipline}: {changes}")
                        
                        try:
                            success = update_service.process_changes(user_id=user_id, changes_data=changes)
                            if not success:
                                logger.error(f"Failed to process changes for {discipline}")
                                return jsonify({
                                    'success': False,
                                    'message': f'Failed to process {discipline} changes'
                                }), 500
                            logger.info(f"Successfully processed changes for {discipline}")
                        except Exception as e:
                            logger.error(f"Error processing {discipline} changes: {str(e)}", exc_info=True)
                            return jsonify({
                                'success': False,
                                'message': f'Error processing {discipline} changes: {str(e)}'
                            }), 500

                # Return success response
                return jsonify({
                    'success': True,
                    'message': 'Changes saved successfully',
                    'redirect_url': url_for('main.performance_pyramid')
                })

            except Exception as e:
                logger.error(f"Error processing changes: {str(e)}", exc_info=True)
                return jsonify({
                    'success': False,
                    'message': f'An error occurred: {str(e)}'
                }), 500

        # GET request handling
        logger.info("Fetching initial pyramid data from DatabaseService")
        pyramids = DatabaseService.get_pyramids_by_user_id(user_id)
        logger.debug(f"Raw pyramid data: {pyramids}")

        routes_grade_list = grade_processor.routes_grade_list
        boulders_grade_list = grade_processor.boulders_grade_list
        logger.debug(f"Grade lists loaded - Routes: {len(routes_grade_list)}, Boulders: {len(boulders_grade_list)}")

        template_data = {
            'user_id': str(user_id),
            'username': user.username,
            'sport_pyramid': pyramids.get('sport', []),
            'trad_pyramid': pyramids.get('trad', []),
            'boulder_pyramid': pyramids.get('boulder', []),
            'routes_grade_list': routes_grade_list,
            'boulders_grade_list': boulders_grade_list
        }

        logger.info("Rendering template with initial data")
        return render_template('viz/pyramidInputs.html', **template_data)

    except Exception as e:
        logger.error(f"Unexpected error in pyramid_input: {str(e)}", exc_info=True)
        flash('An unexpected error occurred. Please try again.', 'danger')
        return redirect(url_for('main.index'))

@main_bp.route("/performance-characteristics")
@login_required
def performance_characteristics():
    try:
        # Get user data
        user = User.query.get(current_user.id)
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('main.index'))

        # Get pyramids and user ticks data using DatabaseService
        pyramids = DatabaseService.get_pyramids_by_user_id(user.id)
        logger.info(f"Raw pyramids data from DB: {pyramids}")
        
        user_ticks = DatabaseService.get_user_ticks_by_id(user.id)
        binned_code_dict = BinnedCodeDict.query.all()

        # Convert to dicts and handle date serialization
        user_ticks_data = [r.as_dict() for r in user_ticks]
        binned_code_dict_data = [r.as_dict() for r in binned_code_dict]

        # Convert dates to strings in user_ticks_data
        for tick in user_ticks_data:
            if 'tick_date' in tick:
                tick['tick_date'] = tick['tick_date'].strftime('%Y-%m-%d')

        # The pyramids data is already properly structured by discipline from DatabaseService
        sport_pyramid_data = pyramids.get('sport', [])
        trad_pyramid_data = pyramids.get('trad', [])
        boulder_pyramid_data = pyramids.get('boulder', [])

        logger.info(f"Processed pyramid data - Sport: {len(sport_pyramid_data)}, Trad: {len(trad_pyramid_data)}, Boulder: {len(boulder_pyramid_data)}")

        template_data = {
            'user_id': str(user.id),
            'username': user.username,
            'sport_pyramid': sport_pyramid_data,
            'trad_pyramid': trad_pyramid_data,
            'boulder_pyramid': boulder_pyramid_data,
            'user_ticks': user_ticks_data,
            'binned_code_dict': binned_code_dict_data
        }
        
        logger.info("Template data prepared successfully")
        return render_template('viz/performanceCharacteristics.html', **template_data)

    except Exception as e:
        logger.error(f"Error loading performance characteristics data: {str(e)}", exc_info=True)
        flash('Error loading visualization data. Please try again.', 'danger')
        return redirect(url_for('main.index'))

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
@login_required
def refresh_data():
    form = RefreshDataForm()
    if not form.validate_on_submit():
        flash('Invalid form submission. Please try again.', 'danger')
        return redirect(url_for('main.userviz'))
        
    try:
        # Get user data
        user = User.query.get(current_user.id)
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
        DatabaseService.clear_user_data(user_id=user.id)
        
        # Process the profile
        processor = DataProcessor(db.session)
        try:
            performance_pyramid, processed_ticks = processor.process_profile(
                profile_url=profile_url,
                user_id=user.id
            )
            
            # Update climber summary if it exists
            if hasattr(user, 'climber_summary') and user.climber_summary:
                summary_service = ClimberSummaryService(user_id=user.id, username=user.username)
                summary_service.update_summary()
            
            flash('Data refreshed successfully!', 'success')
            return redirect(url_for('main.userviz'))
            
        except DataProcessingError as e:
            flash(str(e), 'danger')
            return redirect(url_for('main.userviz'))

    except Exception as e:
        logger.error(f"Error refreshing data for user {current_user.id}: {str(e)}")
        flash('An error occurred while refreshing your data. Please try again.', 'danger')
        return redirect(url_for('main.userviz'))


# Chat Routes--------------------------------
REQUIRED_FIELDS = ['climbing_goals']

@main_bp.route("/sage-chat")
@login_required
@temp_user_check
@payment_required
def sage_chat():
    user_id = current_user.id
    current_app.logger.info(f"Sage chat request for user_id: {user_id}")
    
    try:
        # Get existing ClimberSummary without updating
        initial_summary = ClimberSummary.query.get(user_id)
        
        if not initial_summary:
            current_app.logger.info(f"Creating new ClimberSummary for user: {user_id}")
            summary_service = ClimberSummaryService(user_id=user_id)
            initial_summary = summary_service.update_summary()
        
        # Create form instance
        form = ClimberSummaryForm()
        
        # Check data completeness
        data_complete = check_data_completeness(initial_summary)
        
        # Initialize grade processor for grade lists
        grade_processor = GradeProcessor()
        
        # Get user's subscription tier for message limit display
        user_tier = current_user.tier if hasattr(current_user, 'tier') else 'basic'
        messages_remaining = None
        if user_tier == 'basic':
            today = date.today()
            if current_user.last_message_date != today:
                messages_remaining = 25
            else:
                messages_remaining = max(0, 25 - (current_user.daily_message_count or 0))
        
        return render_template('chat/main.html',
                             user_id=user_id,
                             initial_summary=initial_summary,
                             initial_data_complete=data_complete,
                             routes_grade_list=grade_processor.routes_grade_list,
                             boulders_grade_list=grade_processor.boulders_grade_list,
                             user_tier=user_tier,
                             messages_remaining=messages_remaining,
                             form=form)
                             
    except Exception as e:
        current_app.logger.error(f"Error in sage_chat: {str(e)}", exc_info=True)
        flash('An error occurred while loading the chat. Please try again.', 'error')
        return redirect(url_for('main.payment'))

@main_bp.route("/sage-chat/onboard", methods=['POST'])
@login_required
@temp_user_check
def sage_chat_onboard():
    user_id = current_user.id
    current_app.logger.info(f"Processing onboarding data for user: {user_id}")
    
    try:
        summary = ClimberSummary.query.get_or_404(user_id)
        form_data = request.form.to_dict()
        
        # Convert boolean fields
        boolean_fields = ['access_to_commercial_gym']
        for field in boolean_fields:
            if field in form_data:
                form_data[field] = form_data[field].lower() == 'true'
        
        # Convert numeric fields
        numeric_fields = {
            'total_climbs': int,
            'years_climbing': int,
            'activity_last_30_days': int
        }
        
        for field, converter in numeric_fields.items():
            if field in form_data and form_data[field]:
                try:
                    form_data[field] = converter(form_data[field])
                except (ValueError, TypeError):
                    current_app.logger.warning(f"Invalid {field} value: {form_data[field]}")
                    form_data[field] = None
        
        # Create UserInputData from form data
        user_input = UserInputData(
            # Core progression metrics
            highest_sport_grade_tried=form_data.get('highest_sport_grade_tried'),
            highest_trad_grade_tried=form_data.get('highest_trad_grade_tried'),
            highest_boulder_grade_tried=form_data.get('highest_boulder_grade_tried'),
            total_climbs=form_data.get('total_climbs'),
            favorite_discipline=form_data.get('favorite_discipline'),
            years_climbing=form_data.get('years_climbing'),
            preferred_crag_last_year=form_data.get('preferred_crag_last_year'),
            
            # Core Context
            climbing_goals=form_data.get('climbing_goals'),
            current_training_description=form_data.get('current_training_description'),
            interests=form_data.get('interests'),
            injury_information=form_data.get('injury_information'),
            additional_notes=form_data.get('additional_notes'),
            
            # Advanced Settings - Training Context
            current_training_frequency=form_data.get('current_training_frequency'),
            typical_session_length=form_data.get('typical_session_length'),
            typical_session_intensity=form_data.get('typical_session_intensity'),
            home_equipment=form_data.get('home_equipment'),
            access_to_commercial_gym=form_data.get('access_to_commercial_gym', False),
            supplemental_training=form_data.get('supplemental_training'),
            training_history=form_data.get('training_history'),
            
            # Performance metrics
            highest_grade_sport_sent_clean_on_lead=form_data.get('highest_grade_sport_sent_clean_on_lead'),
            highest_grade_tr_sent_clean=form_data.get('highest_grade_tr_sent_clean'),
            highest_grade_trad_sent_clean_on_lead=form_data.get('highest_grade_trad_sent_clean_on_lead'),
            highest_grade_boulder_sent_clean=form_data.get('highest_grade_boulder_sent_clean'),
            onsight_grade_sport=form_data.get('onsight_grade_sport'),
            onsight_grade_trad=form_data.get('onsight_grade_trad'),
            flash_grade_boulder=form_data.get('flash_grade_boulder'),
            
            # Health and Limitations
            physical_limitations=form_data.get('physical_limitations'),
            
            # Recent Activity
            activity_last_30_days=form_data.get('activity_last_30_days'),
            
            # Style preferences
            favorite_angle=form_data.get('favorite_angle'),
            strongest_angle=form_data.get('strongest_angle'),
            weakest_angle=form_data.get('weakest_angle'),
            favorite_hold_types=form_data.get('favorite_hold_types'),
            strongest_hold_types=form_data.get('strongest_hold_types'),
            weakest_hold_types=form_data.get('weakest_hold_types'),
            favorite_energy_type=form_data.get('favorite_energy_type'),
            strongest_energy_type=form_data.get('strongest_energy_type'),
            weakest_energy_type=form_data.get('weakest_energy_type'),
            
            # Lifestyle
            sleep_score=form_data.get('sleep_score'),
            nutrition_score=form_data.get('nutrition_score')
        )
        
        # Use service to update summary
        summary_service = ClimberSummaryService(user_id=user_id)
        updated_summary = summary_service.update_summary(user_input=user_input)
        
        # Verify data completeness after update
        if not check_data_completeness(updated_summary):
            current_app.logger.warning(f"Incomplete data after update for user: {user_id}")
            return jsonify({
                "error": "Required fields are missing or invalid",
                "success": False
            }), 400
        
        current_app.logger.info(f"Successfully updated climber summary for user: {user_id}")
        return jsonify({
            "success": True,
            "message": "Profile updated successfully",
            "reset_chat": True
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in sage_chat_onboard: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            "error": "Failed to update profile",
            "message": str(e),
            "success": False
        }), 500

def check_data_completeness(summary):
    """
    Check if a ClimberSummary has all required fields filled out.
    Returns True if all required fields are properly filled out.
    """
    if not summary:
        return False

    required_fields = {
        # Core progression metrics
        'favorite_discipline': ClimbingDiscipline,
        'years_climbing': (int, type(None)),
        
        # Core Context
        'climbing_goals': str,
        'current_training_description': str,
        'interests': (list, type(None)),
        'injury_information': str,
    }
    
    for field, expected_type in required_fields.items():
        value = getattr(summary, field, None)
        
        # Check if value exists
        if value is None:
            current_app.logger.debug(f"Field {field} is None")
            return False
            
        # Handle Enum types
        if isinstance(expected_type, type) and issubclass(expected_type, enum.Enum):
            if not isinstance(value, expected_type):
                current_app.logger.debug(f"Field {field} is not a valid {expected_type.__name__}")
                return False
        # Handle string fields
        elif expected_type == str:
            if not isinstance(value, str) or not value.strip():
                current_app.logger.debug(f"Field {field} is not a valid string")
                return False
        # Handle boolean fields
        elif expected_type == bool:
            if not isinstance(value, bool):
                current_app.logger.debug(f"Field {field} is not a valid boolean")
                return False
        # Handle numeric fields with None option
        elif isinstance(expected_type, tuple) and type(None) in expected_type:
            valid_types = tuple(t for t in expected_type if t is not type(None))
            if value is not None and not isinstance(value, valid_types):
                current_app.logger.debug(f"Field {field} is not a valid numeric type or None")
                return False
        # Handle list fields with None option
        elif isinstance(expected_type, tuple) and list in expected_type:
            if value is not None and not isinstance(value, list):
                current_app.logger.debug(f"Field {field} is not a valid list")
                return False
    
    return True

@main_bp.route("/sage-chat/message", methods=['POST'])
@login_required
@temp_user_check
async def sage_chat_message():
    try:
        # Validate user tier
        if current_user.tier not in VALID_TIERS:
            current_app.logger.error(f"Invalid tier for user {current_user.id}: {current_user.tier}")
            return jsonify({"error": "Invalid subscription tier"}), 400

        # Check daily message limit for basic tier users
        if current_user.tier == 'basic':
            today = date.today()
            
            # Reset counter if it's a new day
            if current_user.last_message_date != today:
                current_user.daily_message_count = 0
                current_user.last_message_date = today
                
            # Check if user has reached daily limit
            if current_user.daily_message_count >= BASIC_TIER_DAILY_MESSAGE_LIMIT:
                return jsonify({
                    "error": "Daily message limit reached",
                    "message": "You've reached your daily message limit. Upgrade to premium for unlimited messages!",
                    "limit_reached": True
                }), 429
                
            # Increment message count
            current_user.daily_message_count += 1
            
            try:
                db.session.commit()
            except SQLAlchemyError as e:
                current_app.logger.error(f"Database error updating message count: {str(e)}")
                db.session.rollback()
                return jsonify({"error": "Error updating message count"}), 500

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        user_prompt = data.get('user_prompt')
        if not user_prompt:
            return jsonify({"error": "Message cannot be empty"}), 400
            
        is_first_message = data.get('is_first_message', False)
        conversation_history = data.get('conversation_history', [])
        custom_context = data.get('custom_context')

        # Initialize services
        v3_client = DeepseekV3Client(api_key=current_app.config['DEEPSEEK_API_KEY'])
        r1_client = R1Client(api_key=current_app.config['DEEPSEEK_API_KEY'])
        context_formatter = ContextFormatter()
        data_integrator = DataIntegrator()

        # Create orchestrator
        orchestrator = ChatOrchestrator(
            db=db.session,
            v3_client=v3_client,
            r1_client=r1_client,
            context_formatter=context_formatter,
            data_integrator=data_integrator
        )

        # Process message
        response = await orchestrator.process_chat_message(
            user_id=str(current_user.id),
            message=user_prompt,
            conversation_history=conversation_history,
            custom_context=custom_context
        )

        # Add message count to response for basic tier users
        if current_user.tier == 'basic':
            messages_remaining = BASIC_TIER_DAILY_MESSAGE_LIMIT - current_user.daily_message_count
            response['messages_remaining'] = messages_remaining

        return jsonify(response)

    except Exception as e:
        current_app.logger.error(f"Error in sage_chat_message: {str(e)}", exc_info=True)
        return jsonify({
            "error": "An error occurred processing your message",
            "details": str(e)
        }), 500

@main_bp.route('/upload', methods=['POST'])
@login_required
@temp_user_check
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400
        
    # Validate user tier
    if current_user.tier not in VALID_TIERS:
        return jsonify({"error": "Invalid subscription tier"}), 400
        
    # Check file size based on user tier
    max_size = 10_000_000 if current_user.tier == 'premium' else 1_000_000  # 10MB for premium, 1MB for basic
    content_length = request.content_length
    if content_length and content_length > max_size:
        return jsonify({
            "error": f"File size exceeds {max_size/1_000_000}MB limit for your tier",
            "tier": current_user.tier
        }), 413
        
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
        return jsonify({
            "success": True, 
            "message": "File uploaded successfully",
            "file_size": len(content),
            "tier_limit": max_size
        })
    except Exception as e:
        current_app.logger.error(f"Error uploading file: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": f"Error uploading file: {str(e)}"}), 500

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

@main_bp.route("/update-climber-summary", methods=['GET', 'POST'])
@login_required
@temp_user_check
def update_climber_summary():
    form = ClimberSummaryForm()
    summary = ClimberSummary.query.get(current_user.id)
    
    if request.method == 'GET':
        if summary:
            # Populate form with existing data
            for field in form._fields:
                if hasattr(summary, field):
                    value = getattr(summary, field)
                    if hasattr(value, 'name'):  # Handle enums
                        form[field].data = value.name
                    else:
                        form[field].data = value
    
    if form.validate_on_submit():
        try:
            # Log all form data for debugging
            current_app.logger.debug("Form Data Submitted:")
            for field_name, field in form._fields.items():
                current_app.logger.debug(f"{field_name}: {field.data}")

            # Create UserInputData from form
            user_input = UserInputData(
                # Core progression metrics
                highest_sport_grade_tried=form.highest_sport_grade_tried.data,
                highest_trad_grade_tried=form.highest_trad_grade_tried.data,
                highest_boulder_grade_tried=form.highest_boulder_grade_tried.data,
                total_climbs=form.total_climbs.data,
                favorite_discipline=form.favorite_discipline.data,
                years_climbing=form.years_climbing.data,
                preferred_crag_last_year=form.preferred_crag_last_year.data,
                
                # Core Context
                climbing_goals=form.climbing_goals.data,
                current_training_description=form.current_training_description.data,
                interests=form.interests.data,
                injury_information=form.injury_information.data,
                additional_notes=form.additional_notes.data,
                
                # Advanced Settings - Training Context
                current_training_frequency=form.current_training_frequency.data,
                typical_session_length=form.typical_session_length.data,
                typical_session_intensity=form.typical_session_intensity.data,
                home_equipment=form.home_equipment.data,
                access_to_commercial_gym=form.access_to_commercial_gym.data,
                supplemental_training=form.supplemental_training.data,
                training_history=form.training_history.data,
                
                # Performance metrics
                highest_grade_sport_sent_clean_on_lead=form.highest_grade_sport_sent_clean_on_lead.data,
                highest_grade_tr_sent_clean=form.highest_grade_tr_sent_clean.data,
                highest_grade_trad_sent_clean_on_lead=form.highest_grade_trad_sent_clean_on_lead.data,
                highest_grade_boulder_sent_clean=form.highest_grade_boulder_sent_clean.data,
                onsight_grade_sport=form.onsight_grade_sport.data,
                onsight_grade_trad=form.onsight_grade_trad.data,
                flash_grade_boulder=form.flash_grade_boulder.data,
                
                # Health and Limitations
                physical_limitations=form.physical_limitations.data,
                
                # Recent Activity
                activity_last_30_days=form.activity_last_30_days.data,
                
                # Style preferences
                favorite_angle=form.favorite_angle.data,
                strongest_angle=form.strongest_angle.data,
                weakest_angle=form.weakest_angle.data,
                favorite_energy_type=form.favorite_energy_type.data,
                strongest_energy_type=form.strongest_energy_type.data,
                weakest_energy_type=form.weakest_energy_type.data,
                favorite_hold_types=form.favorite_hold_types.data,
                strongest_hold_types=form.strongest_hold_types.data,
                weakest_hold_types=form.weakest_hold_types.data,
                
                # Lifestyle
                sleep_score=form.sleep_score.data,
                nutrition_score=form.nutrition_score.data
            )
            
            # Log UserInputData for debugging
            current_app.logger.debug("UserInputData created:")
            current_app.logger.debug(user_input.__dict__)
            
            # Update summary using service
            summary_service = ClimberSummaryService(user_id=current_user.id)
            summary = summary_service.update_summary(user_input=user_input)
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('main.sage_chat'))
            
        except Exception as e:
            current_app.logger.error(f"Error updating climber summary: {str(e)}", exc_info=True)
            flash('Error updating profile. Please try again.', 'danger')
            db.session.rollback()
    else:
        # Log form validation errors if any
        if form.errors:
            current_app.logger.debug("Form Validation Errors:")
            for field_name, errors in form.errors.items():
                current_app.logger.debug(f"{field_name}: {errors}")
                flash(f"Error in {field_name}: {', '.join(errors)}", 'danger')
    
    # If we get here, either it's a GET request or form validation failed
    return redirect(url_for('main.sage_chat'))

@main_bp.route("/create-ticks", methods=['POST'])
@login_required
def create_ticks():
    logger = logging.getLogger(__name__)
    user_id = current_user.id
    
    try:
        data = request.get_json()
        if not data or 'entries' not in data or 'discipline' not in data:
            logger.error("Invalid data format for create_ticks")
            return jsonify({'error': 'Invalid data format'}), 400

        discipline = data['discipline']
        entries = data['entries']
        new_tick_ids = []

        # Reset sequences for both tables
        try:
            db.session.execute(text('SELECT setval(pg_get_serial_sequence(\'user_ticks\', \'id\'), coalesce((SELECT MAX(id) FROM user_ticks), 0) + 1, false)'))
            db.session.execute(text('SELECT setval(pg_get_serial_sequence(\'performance_pyramid\', \'id\'), coalesce((SELECT MAX(id) FROM performance_pyramid), 0) + 1, false)'))
            logger.debug("Reset sequences for user_ticks and performance_pyramid")
        except Exception as e:
            logger.warning(f"Could not reset sequences: {str(e)}")

        # Create all UserTicks first
        new_ticks = []
        for entry in entries:
            # Process grade information
            grade_processor = GradeProcessor()
            route_grade = entry.get('route_grade')
            binned_code = grade_processor.convert_grades_to_codes([route_grade])[0] if route_grade else None
            binned_grade = grade_processor.get_grade_from_code(binned_code) if binned_code else None

            new_tick = UserTicks(
                user_id=user_id,
                route_name=entry.get('route_name', 'Unknown Route'),
                route_grade=route_grade,
                binned_grade=binned_grade,
                binned_code=binned_code,
                tick_date=datetime.strptime(entry.get('send_date', ''), '%Y-%m-%d').date() if entry.get('send_date') else datetime.now().date(),
                location=entry.get('location'),
                location_raw=entry.get('location'),
                discipline=ClimbingDiscipline[discipline],
                send_bool=True,
                length=entry.get('length', 0),
                notes=entry.get('description')
            )
            new_ticks.append(new_tick)
            db.session.add(new_tick)
        
        # Flush to get IDs for the new ticks
        db.session.flush()
        
        # Now create PerformancePyramid entries
        for tick, entry in zip(new_ticks, entries):
            pyramid_entry = PerformancePyramid(
                user_id=user_id,
                tick_id=tick.id,
                send_date=tick.tick_date,
                location=tick.location,
                binned_code=tick.binned_code,
                num_attempts=entry.get('num_attempts', 1),
                days_attempts=entry.get('days_tried', 1),
                description=entry.get('description'),
                crux_angle=CruxAngle(entry.get('crux_angle')) if entry.get('crux_angle') else None,
                crux_energy=CruxEnergyType(entry.get('crux_energy')) if entry.get('crux_energy') else None
            )
            db.session.add(pyramid_entry)
            new_tick_ids.append(tick.id)

        db.session.commit()
        logger.info(f"Created {len(new_tick_ids)} new ticks and pyramid entries for user {user_id}")
        return jsonify(new_tick_ids)

    except Exception as e:
        logger.error(f"Error creating ticks: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500




