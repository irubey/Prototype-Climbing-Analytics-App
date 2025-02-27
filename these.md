General Context Questions

    Application Purpose and Audience: What is the primary goal of your climbing analytics application, and who are the target users (e.g., casual climbers, competitive climbers, coaches)?
    The application is meant to serve as a tool for climbers to analyze their climbing history and performance. This is achieved by displaying interactive data visualizations if the climber has uploaded data, the paid tiers are meant to unlock the ability to chat with a context aware AI coach and the ability to upload more data.

    Scalability Requirements: How many users do you expect to serve initially, and what’s the anticipated growth over the next year or two? Are there specific performance requirements (e.g., response time under 200ms)?
    The application is meant to be used by a wide range of climbers, from casual climbers to competitive climbers and coaches. I expect the application to grow over the next year or two as more climbers discover it and as it becomes more integrated into the climbing community. 10,000 users is a good starting point.

    Security and Compliance: Are there specific security standards (e.g., GDPR, HIPAA) or data privacy requirements you need to meet, especially for user profile and payment data?
    The application is not meant to handle sensitive data, it is meant to be a tool for climbers to analyze their climbing history and performance.

    Error Handling: How should the API handle errors (e.g., standardized error responses with codes and messages)? Are there specific user-facing messages you’d like for certain scenarios?
    There are standardized error responses for the API in app/core/exceptions.py and app/core/error_handlers.py

    Versioning: Do you plan to version your API (e.g., /v1/users/me), and if so, how should versioning impact these endpoints?
    The API is versioned to v1.

Profile Management Endpoints
GET /users/me

    Response Data: What specific fields from the User model should be returned (e.g., username, email, tier, etc.)? Should sensitive fields like hashed_password or stripe_customer_id be excluded?
    The response data should include the following fields:
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    tier: Mapped[UserTier] = mapped_column(SQLEnum(UserTier), default=UserTier.FREE)
    payment_status: Mapped[PaymentStatus] = mapped_column(SQLEnum(PaymentStatus), default=PaymentStatus.INACTIVE)
    daily_message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    mtn_project_last_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    eight_a_last_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    Access Control: Should this endpoint be accessible only to authenticated users, or are there scenarios where additional permissions (e.g., admin access) are required?
    This endpoint is accessible only to authenticated users.
    Caching: Would you like response caching for this endpoint to reduce database load, and if so, how long should the cache persist?
    There should be response caching for this endpoint if it makes sense. Lean more towards not caching if possible.

PATCH /users/me

    Updatable Fields: Which fields in the User model can users modify (e.g., username, email, mountain_project_url)? Are there fields that should be immutable or require special validation (e.g., email uniqueness)?
    The following fields can be updated by the user: username, email, password, mountain_project_url, eight_a_nu_url

    Validation Rules: What validation rules apply (e.g., max length for username, valid URL format for mountain_project_url)?
    Yes use Pydantic to validate the data.


    Side Effects: Should updating certain fields trigger additional actions (e.g., re-syncing Mountain Project data if mountain_project_url changes)?
    Yes, updating the mountain_project_url or eight_a_nu_url should trigger a background task to re-sync the data.

POST /users/me/change-password

    Input Requirements: What data should the request body include (e.g., old password, new password, confirmation)? Should the new password meet specific complexity requirements?
    The request body should include the following fields: old_password, new_password, confirmation
    Yes, the new password should meet specific complexity requirements.

    Security Measures: Should this endpoint log the change or notify the user via email? How should it handle brute-force attempts?
    This endpoint should log the change and notify the user via email. It should also handle brute-force attempts by limiting the number of attempts. email config is in app/core/email.py

    Session Impact: Should changing the password invalidate existing JWT tokens or refresh tokens?
    Yes, changing the password should invalidate existing JWT tokens and refresh tokens.

Account Management Endpoints
POST /users/me/deactivate

    Deactivation Behavior: What does “deactivate” mean in your system? Does it set is_active to False, delete data, or mark the account for later deletion? its a soft delete.
    Reversibility: Can a deactivated account be reactivated, and if so, how (e.g., via admin action or user request)?
    Yes, a deactivated account can be reactivated by the user via the login endpoint.
    Side Effects: Should deactivation cancel an active Stripe subscription or revoke tokens? What happens to related data like chat_histories or performance_pyramids?
    Yes, deactivation should cancel an active Stripe subscription and revoke tokens.

Subscription Management Endpoints
GET /users/me/subscription

    Response Data: What subscription details should be returned (e.g., tier, payment_status, stripe_subscription_id, renewal date)? Should it include Stripe-specific data like the next billing date?
    The response data should include the following fields: tier, payment_status, stripe_subscription_id, renewal_date
    Yes, it should include Stripe-specific data like the next billing date.
    Stripe Integration: Should this endpoint fetch real-time data from Stripe, or rely on locally stored data (e.g., last_payment_check)?
    This endpoint should fetch real-time data from Stripe.
    Error Scenarios: How should it handle cases where the subscription data is out of sync with Stripe (e.g., webhook delay)?
    This endpoint should handle cases where the subscription data is out of sync with Stripe by fetching the latest data from Stripe.

POST /users/me/subscribe

    Input Requirements: What data should the request body include (e.g., desired tier)? Should it redirect to a Stripe checkout session or handle payment internally?
    The request body should include the following fields: desired_tier
    Yes, it should redirect to a Stripe checkout session.
    Tier Transitions: How should transitions between tiers work (e.g., free → basic, basic → premium)? Are upgrades/downgrades immediate or queued until the next billing cycle?
    Upgrades and downgrades should be immediate.
    Failure Handling: What happens if Stripe payment fails (e.g., retry logic, user notification)?
    If the payment fails, the user should be notified and the subscription should not be updated.

POST /users/me/cancel-subscription

    Cancellation Behavior: Does cancellation take effect immediately or at the end of the billing period? How should tier and payment_status update?
    Cancellation should take effect immediately.
    Stripe Integration: Should this endpoint call Stripe to cancel the subscription, or rely on webhook events?
    This endpoint should call Stripe to cancel the subscription.
    Post-Cancellation: What features should remain accessible after cancellation (e.g., free tier functionality)?
    The free tier functionality should remain accessible after cancellation.

Usage Tracking Endpoints
GET /users/me/message-count

    Response Data: Should this return just daily_message_count, or include additional context like last_message_date and the maximum allowed messages for the user’s tier?
    The response data should include the following fields: daily_message_count, last_message_date, max_daily_messages
    Time Window: Is the “daily” count strictly 24 hours from midnight UTC, or a rolling 24-hour window? Should it support querying historical usage?
    Rolling 24-hour window.
    Tier Restrictions: How should the response differ for free vs. paid users (e.g., include a “remaining messages” field for paid tiers)?
    The response should differ for free vs. paid users (e.g., include a “remaining messages” field for paid tiers).

Technical Implementation Details

    Database Transactions: Are there endpoints where atomicity is critical (e.g., subscription changes affecting tier and payment_status)? Should rollback occur on failure?
    Yes, there are endpoints where atomicity is critical. Db sessions are handled with a dependency.
    Dependencies: Are there additional FastAPI dependencies (e.g., get_current_active_user) or middleware (e.g., rate limiting) you want applied to these endpoints?
    Yes, there are additional FastAPI dependencies and middleware.
    Background Tasks: Should any endpoints trigger asynchronous tasks (e.g., syncing climbing data, sending confirmation emails)?
    Yes, there are endpoints that trigger asynchronous tasks.
    Logging: What level of logging is needed for each endpoint (e.g., info for successful requests, errors for failures)? Are there specific metrics to track (e.g., subscription changes)?
    Yes, there are specific metrics to track (e.g., subscription changes).
    Testing Requirements: What test cases should be prioritized (e.g., edge cases like invalid tokens, concurrent subscription changes)?
    Yes, there are test cases for edge cases like invalid tokens, concurrent subscription changes.
