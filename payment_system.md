# Payment System Documentation - SendSage

This document details the **payment system architecture** for SendSage. The system integrates with **Stripe** to handle subscriptions, payment processing, and related webhook events. The design ensures a scalable and maintainable approach while adhering to best practices in Flask development.

---

## 1. Setup

Before running the payment system, ensure that all required environment variables are set:

- **STRIPE_PUBLIC_KEY**: Public key for Stripe checkout.
- **STRIPE_PRICE_ID_BASIC**: Price ID for the basic tier.
- **STRIPE_PRICE_ID_PREMIUM**: Price ID for the premium tier.
- **STRIPE_WEBHOOK_SECRET**: Webhook secret for verifying Stripe events.

Additionally, initialize the Stripe library with your secret key (configured in your app's settings). The environment must contain these values for secure operation. Ensure the Flask app includes proper error logging if any Stripe configuration is missing.

---

## 2. Implementation

### Payment Checkout Flow

When a user navigates to the `/payment` endpoint:

- The system verifies if the user's payment status is not already active.
- Depending on the query parameter (defaulting to **basic**), the page displays tier options with details (free, basic, premium).
- On form submission via `POST`, the system retrieves the appropriate **price_id** (using the environment variables) and creates a **Stripe Checkout Session** with:
  - Supported payment methods (card)
  - Line items containing the plan details
  - Mode set to `"subscription"`
  - Success and cancel URLs configured with `url_for`
  - Customer email passed in for identification

The user is then redirected to the Stripe checkout page where payment is processed.

### Post-Payment Flow

Once payment is successfully processed, Stripe redirects the user to the `/payment/success` page. Here:

- The app updates the user's payment status to `pending_verification` immediately.
- The actual activation is subsequently updated via the Stripe webhook.

### Webhook Integration

The `/stripe-webhook` endpoint validates incoming events from **Stripe**. Key event types include:

- **checkout.session.completed** and **checkout.session.async_payment_succeeded**:  
  The corresponding handler (`handle_checkout_session`) locates the user by email, updates attributes such as `stripe_customer_id`, `stripe_subscription_id`, sets the user's payment status to `active`, and uses the function `get_tier_from_subscription` to determine the tier (**premium** or **basic**).

- **customer.subscription.updated**:  
  Updates the user's subscription status and tier.

- **customer.subscription.deleted**:  
  Downgrades the user by marking the payment status as `canceled` and setting the tier to `basic`.

- **invoice.payment_failed**:  
  Marks the user's status as `past_due`.

All webhook handlers reside in the module `app/services/payment/stripe_handler.py`, ensuring concise and encapsulated logic.

---

## 3. Testing

Test the payment system by:

- **Simulating checkout sessions** using the Stripe test keys. Verify that the user is redirected correctly, and the checkout session is created with the correct price details.
- **Testing webhook events** either through Stripe's CLI or a tool like ngrok to ensure that events such as `checkout.session.completed` and `customer.subscription.updated` trigger the appropriate updates in the database.
- **Mocking failure cases**, such as missing form inputs or incorrect configurations, to validate the robustness of error logging and flash messages shown to the user.

---

## 4. Deployment

When deploying the system:

- Ensure that production environment variables are configured correctly with live Stripe keys.
- Verify that the `/stripe-webhook` endpoint is reachable from Stripe and is secured via the webhook secret.
- Monitor logs for any Stripe-related errors and handle subscription updates, cancellations, or payment failure events promptly.
- A maintenance plan should include periodic review of Stripe API changes and webhook event formats.

---

## System Components

- **Flask Routes (app/routes.py):**  
  Contains endpoints for initiating payment (`/payment`), handling successful transactions (`/payment/success`), and the webhook (`/stripe-webhook`).

- **Stripe Handler (app/services/payment/stripe_handler.py):**  
  Encapsulates logic to process sessions, subscription updates, cancellations, and payment failures. It uses Stripe's SDK to retrieve subscription details and determine user tier.

- **Frontend Integration:**  
  The tier selection page (`templates/payment/payment.html`) dynamically displays pricing information based on the current tier selection and populates checkout buttons with appropriate styling (selected tier highlighted).

- **User State Management:**  
  The payment status, stripe subscription identifiers, and user tiers are stored in the User model. The system leverages Flask-Login to verify user status before allowing access to protected resources (e.g., the chat feature).

---

By following this documentation, developers and maintainers can understand the flow of payments, manage Stripe event handling, and troubleshoot issues related to subscription management.

_Sources:_

- Stripe API documentation (https://stripe.com/docs/api)
- Flask best practices
