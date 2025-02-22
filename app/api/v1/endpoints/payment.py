from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import stripe
from datetime import datetime, timezone

from app.core.auth import (
    get_current_active_user,
)
from app.core.logging import logger
from app.core import settings
from app.db.session import get_db
from app.models import User
from app.schemas.auth import UserTier, PaymentStatus
from app.schemas.payment import (
    StripeCheckoutSession,
    StripeWebhookEvent,
    PaymentDetails,
    PricingInfo
)

router = APIRouter()
stripe.api_key = settings.STRIPE_API_KEY

PRICING_INFO = {
    "basic": {
        "price": "$9.99",
        "features": [
            "Everything in Free Tier",
            "AI Coaching Chat (25 Daily Messages)",
            "Enhanced Performance Analysis",
            "1MB File Uploads"
        ]
    },
    "premium": {
        "price": "$29.99",
        "features": [
            "Everything in Basic Tier",
            "Unlimited AI Coaching Chat",
            "Advanced Reasoning, Analysis, and Recommendations",
            "10MB File Uploads"
        ]
    }
}

@router.get("/pricing", response_model=Dict[str, PricingInfo])
async def get_pricing_info() -> Any:
    """Get pricing information for all tiers."""
    return PRICING_INFO

@router.post("/create-checkout-session", response_model=StripeCheckoutSession)
async def create_checkout_session(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    tier: UserTier
) -> Any:
    """Create Stripe checkout session for subscription."""
    # Check if user already has active subscription
    if current_user.payment_status == PaymentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has active subscription"
        )

    try:
        price_id = settings.STRIPE_PRICE_ID_PREMIUM if tier == UserTier.PREMIUM else settings.STRIPE_PRICE_ID_BASIC
        if not price_id:
            raise ValueError(f"No price ID found for tier: {tier}")
        
        # Create or get Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={"user_id": str(current_user.id)}
            )
            current_user.stripe_customer_id = customer.id
            db.add(current_user)
            await db.commit()
        
        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1
            }],
            mode="subscription",
            success_url=f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/payment/cancel",
            metadata={
                "user_id": str(current_user.id),
                "tier": tier
            }
        )
        
        return {"checkout_session_id": session.id}
        
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create checkout session"
        )

@router.post("/webhook", response_model=Dict[str, str])
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Handle Stripe webhook events."""
    try:
        body = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        try:
            event = stripe.Webhook.construct_event(
                body, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(
                "Invalid webhook payload",
                extra={
                    "error": str(e),
                    "error_type": "ValueError"
                }
            )
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.SignatureVerificationError as e:
            logger.error(
                "Invalid webhook signature",
                extra={
                    "error": str(e),
                    "error_type": "SignatureVerificationError"
                }
            )
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Process the event
        if event.type == "customer.subscription.updated":
            background_tasks.add_task(
                handle_subscription_update,
                db=db,
                subscription=event.data.object
            )
        elif event.type == "customer.subscription.deleted":
            background_tasks.add_task(
                handle_subscription_cancellation,
                db=db,
                subscription=event.data.object
            )
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(
            "Error processing webhook",
            extra={
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing webhook"
        )

async def handle_checkout_session(
    db: AsyncSession,
    session: Dict[str, Any],
    background_tasks: BackgroundTasks
) -> bool:
    """Handle successful checkout session completion."""
    try:
        user_id = session.get("metadata", {}).get("user_id")
        tier = session.get("metadata", {}).get("tier")
        
        result = await db.execute(
            select(User).filter(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.stripe_subscription_id = session.get("subscription")
            user.tier = tier
            user.payment_status = PaymentStatus.ACTIVE
            user.stripe_webhook_verified = True
            user.last_payment_check = datetime.now(timezone.utc)
            
            db.add(user)
            await db.commit()
            
            background_tasks.add_task(
                setup_subscription_features,
                user.id,
                tier
            )
            return True
        return False
    except Exception as e:
        logger.error(f"Error handling checkout session: {e}")
        return False

async def handle_subscription_update(
    db: AsyncSession,
    subscription: Dict[str, Any]
) -> None:
    """Handle subscription updates."""
    try:
        result = await db.execute(
            select(User).filter(User.stripe_subscription_id == subscription.get("id"))
        )
        user = result.scalar_one_or_none()
        
        if user:
            status = subscription.get("status")
            if status == "active":
                user.payment_status = PaymentStatus.ACTIVE
            elif status == "canceled":
                user.payment_status = PaymentStatus.CANCELLED
            
            db.add(user)
            await db.commit()
    except Exception as e:
        logger.error(f"Error handling subscription update: {e}")

async def handle_subscription_cancellation(
    db: AsyncSession,
    subscription: Dict[str, Any]
) -> None:
    """Handle subscription cancellation."""
    try:
        result = await db.execute(
            select(User).filter(User.stripe_subscription_id == subscription.get("id"))
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.tier = UserTier.FREE
            user.payment_status = PaymentStatus.CANCELLED
            user.stripe_subscription_id = None
            
            db.add(user)
            await db.commit()
    except Exception as e:
        logger.error(f"Error handling subscription cancellation: {e}")

async def handle_payment_failure(
    db: AsyncSession,
    invoice: Dict[str, Any]
) -> None:
    """Handle failed payment."""
    try:
        subscription_id = invoice.get("subscription")
        result = await db.execute(
            select(User).filter(User.stripe_subscription_id == subscription_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.payment_status = PaymentStatus.INACTIVE
            db.add(user)
            await db.commit()
    except Exception as e:
        logger.error(f"Error handling payment failure: {e}")

async def handle_invoice_payment_succeeded(
    db: AsyncSession,
    invoice: Dict[str, Any]
) -> None:
    """Handle successful invoice payment."""
    try:
        subscription_id = invoice.get("subscription")
        result = await db.execute(
            select(User).filter(User.stripe_subscription_id == subscription_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.payment_status = PaymentStatus.ACTIVE
            user.last_payment_check = datetime.now(timezone.utc)
            db.add(user)
            await db.commit()
    except Exception as e:
        logger.error(f"Error handling invoice payment success: {e}")

async def handle_subscription_created(
    db: AsyncSession,
    subscription: Dict[str, Any]
) -> None:
    """Handle new subscription creation."""
    try:
        customer_id = subscription.get("customer")
        result = await db.execute(
            select(User).filter(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.stripe_subscription_id = subscription.get("id")
            user.payment_status = PaymentStatus.ACTIVE
            db.add(user)
            await db.commit()
    except Exception as e:
        logger.error(f"Error handling subscription creation: {e}")

async def setup_subscription_features(user_id: str, tier: str) -> None:
    """Background task to setup additional features after subscription."""
    # TODO: Implement any post-subscription setup
    pass 