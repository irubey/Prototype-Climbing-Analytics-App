# Send Sage API Documentation

## Overview

The Send Sage API provides a comprehensive set of endpoints for managing climbing data, performance analysis, and subscription services. This API is built using FastAPI and provides asynchronous operations for improved performance.

## Base URL

```
https://api.sendsage.com/api/v1
```

## Authentication

All authenticated endpoints require a valid JWT token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Authentication Endpoints

#### Register User

```http
POST /auth/register
```

Create a new user account.

**Request Body:**

```json
{
  "email": "user@example.com",
  "username": "climber123",
  "password": "SecurePass123!",
  "mountain_project_url": "https://mountainproject.com/user/12345"
}
```

**Response:** `201 Created`

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "climber123",
  "tier": "free",
  "created_at": "2024-02-20T12:00:00Z"
}
```

#### Login

```http
POST /auth/token
```

Obtain access token.

**Request Body (form-data):**

```
username: user@example.com
password: SecurePass123!
```

**Response:** `200 OK`

```json
{
  "access_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### Refresh Token

```http
POST /auth/refresh-token
```

Refresh access token.

**Response:** `200 OK`

```json
{
  "access_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

## Payment & Subscription

### Pricing Information

```http
GET /payment/pricing
```

Get available subscription tiers and pricing.

**Response:** `200 OK`

```json
{
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
```

### Create Checkout Session

```http
POST /payment/create-checkout-session
```

Create Stripe checkout session for subscription.

**Request Body:**

```json
{
  "tier": "premium"
}
```

**Response:** `200 OK`

```json
{
  "checkout_session_id": "cs_test_..."
}
```

## Data Management

### Create Tick

```http
POST /data/ticks
```

Create a new climbing tick.

**Request Body:**

```json
{
  "route_name": "Project X",
  "grade": "5.12a",
  "style": "Lead",
  "attempts": 3,
  "send_status": "SENT",
  "date_climbed": "2024-02-20T12:00:00Z",
  "location": "Red River Gorge",
  "notes": "Finally sent after working the crux",
  "discipline": "sport"
}
```

**Response:** `201 Created`

```json
{
  "id": 123,
  "route_name": "Project X",
  "grade": "5.12a",
  "created_at": "2024-02-20T12:00:00Z"
}
```

### Batch Create Ticks

```http
POST /data/ticks/batch
```

Create multiple ticks at once.

**Request Body:**

```json
{
  "ticks": [
    {
      "route_name": "Route 1",
      "grade": "5.10a",
      "discipline": "sport"
    },
    {
      "route_name": "Route 2",
      "grade": "5.11b",
      "discipline": "sport"
    }
  ]
}
```

**Response:** `201 Created`

```json
[
  {
    "id": 124,
    "route_name": "Route 1"
  },
  {
    "id": 125,
    "route_name": "Route 2"
  }
]
```

### Delete Tick

```http
DELETE /data/ticks/{tick_id}
```

Delete a specific tick.

**Response:** `204 No Content`

### Refresh Logbook

```http
POST /data/refresh
```

Initiate Mountain Project data refresh.

**Response:** `202 Accepted`

```json
{
  "task_id": "task_123",
  "status": "pending"
}
```

## Visualization

### Dashboard Data

```http
GET /visualization/dashboard
```

Get user's climbing dashboard overview.

**Response:** `200 OK`

```json
{
  "recent_ticks": [
    {
      "route_name": "Project X",
      "grade": "5.12a",
      "date": "2024-02-20"
    }
  ],
  "discipline_distribution": {
    "sport": 45,
    "boulder": 30,
    "trad": 25
  },
  "grade_distribution": {
    "5.10a": 10,
    "5.10b": 15,
    "5.11a": 5
  },
  "total_climbs": 100
}
```

### Performance Pyramid

```http
GET /visualization/performance-pyramid
```

Get performance pyramid data.

**Query Parameters:**

- `discipline`: string (sport, boulder, trad)

**Response:** `200 OK`

```json
{
  "discipline": "sport",
  "grade_counts": {
    "5.12a": 1,
    "5.11d": 2,
    "5.11c": 4,
    "5.11b": 8
  },
  "total_sends": 15
}
```

### Base Volume Analysis

```http
GET /visualization/base-volume
```

Get climbing volume analysis.

**Response:** `200 OK`

```json
{
  "volume_by_difficulty": {
    "warmup": {
      "count": 50,
      "avg_length": 20
    },
    "project": {
      "count": 30,
      "avg_length": 25
    }
  }
}
```

### Location Analysis

```http
GET /visualization/location-analysis
```

Get climbing location patterns.

**Response:** `200 OK`

```json
{
  "locations": {
    "Red River Gorge": {
      "count": 30,
      "grades": ["5.10a", "5.11b", "5.12a"]
    }
  },
  "seasonal_patterns": {
    "spring": 40,
    "summer": 20,
    "fall": 35,
    "winter": 5
  }
}
```

## Error Responses

The API uses standard HTTP status codes and returns error details in JSON format:

```json
{
  "error": "Error message description"
}
```

Common error codes:

- `400 Bad Request`: Invalid input data
- `401 Unauthorized`: Missing or invalid authentication
- `402 Payment Required`: Premium feature access denied
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Rate Limiting

- Free tier: 60 requests per minute
- Basic tier: 120 requests per minute
- Premium tier: 300 requests per minute

## Webhook Events

The API sends webhook events for subscription-related updates:

- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_failed`
- `invoice.payment_succeeded`

Configure webhook URL in your dashboard settings.
