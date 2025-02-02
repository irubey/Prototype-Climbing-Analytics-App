import os
import stripe
from app.models import User
from app import db
from flask import current_app

def handle_checkout_session(session):
    """Process completed checkout session and activate user subscription"""
    try:
        current_app.logger.debug(f"Processing checkout session: {session.id}")
        
        # Get customer email, handling both live and test mode
        customer_email = session.get('customer_details', {}).get('email')
        if not customer_email and 'livemode' not in session:
            customer_email = session.get('customer_email')  # Fallback for test mode
            
        if not customer_email:
            current_app.logger.error("No customer email found in session")
            return False
            
        current_app.logger.debug(f"Looking up user with email: {customer_email}")
        user = User.query.filter_by(email=customer_email).first()
        
        if user:
            current_app.logger.info(f"Found user {user.id} for email {customer_email}")
            # Store Stripe customer ID if not already set
            if not user.stripe_customer_id:
                user.stripe_customer_id = session.get('customer')
                
            # Update subscription details
            subscription_id = session.get('subscription')
            if subscription_id:
                user.stripe_subscription_id = subscription_id
                user.tier = get_tier_from_subscription(subscription_id)
                
            user.payment_status = 'active'
            user.stripe_webhook_verified = True
            
            db.session.commit()
            current_app.logger.info(f"Successfully updated user {user.id} subscription details")
            return True
            
        current_app.logger.error(f"No user found for email: {customer_email}")
        return False
        
    except Exception as e:
        current_app.logger.error(f"Checkout session error: {str(e)}", exc_info=True)
        db.session.rollback()
        return False

def handle_subscription_update(subscription):
    """Update user tier and status based on subscription changes"""
    user = User.query.filter_by(stripe_subscription_id=subscription.id).first()
    if user:
        user.tier = get_tier_from_subscription(subscription.id)
        user.payment_status = subscription.status
        db.session.commit()

def handle_subscription_cancellation(subscription):
    """Handle subscription cancellation and downgrade user"""
    user = User.query.filter_by(stripe_subscription_id=subscription.id).first()
    if user:
        user.payment_status = 'canceled'
        user.tier = 'basic'
        db.session.commit()

def handle_payment_failure(invoice):
    """Update user status for failed payments"""
    customer_id = invoice['customer']
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    
    if user:
        user.payment_status = 'past_due'
        db.session.commit()

def get_tier_from_subscription(subscription_id):
    """Determine user tier from Stripe subscription data"""
    subscription = stripe.Subscription.retrieve(subscription_id)
    price_id = subscription['items']['data'][0]['price']['id']
    return 'premium' if price_id == os.getenv('STRIPE_PRICE_ID_PREMIUM') else 'basic'

def handle_invoice_payment_succeeded(invoice):
    """Update user status on a successful recurring invoice payment."""
    try:
        customer_id = invoice['customer']
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            # Confirm that the subscription is in a good state
            user.payment_status = 'active'
            db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Invoice payment succeeded handler error: {str(e)}")
        db.session.rollback()

def handle_subscription_created(subscription):
    """Handle new subscription creation and initialization."""
    try:
        # Get customer details
        customer_id = subscription.get('customer')
        if not customer_id:
            current_app.logger.error("No customer ID in subscription")
            return False
            
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if not user:
            current_app.logger.error(f"No user found for customer ID: {customer_id}")
            return False
            
        # Update subscription details
        user.stripe_subscription_id = subscription.get('id')
        user.payment_status = subscription.get('status', 'active')
        user.tier = get_tier_from_subscription(subscription.get('id'))
        
        db.session.commit()
        current_app.logger.info(f"Successfully initialized subscription for user {user.id}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Subscription creation error: {str(e)}", exc_info=True)
        db.session.rollback()
        return False
