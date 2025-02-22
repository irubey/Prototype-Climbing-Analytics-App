"""
Payment and subscription schemas.

This module defines Pydantic models for:
- Stripe integration
- Payment processing
- Subscription management
- Billing operations
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, UUID4, HttpUrl, model_validator
from app.models.enums import UserTier, PaymentStatus

class StripeCheckoutSession(BaseModel):
    """Schema for Stripe checkout session response."""
    checkout_session_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Stripe checkout session ID"
    )
    checkout_url: HttpUrl = Field(
        ...,
        description="Checkout session URL"
    )
    tier: UserTier = Field(
        ...,
        description="Selected subscription tier"
    )
    expires_at: datetime = Field(
        ...,
        description="Session expiration timestamp"
    )


    @model_validator(mode="after")
    def validate_expiration(self) -> "StripeCheckoutSession":
        """Validate session expiration."""
        if self.expires_at < datetime.now(timezone.utc):
            raise ValueError("Session has already expired")
        return self

class StripeWebhookEvent(BaseModel):
    """Schema for Stripe webhook event data."""
    id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Stripe event ID"
    )
    type: str = Field(
        ...,
        pattern=r"^(checkout|subscription|invoice|payment|customer)\.",
        description="Event type"
    )
    data: Dict[str, Any] = Field(
        ...,
        description="Event data payload"
    )
    created: datetime = Field(
        ...,
        description="Event creation timestamp"
    )
    api_version: Optional[str] = Field(
        None,
        max_length=20,
        description="Stripe API version"
    )
    pending_webhooks: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Number of pending webhooks"
    )
    request_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Request ID"
    )



class PaymentDetails(BaseModel):
    """Schema for subscription payment details."""
    user_id: UUID4 = Field(
        ...,
        description="User ID"
    )
    tier: UserTier = Field(
        ...,
        description="User subscription tier"
    )
    status: PaymentStatus = Field(
        ...,
        description="Payment status"
    )
    stripe_customer_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Stripe customer ID"
    )
    stripe_subscription_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Stripe subscription ID"
    )
    current_period_start: Optional[datetime] = Field(
        None,
        description="Subscription period start date"
    )
    current_period_end: Optional[datetime] = Field(
        None,
        description="Subscription period end date"
    )
    cancel_at_period_end: bool = Field(
        False,
        description="Whether subscription will cancel at period end"
    )
    canceled_at: Optional[datetime] = Field(
        None,
        description="When subscription was canceled"
    )
    trial_end: Optional[datetime] = Field(
        None,
        description="Trial period end date"
    )
    last_payment_status: Optional[str] = Field(
        None,
        pattern="^(succeeded|failed|pending|canceled)$",
        description="Status of last payment attempt"
    )
    last_payment_error: Optional[str] = Field(
        None,
        max_length=500,
        description="Error message from last failed payment"
    )



    @model_validator(mode="after")
    def validate_dates(self) -> "PaymentDetails":
        """Validate subscription date relationships."""
        if (self.current_period_start and self.current_period_end and 
            self.current_period_start > self.current_period_end):
            raise ValueError("Period start cannot be after period end")
        if (self.canceled_at and self.current_period_start and 
            self.canceled_at < self.current_period_start):
            raise ValueError("Cancellation cannot be before period start")
        if (self.trial_end and self.current_period_start and 
            self.trial_end < self.current_period_start):
            raise ValueError("Trial end cannot be before period start")
        return self

class PricingInfo(BaseModel):
    """Schema for tier pricing information."""
    tier: UserTier = Field(
        ...,
        description="Subscription tier"
    )
    price_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Stripe price ID"
    )
    price: str = Field(
        ...,
        pattern=r"^\$\d+(\.\d{2})?$",
        description="Price in USD",
        examples=["$9.99", "$29.99"]
    )
    interval: str = Field(
        ...,
        pattern="^(month|year)$",
        description="Billing interval"
    )
    features: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of tier features"
    )
    recommended: bool = Field(
        False,
        description="Whether this is the recommended tier"
    )
    trial_days: Optional[int] = Field(
        None,
        ge=0,
        le=90,
        description="Number of trial days available"
    )


class SubscriptionUpdate(BaseModel):
    """Schema for updating subscription settings."""
    cancel_at_period_end: Optional[bool] = Field(
        None,
        description="Set to true to cancel at period end"
    )
    new_tier: Optional[UserTier] = Field(
        None,
        description="New tier to upgrade/downgrade to"
    )
    proration_behavior: Optional[str] = Field(
        None,
        pattern="^(create_prorations|none|always_invoice)$",
        description="How to handle proration"
    )

class PaymentMethodUpdate(BaseModel):
    """Schema for updating payment method."""
    payment_method_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="New Stripe payment method ID"
    )
    set_as_default: bool = Field(
        True,
        description="Whether to set as default payment method"
    )

class BillingPortalSession(BaseModel):
    """Schema for customer billing portal session."""
    portal_url: HttpUrl = Field(
        ...,
        description="URL to billing portal"
    )
    expires_at: datetime = Field(
        ...,
        description="Session expiration timestamp"
    )



    @model_validator(mode="after")
    def validate_expiration(self) -> "BillingPortalSession":
        """Validate session expiration."""
        if self.expires_at < datetime.now(timezone.utc):
            raise ValueError("Session has already expired")
        return self 