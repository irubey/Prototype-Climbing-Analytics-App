# User Service for SendSage Climbing Analytics - Product Requirements Document (PRD)

**Date**: February 23, 2025  
**Author**: Grok 3 (xAI)

## Overview and Objectives

The user service is a core component of SendSage's FastAPI-based backend, powering a climbing analytics application that helps climbers analyze their performance through data visualizations and AI-driven coaching. This service manages user profiles, account status, Stripe subscriptions, and usage tracking for AI interactions, supporting a seamless experience across free, Basic, and Premium tiers. Integrated with OAuth2/JWT authentication and Stripe payments, it ensures secure, scalable access for an initial 10,000 users, with projected growth over the next 1-2 years.

### Objectives

- Provide climbers with intuitive profile management and secure password updates
- Enable reversible account deactivation and real-time subscription management
- Track AI coaching usage with tier-specific limits, enhancing user engagement
- Scale to support 10,000 users with <500ms response times, ensuring reliability

## Use Cases and User Scenarios

### Profile Management

**Scenario**: Alex, a new climber, logs in and retrieves their profile via `GET /v1/users/me`, seeing their free tier status and last login. They update their email and Mountain Project URL via `PATCH /v1/users/me`, triggering a data sync.

**Requirement**: Retrieve all non-sensitive fields; allow updates to username, email, and climbing URLs with validation.

**Scenario**: Alex changes their password via `POST /v1/users/me/change-password` after forgetting it, receiving an email confirmation and logging in anew.

**Requirement**: Secure password updates with complexity checks, token invalidation, and notifications.

### Account Management

**Scenario**: Jane, a casual climber, deactivates her account via `POST /v1/users/me/deactivate` after a break, later reactivating it by logging in.

**Requirement**: Soft delete with Stripe cancellation and token revocation, reversible via login.

### Subscription Management

**Scenario**: Mark, a competitive climber, checks his Basic tier details via `GET /v1/users/me/subscription`, upgrades to Premium via `POST /v1/users/me/subscribe`, and cancels it later via `POST /v1/users/me/cancel-subscription`, reverting to free tier features.

**Requirement**: Real-time Stripe data retrieval, immediate tier transitions, and free tier access post-cancellation.

### Usage Tracking

**Scenario**: Jane (free tier) checks her message count via `GET /v1/users/me/message-count` and sees 0 max messages, while Mark (Premium) sees unlimited remaining messages after 10 uses.

**Requirement**: Rolling 24-hour counts with tier-specific limits and remaining message visibility.

### Edge Cases

- **Invalid Token**: Alex uses an expired JWT; sees "Unauthorized—please log in again."
- **Subscription Sync Failure**: Mark's Stripe data lags; `GET /v1/users/me/subscription` fetches real-time data to correct it.
- **Brute-Force Password Attempts**: Jane tries 6 password changes in a minute; sees "Too many attempts—wait 60 seconds."

## Detailed Functional Requirements

### user/ Service

#### Purpose

Manage user profiles, accounts, subscriptions, and AI usage tracking, integrating with authentication and Stripe for a cohesive experience.

#### Endpoints

##### GET /v1/users/me

- **Purpose**: Retrieve the authenticated user's profile
- **Auth**: JWT with user scope (via get_current_active_user)
- **Response**:

```json
{
  "username": "alex_climber",
  "email": "alex@example.com",
  "is_active": true,
  "is_superuser": false,
  "tier": "free",
  "payment_status": "inactive",
  "daily_message_count": 0,
  "last_message_date": null,
  "mtn_project_last_sync": null,
  "eight_a_last_sync": null,
  "created_at": "2025-02-23T10:00:00Z",
  "updated_at": null,
  "last_login": "2025-02-23T10:05:00Z"
}
```

- **Errors**:
  - 401: `{"detail": "Invalid token"}`
  - 403: `{"detail": "Inactive user"}`

##### PATCH /v1/users/me

- **Purpose**: Update user profile fields
- **Auth**: JWT with user scope
- **Request**:

```json
{
  "email": "alex.new@example.com",
  "mountain_project_url": "https://mountainproject.com/user/alex"
}
```

- **Validation**: Pydantic checks (e.g., email format, URL validity, uniqueness)
- **Response**: Updated profile (same as GET)
- **Side Effect**: Background task for mountain_project_url/eight_a_nu_url sync via LogbookOrchestrator
- **Errors**:
  - 400: `{"detail": "Email already in use"}`

##### POST /v1/users/me/change-password

- **Purpose**: Update user password securely
- **Auth**: JWT with user scope
- **Request**:

```json
{
  "old_password": "OldPass123!",
  "new_password": "NewPass456#",
  "confirmation": "NewPass456#"
}
```

- **Validation**: Complexity (8+ chars, uppercase, number, special); match confirmation
- **Response**: `{"message": "Password updated successfully"}`
- **Side Effects**:
  - Log change (INFO)
  - Email notification (app/core/email.py)
  - Revoke tokens (RevokedToken)
- **Errors**:
  - 400: `{"detail": "Passwords don't match"}`
  - 429: `{"detail": "Too many attempts"}` (5/min via Redis)

##### POST /v1/users/me/deactivate

- **Purpose**: Soft-delete user account
- **Auth**: JWT with user scope
- **Request**: None
- **Response**: `{"message": "Account deactivated successfully"}`
- **Behavior**: Set is_active=False, cancel Stripe subscription, revoke tokens
- **Errors**:
  - 401: `{"detail": "Invalid token"}`

##### GET /v1/users/me/subscription

- **Purpose**: Retrieve subscription details with Stripe sync
- **Auth**: JWT with user scope
- **Response**:

```json
{
  "tier": "basic",
  "payment_status": "active",
  "stripe_subscription_id": "sub_123",
  "renewal_date": "2025-03-23T00:00:00Z",
  "next_billing_date": "2025-03-23T00:00:00Z"
}
```

- **Behavior**: Fetch real-time Stripe data
- **Errors**:
  - 502: `{"detail": "Stripe unavailable"}`

##### POST /v1/users/me/subscribe

- **Purpose**: Initiate a subscription
- **Auth**: JWT with user scope
- **Request**:

```json
{
  "desired_tier": "premium"
}
```

- **Response**: `{"checkout_session_id": "cs_456"}`
- **Behavior**: Immediate tier change on Stripe success
- **Errors**:
  - 400: `{"detail": "Active subscription exists"}`

##### POST /v1/users/me/cancel-subscription

- **Purpose**: Cancel active subscription
- **Auth**: JWT with user scope
- **Request**: None
- **Response**: `{"message": "Subscription cancelled successfully"}`
- **Behavior**: Call Stripe to cancel, set tier=free, payment_status=cancelled
- **Errors**:
  - 400: `{"detail": "No active subscription"}`

##### GET /v1/users/me/message-count

- **Purpose**: Track AI coaching usage
- **Auth**: JWT with user scope
- **Response**:

```json
{
  "daily_message_count": 5,
  "last_message_date": "2025-02-23T12:00:00Z",
  "max_daily_messages": 25,
  "remaining_messages": 20
}
```

- **Behavior**: Rolling 24-hour window; remaining_messages for paid tiers only
- **Errors**:
  - 401: `{"detail": "Invalid token"}`

## Non-Functional Requirements

### Performance

- Target <500ms response time for all endpoints
- Stripe calls: <1s latency

### Scalability

- Support 10,000 users with async SQLAlchemy sessions and Redis

### Security

- JWT authentication for all endpoints
- Rate limit password changes (5/min via Redis)
- TLS/HTTPS for API calls

### Monitoring

- Log successes (INFO), failures (ERROR), subscription changes
- Alerts: >5% error rate, latency >1s

### Integration

- With auth/: Use get_current_active_user
- With Stripe: Real-time subscription sync
- With context/logbook: Background sync for climbing URLs

### Testing

- Unit Tests: Validation, token revocation, Stripe mocks
- Integration Tests: Profile updates with sync, subscription transitions
- Edge Cases: Invalid tokens, concurrent cancellations

## Implementation Plan

### Project Overview

- **Goal**: Deliver a robust user service for profile, account, subscription, and usage management
- **Timeline**: March 1, 2025 - April 11, 2025 (6 weeks, 5 sprints)
- **Team**:
  - Backend Developer 1 (BD1): API endpoints, Stripe integration
  - Backend Developer 2 (BD2): Background tasks, database logic
  - QA Engineer (QA): Testing and validation
  - DevOps Engineer (DE): Monitoring, scalability setup
- **Assumptions**:
  - Existing auth/ and Stripe systems are functional
  - LogbookOrchestrator handles climbing data sync

### Sprint Breakdown

#### Sprint 1: Profile Management (March 1 - March 7)

- **Goal**: Implement GET and PATCH /v1/users/me
- **Tasks**:
  - BD1: GET endpoint (2 days, Mar 1-2)
  - BD1: PATCH endpoint with Pydantic (2 days, Mar 3-4)
  - BD2: Background sync task (2 days, Mar 3-4)
  - QA: Unit tests (2 days, Mar 6-7)
- **Deliverables**: Functional profile retrieval and updates

#### Sprint 2: Password and Account Management (March 8 - March 14)

- **Goal**: Add password change and deactivation
- **Tasks**:
  - BD1: POST /change-password with security (3 days, Mar 8-10)
  - BD1: POST /deactivate with Stripe call (2 days, Mar 11-12)
  - QA: Integration tests (2 days, Mar 13-14)
- **Deliverables**: Secure password updates, account deactivation

#### Sprint 3: Subscription Management (March 15 - March 21)

- **Goal**: Implement subscription endpoints
- **Tasks**:
  - BD1: GET /subscription with Stripe sync (2 days, Mar 15-16)
  - BD1: POST /subscribe (2 days, Mar 17-18)
  - BD1: POST /cancel-subscription (2 days, Mar 19-20)
  - QA: Tests (2 days, Mar 20-21)
- **Deliverables**: Full subscription lifecycle

#### Sprint 4: Usage Tracking and Polish (March 22 - March 28)

- **Goal**: Add message count and refine endpoints
- **Tasks**:
  - BD1: GET /message-count (2 days, Mar 22-23)
  - BD2: Logging and error handling (2 days, Mar 24-25)
  - QA: Edge case tests (2 days, Mar 27-28)
- **Deliverables**: Usage tracking, polished service

#### Sprint 5: Deployment and Monitoring (March 29 - April 4)

- **Goal**: Deploy and ensure scalability
- **Tasks**:
  - DE: Redis setup, load balancing (3 days, Mar 29-31)
  - QA: Performance tests (10,000 users, 2 days, Apr 1-2)
  - BD1: Final tweaks (2 days, Apr 3-4)
- **Deliverables**: Production-ready service

## Conclusion

This PRD outlines a scalable, user-focused user service for SendSage, delivering secure profile management, flexible subscriptions, and usage tracking. Aligned with your climbing analytics vision, it ensures a robust experience for 10,000+ climbers.
