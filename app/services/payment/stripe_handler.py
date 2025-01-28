import os
import stripe
from app.models import User
from app import db
from flask import current_app

def handle_checkout_session(session):
    """Process completed checkout session and activate user subscription"""
    try:
        customer_email = session['customer_details']['email']
        user = User.query.filter_by(email=customer_email).first()
        
        if user:
            user.stripe_customer_id = session['customer']
            user.payment_status = 'active'
            user.stripe_subscription_id = session['subscription']
            user.tier = get_tier_from_subscription(session['subscription'])
            db.session.commit()
            return True
            
        current_app.logger.error(f"No user found for email: {customer_email}")
        return False
        
    except Exception as e:
        current_app.logger.error(f"Checkout session error: {str(e)}")
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
