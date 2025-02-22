# OAuth2/JWT Login Flow PRD

## 1. Introduction

This document outlines the implementation of an OAuth2/JWT-based login flow for the Send Sage application. This system will replace the existing basic authentication with a more secure and standardized approach, enabling features like refresh tokens and granular access control via scopes. This PRD focuses on a self-contained OAuth2 implementation, using the application's own user database. Integration with third-party OAuth2 providers (e.g., Google, Facebook) is not included in this phase but is considered in the design for future extensibility.

## 2. Goals

- Implement a secure and standards-compliant OAuth2/JWT authentication flow.
- Provide both access and refresh tokens.
- Implement refresh token rotation and single-use refresh tokens for enhanced security.
- Define and enforce user scopes (**free_user**, **basic_user**, **premium_user**, **admin**).
- Integrate seamlessly with the existing user registration and password reset flows.
- Maintain comprehensive logging for all authentication-related events.
- Implement rate limiting to mitigate brute-force attacks.
- Ensure thorough test coverage using pytest.
- Design for future extensibility to support third-party OAuth2 providers.

## 3. Proposed Solution

The solution will leverage FastAPI's built-in security features (specifically `OAuth2PasswordBearer`) along with the `python-jose` library for JWT handling. The implementation will adhere to OAuth2 best practices and industry standards for JWT usage. The `cryptography` library will be used for key generation and encryption.

### 3.1 Token Endpoint (/token)

This endpoint will handle user authentication and token issuance.

**Request Flow:**

- Accepts username (or email) and password via `OAuth2PasswordRequestForm`.
- Authentication uses the `authenticate_user` function (in `app/core/auth.py`) to verify credentials against the database.
- Determines user's scopes based on their tier and `payment_status` (from the `User` model).

**Token Creation:**

- Generates a JWT access token with:

  - `sub` claim: User's UUID (not string ID)
  - `scopes` claim: List of granted scopes
  - `type` claim: "access"
  - `jti` claim: UUID v4 string
  - `kid` claim: Key ID for rotation
  - Configurable expiration (`ACCESS_TOKEN_EXPIRE_MINUTES`)

- Generates a JWT refresh token with:
  - `sub` claim: User's UUID (not string ID)
  - `scopes` claim: List of granted scopes
  - `type` claim: "refresh"
  - `jti` claim: UUID v4 string
  - `kid` claim: Key ID for rotation
  - Configurable expiration (`REFRESH_TOKEN_EXPIRE_DAYS`)

**Response:**

- Returns JSON object containing:
  - `access_token`
  - `token_type` ("bearer")
  - `expires_in`
  - `refresh_token` (also returned in an HttpOnly cookie)
- Sets HttpOnly, Secure cookie containing the `refresh_token`. The cookie should also have a `SameSite=Strict` attribute for CSRF protection.

**Implementation (`app/api/v1/endpoints/auth.py`):**

````python
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_async_db
from app.models.user import User
from app.models.revoked_token import RevokedToken
from app.core.auth import create_access_token, create_refresh_token, verify_password

router = APIRouter()

@router.post("/token")
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Authenticate user and issue tokens"""
    # Rate limiting check
    ip_address = request.client.host
    failed_attempts = await redis_client.incr(f"failed_logins:{ip_address}")

    if failed_attempts > settings.MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts"
        )

    # Fetch user and verify credentials
    async with db.begin():
        user = await db.scalar(
            select(User).where(User.email == form_data.username)
        )

        if not user or not await verify_password(form_data.password, user.hashed_password):
            await redis_client.expire(f"failed_logins:{ip_address}", 60)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )

        # Reset failed attempts on successful login
        await redis_client.delete(f"failed_logins:{ip_address}")

        # Determine user scopes based on subscription status
        scopes = await determine_user_scopes(db, user)

        # Generate tokens with unique JTIs
        access_token = await create_access_token(
            user_id=user.id,
            scopes=scopes,
            jti=str(uuid.uuid4())
        )

        refresh_token = await create_refresh_token(
            user_id=user.id,
            scopes=scopes,
            jti=str(uuid.uuid4())
        )

        # Set refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=settings.REFRESH_TOKEN_EXPIRE_SECONDS,
            path="/api/v1/auth/refresh-token"
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

async def determine_user_scopes(db: AsyncSession, user: User) -> list[str]:
    """Determine user scopes based on subscription status"""
    # Fetch subscription status
    subscription = await db.scalar(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .where(Subscription.status == "active")
    )

    scopes = ["user"]  # Base scope

    if subscription:
        if subscription.tier == "premium":
            scopes.append("premium_user")
        elif subscription.tier == "basic":
            scopes.append("basic_user")

    if user.is_admin:
        scopes.append("admin")

    return scopes

### 3.2 Refresh Token Endpoint (/refresh-token)

**Implementation (`app/api/v1/endpoints/auth.py`):**

```python
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from jose import JWTError, jwt
import uuid
from datetime import datetime, timedelta
from app.core.config import settings
from app.db.session import async_session
from app.models.revoked_token import RevokedToken
from app.core.auth import get_key, create_access_token, create_refresh_token

router = APIRouter()

@router.post("/refresh-token")
async def refresh_token(request: Request, response: Response):
    """
    Refresh access token using a valid refresh token from HttpOnly cookie.
    Implements refresh token rotation with single-use tokens.
    """
    # Extract refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # First attempt with current key
        payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        # Try key rotation logic
        try:
            headers = jwt.get_unverified_headers(refresh_token)
            kid = headers.get("kid")
            if not kid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token format",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Get historical key pair
            private_key, public_key = await get_key(kid)
            if not public_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            payload = jwt.decode(
                refresh_token,
                public_key,
                algorithms=[settings.ALGORITHM]
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Validate token type and extract claims
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    old_jti = payload.get("jti")
    scopes = payload.get("scopes", [])

    if not all([user_id, old_jti, scopes]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if refresh token has been revoked
    async with async_session() as session:
        revoked = await session.get(RevokedToken, old_jti)
        if revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Revoke the used refresh token (single-use)
        session.add(RevokedToken(jti=old_jti))

        # Generate new tokens with new JTIs
        new_access_token = await create_access_token(
            user_id=user_id,
            scopes=scopes,
            jti=str(uuid.uuid4())  # New unique JTI
        )

        new_refresh_token = await create_refresh_token(
            user_id=user_id,
            scopes=scopes,
            jti=str(uuid.uuid4())  # New unique JTI
        )

        await session.commit()

    # Set new refresh token in HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,  # Requires HTTPS
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_SECONDS,
        path="/api/v1/auth/refresh-token"  # Restrict to refresh endpoint
    )

    # Return new access token
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }
````

The implementation includes:

1. **Cookie Handling:**

   - Extracts refresh token from `HttpOnly` cookie
   - Sets new refresh token in `HttpOnly` cookie with secure attributes
   - Restricts cookie to refresh token endpoint path

2. **Token Verification:**

   - Supports key rotation with `kid` claim
   - Validates token type is "refresh"
   - Extracts and validates required claims

3. **Single-Use Refresh Tokens:**

   - Generates new unique JTIs for both new tokens
   - Revokes used refresh token by adding its JTI to `RevokedToken` table
   - Atomic operation: token revocation and new token generation in same transaction

4. **Security Features:**
   - Cookie security attributes (`HttpOnly`, `Secure`, `SameSite=strict`)
   - Path restriction for refresh token cookie
   - Comprehensive error handling with appropriate status codes

### 3.3 Token Revocation and Reuse Detection, Key Rotation

#### Token Security Implementation

The system implements a robust token security mechanism through two primary components:

1.  **Token Revocation System**

    - Utilizes a dedicated `RevokedToken` database table with the following schema:

    ```sql
    CREATE TABLE revoked_tokens (
        jti VARCHAR(255) PRIMARY KEY,
        revoked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    CREATE INDEX idx_revoked_tokens_jti ON revoked_tokens (jti);
    ```

    - Implements automatic revocation triggers for:
      - Successful token refresh operations
      - Explicit logout requests

    **Logout Implementation:**

    - The `/logout` endpoint specifically revokes the refresh token by adding its `jti` to the `RevokedToken` table
    - Access tokens are not explicitly revoked due to their short lifespan (`ACCESS_TOKEN_EXPIRE_MINUTES`)
    - The endpoint also clears the refresh token cookie by setting an expired cookie with the same parameters
    - Example logout flow:
      1. Extract `jti` from the refresh token
      2. Add `jti` to `RevokedToken` table
      3. Clear the refresh token cookie
      4. Return success response

2.  **Reuse Detection Mechanism**
    - Employs JTI (JWT ID) tracking for preventing token replay attacks
    - Validates each token against the `RevokedToken` table within the `get_current_user` dependency.
    - Implements signature verification with fallback support for key rotation:
      - Primary verification using current key (from `settings.SECRET_KEY`).
      - Secondary verification using previous key (during grace period), looked up via the `kid` claim in the `key_history` table.

#### Key Rotation Strategy

The system employs a time-based key rotation mechanism with the following characteristics:

1.  **Rotation Schedule**
    - Configurable rotation interval via `KEY_ROTATION_INTERVAL` environment variable (e.g., 7 days).
    - Automated key pair generation on schedule, integrated into the FastAPI application using a background task.
2.  **Key Generation**
    - Uses the `cryptography` library to generate RSA key pairs.
    - Algorithm: RS256 (RSA with SHA-256).
3.  **Grace Period Management**

    - Configurable grace period via `KEY_ROTATION_GRACE_PERIOD` environment variable (e.g., 24 hours).
    - Maintains previous key in the `key_history` table for validation during the transition.
    - `key_history` table schema:

    ```sql
    CREATE TABLE key_history (
        kid VARCHAR(255) PRIMARY KEY,
        private_key VARCHAR(255) NOT NULL,  -- Encrypted!
        public_key VARCHAR(255) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL
    );
    CREATE INDEX idx_key_history_kid ON key_history (kid);

    ```

4.  **Key Storage**
    - Current private key: Stored in the `SECRET_KEY` environment variable.
    - Previous private keys: Stored in the `key_history` table, with the `private_key` column _encrypted at rest_ using AES-256-GCM (or a similar strong algorithm). A separate, securely stored master key is used for this encryption, this is stored in the `MASTER_KEY` environment variable.
5.  **Distribution**
    - All application instances access the same `key_history` table.
    - The `SECRET_KEY` environment variable is updated across all instances during deployment using rolling updates or a configuration management system.
6.  **`get_current_user` Key Rotation Logic**
    - First, attempts to decode the JWT using the current `SECRET_KEY`.
    - If that fails due to an invalid signature, extracts the `kid` from the JWT header.
    - Queries the `key_history` table for a matching `kid` with an `expires_at` in the future.
    - If found, retrieves the corresponding _public_ key and attempts to decode the JWT again.
    - If both attempts fail, the token is rejected.

#### Key Rotation Implementation Details

1. **Key Management Functions (`app/core/auth.py`)**

```python
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
from datetime import datetime, timedelta
from app.core.config import settings
from app.db.session import async_session
from app.models.key_history import KeyHistory

async def get_key(kid: str) -> tuple[str, str]:
    """
    Retrieve and decrypt a key pair from the key_history table.
    Returns (private_key, public_key) tuple.
    """
    async with async_session() as session:
        key = await session.get(KeyHistory, kid)
        if not key or key.expires_at < datetime.utcnow():
            return None, None

        # Decrypt private key using AESGCM
        nonce = key.private_key[:12]  # First 12 bytes are nonce
        ciphertext = key.private_key[12:]
        aesgcm = AESGCM(settings.MASTER_KEY.encode())
        private_key = aesgcm.decrypt(nonce, ciphertext, None)

        return private_key.decode(), key.public_key

async def generate_key_pair() -> tuple[str, str, str]:
    """Generate a new RSA key pair and return (private_key, public_key, kid)"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    # Generate kid as UUID
    kid = str(uuid.uuid4())

    # Serialize keys
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    return private_pem, public_pem, kid

async def encrypt_private_key(private_key: str) -> bytes:
    """Encrypt private key using AESGCM with MASTER_KEY"""
    aesgcm = AESGCM(settings.MASTER_KEY.encode())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, private_key.encode(), None)
    return nonce + ciphertext  # Prepend nonce to ciphertext
```

2. **Key Rotation Background Task (`app/core/key_rotation.py`)**

```python
from fastapi import BackgroundTasks
from app.core.logging import logger
from app.core.config import settings
from app.db.session import async_session
from app.models.key_history import KeyHistory
from datetime import datetime, timedelta

async def rotate_keys(background_tasks: BackgroundTasks):
    """Background task to handle key rotation"""
    try:
        # Generate new key pair
        private_key, public_key, kid = await generate_key_pair()

        # Encrypt private key
        encrypted_private_key = await encrypt_private_key(private_key)

        # Calculate expiration
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(
            days=settings.KEY_ROTATION_INTERVAL_DAYS +
                 settings.KEY_ROTATION_GRACE_PERIOD_DAYS
        )

        # Store in database
        async with async_session() as session:
            new_key = KeyHistory(
                kid=kid,
                private_key=encrypted_private_key,
                public_key=public_key,
                created_at=created_at,
                expires_at=expires_at
            )
            session.add(new_key)
            await session.commit()

        # Update current SECRET_KEY
        # Note: This requires infrastructure support for dynamic env updates
        await update_secret_key(private_key)

        logger.info(f"Key rotation completed successfully",
                   extra={"kid": kid, "expires_at": expires_at})

        # Schedule next rotation
        background_tasks.add_task(
            schedule_next_rotation,
            timedelta(days=settings.KEY_ROTATION_INTERVAL_DAYS)
        )

    except Exception as e:
        logger.error(f"Key rotation failed: {str(e)}")
        # Alert operations team
        await alert_ops_team("Key rotation failed", str(e))
```

3. **MASTER_KEY Management**

The `MASTER_KEY` is a critical security component used for encrypting private keys at rest:

- **Storage**:

  - Stored as a secure environment variable (`MASTER_KEY`)
  - Should be a 32-byte (256-bit) key encoded in base64
  - Must be consistent across all application instances

- **Generation**:

```python
# Generate a new MASTER_KEY (during initial setup only)
master_key = base64.b64encode(os.urandom(32)).decode()
```

- **Access**:

```python
# In app/core/config.py
class Settings(BaseSettings):
    MASTER_KEY: str  # Base64-encoded 32-byte key

    @validator("MASTER_KEY")
    def validate_master_key(cls, v):
        try:
            decoded = base64.b64decode(v)
            if len(decoded) != 32:
                raise ValueError("MASTER_KEY must be 32 bytes when decoded")
            return v
        except Exception:
            raise ValueError("MASTER_KEY must be valid base64-encoded 32-byte key")
```

4. **Encryption Algorithm Details**

Private key encryption uses AES-256-GCM (Galois/Counter Mode):

- Algorithm: AES-256-GCM
- Key Size: 256 bits (32 bytes)
- Nonce Size: 96 bits (12 bytes)
- Authentication Tag: 128 bits (16 bytes)
- Implementation: Python's `cryptography.hazmat.primitives.ciphers.aead.AESGCM`

Benefits of AES-256-GCM:

- Authenticated encryption (provides both confidentiality and authenticity)
- Parallel processing capability
- Wide support and proven security

### 3.4 Scope Enforcement

**TokenData Schema (`app/schemas/token.py`):**

```python
from pydantic import BaseModel, UUID4
from typing import List

class TokenData(BaseModel):
    user_id: UUID4
    scopes: List[str]
    type: str  # "access" or "refresh"
    jti: UUID4
```

**`get_current_user` Dependency Implementation (`app/core/auth.py`):**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.core.config import settings
from app.db.session import async_session
from app.models.revoked_token import RevokedToken
from app.models.user import User
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Validates the access token and returns the current user.
    Handles key rotation and JTI validation.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # First attempt: Try current SECRET_KEY
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
    except JWTError as e:
        # If verification fails, try key rotation logic
        try:
            # Extract unverified headers to get kid
            headers = jwt.get_unverified_headers(token)
            kid = headers.get("kid")
            if not kid:
                raise credentials_exception

            # Get historical key pair
            private_key, public_key = await get_key(kid)
            if not public_key:
                raise credentials_exception

            # Second attempt: Try with historical public key
            payload = jwt.decode(
                token,
                public_key,
                algorithms=[settings.ALGORITHM]
            )
        except JWTError:
            raise credentials_exception

    try:
        token_data = TokenData(
            user_id=UUID(payload.get("sub")),  # Convert string to UUID
            scopes=payload.get("scopes", []),
            type=payload.get("type"),
            jti=UUID(payload.get("jti"))  # Convert string to UUID
        )
    except (ValueError, ValidationError):
        raise credentials_exception

    if token_data.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if token has been revoked
    async with async_session() as session:
        revoked = await session.get(RevokedToken, str(token_data.jti))
        if revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get user from database
        user = await session.get(User, token_data.user_id)
        if not user:
            raise credentials_exception

        # Attach scopes to user object for convenience
        user.token_scopes = token_data.scopes

        return user
```

The implementation includes:

1. **Token Verification Flow:**

   - Initial attempt with current `SECRET_KEY`
   - Fallback to key rotation logic using `kid` if initial attempt fails
   - Comprehensive error handling for all verification steps

2. **Claim Validation:**

   - Extracts and validates required claims (`type`, `sub`, `jti`, `scopes`)
   - Ensures token is an access token
   - Validates token hasn't been revoked using `jti`

3. **User Resolution:**

   - Retrieves user from database
   - Attaches token scopes to user object for convenience
   - Validates user is active

4. **Scope Validation:**
   - Provides a scope validation factory function
   - Includes convenience dependencies for common scopes
   - Proper error handling for insufficient permissions

**Protected Endpoints Example:**

```python
@router.get("/admin-only", dependencies=[Depends(get_current_admin)])
async def admin_only():
    return {"message": "Admin access granted"}

@router.get("/premium-feature", dependencies=[Depends(get_current_premium_user)])
async def premium_feature():
    return {"message": "Premium access granted"}

@router.get("/user-data")
async def user_data(current_user: User = Depends(get_current_basic_user)):
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "scopes": current_user.token_scopes
    }
```

### 3.5 Registration and Password Reset

- Registration endpoint issues tokens post-creation with the `user` scope.
- Password reset maintains existing flow with `password-reset` scope. Password reset tokens are single-use and are revoked after successful password change.
- Post-reset requires new token acquisition.

### 3.6 Rate Limiting

**Implementation:**

A counter-based approach tracking failed attempts will be used, storing counters in Redis for performance. This will be implemented using a FastAPI dependency to manage the Redis connection and provide a Redis client instance to relevant endpoints.

**FastAPI Dependency:** A dependency function (`get_redis`) will be created in `app/core/redis.py` to handle Redis connection creation, pooling, and closing. This dependency will be injected into any endpoint that requires rate limiting functionality (e.g., `/token`, `/password-reset`).

**Configurable limits via environment variables. Examples:**

- 10 failed login attempts per minute per IP address.
- 5 password reset requests per hour per email address.

Counters are reset on a time-based interval (e.g., login attempts reset after 1 minute, password reset requests after 1 hour).
429 status code (`Too Many Requests`) for limit violations, with a `Retry-After` header indicating when the client can retry.

**Example Usage (Conceptual):**

```python
# In app/core/redis.py
import redis.asyncio as redis
from typing import AsyncGenerator
from app.core.config import settings

async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    client = redis.from_url(settings.REDIS_URL)
    try:
        yield client
    finally:
        await client.close()
```

```python
# In app/api/v1/endpoints/auth.py
from fastapi import Depends, HTTPException, status
from app.core.redis import get_redis
import redis.asyncio as redis

@router.post("/token")
async def login_for_access_token(
    db: AsyncSession = Depends(get_async_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    redis_client: redis.Redis = Depends(get_redis)  # Inject Redis client
):
    # ... authentication logic ...

    # Rate limiting example:
    ip_address = "127.0.0.1"  # Get from request in a real app
    failed_attempts = await redis_client.incr(f"failed_logins:{ip_address}")
    await redis_client.expire(f"failed_logins:{ip_address}", 60)  #expire after 60 seconds

    if failed_attempts > 10:
        raise HTTPException(status_code=429, detail="Too many failed attempts")

    # ... rest of the login logic ...
```

### 3.7 Logging

**Events Tracked (using Loguru, configured in `app/core/logging_config.py` and `app/core/logging.py`):**

- **Login Attempts (success/failure):** `user_id` (if known), `email`, `ip_address`, `user_agent`, `success` (boolean), `reason` (if failure).
- **Token Operations:** `user_id`, `token_type` (access/refresh), `jti`, `scopes`, `operation` (issuance, refresh, revocation), `ip_address`, `user_agent`, `kid`.
- **Rate Limiting Events:** `ip_address`, `user_id` (if known), `email` (if known), `limit_type` (login, password reset), `limit_exceeded`.
- **Key Rotation Events:** `kid` (of the new key), `status` (success/failure).

### 3.8 Error Handling

- Consistent `HTTPException` usage.
- Detailed context logging, leveraging the structured logging setup.
- Standardized error responses:

  ```json
  {
      "error": "error_code",
      "detail": "Human-readable error message",
      "context": { ...optional details... }
  }
  ```

  Specific error codes will be defined for common authentication failures (e.g., `invalid_credentials`, `token_expired`, `invalid_token`, `insufficient_scope`, `account_locked`, `token_revoked`, `invalid_signature`, `key_not_found`, etc.). This aligns with the exception handling in `app/core/error_handlers.py` and custom exceptions defined in `app/core/exceptions.py`.

### 3.8 Asynchronous Database Operations

The system implements fully asynchronous database operations across all authentication endpoints to ensure optimal performance and prevent event loop blocking. Key implementation details include:

1. **Session Management**

```python
# app/db/session.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

async_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.SQL_ECHO
)

AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_async_db() -> AsyncSession:
    """Dependency for getting async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

2. **Transaction Patterns**

```python
# Pattern 1: Explicit Transaction with commit
async with db.begin():
    # Operations that need to be atomic
    session.add(new_entity)
    await session.flush()
    # More operations...
    # Auto-commits on successful completion

# Pattern 2: Manual Transaction Management
try:
    async with db.begin():
        # Multiple operations that need to be atomic
        await db.execute(stmt1)
        await db.execute(stmt2)
        await db.flush()
        # Auto-commits on successful completion
except SQLAlchemyError as e:
    # Transaction automatically rolled back
    logger.error(f"Database error: {str(e)}")
    raise HTTPException(status_code=500, detail="Database error")
```

3. **Query Patterns**

```python
# Scalar Results
user = await db.scalar(
    select(User).where(User.email == email)
)

# Multiple Results
results = await db.scalars(
    select(User).where(User.is_active == True)
)
users = results.all()

# Pagination
page_size = 20
offset = (page - 1) * page_size
results = await db.scalars(
    select(User)
    .order_by(User.created_at.desc())
    .offset(offset)
    .limit(page_size)
)
```

4. **Relationship Loading**

```python
# Explicit Loading
user = await db.scalar(
    select(User)
    .options(selectinload(User.roles))
    .where(User.id == user_id)
)

# Lazy Loading (within async context)
async with db.begin():
    user = await db.get(User, user_id)
    roles = await user.awaitable_attrs.roles
```

5. **Error Handling**

```python
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

async def database_operation(db: AsyncSession):
    try:
        async with db.begin():
            # Database operations
            await db.flush()
    except IntegrityError as e:
        logger.error(f"Integrity error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resource already exists"
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error"
        )
```

6. **Bulk Operations**

```python
async def bulk_revoke_tokens(db: AsyncSession, jti_list: list[str]):
    """Bulk revoke multiple tokens"""
    try:
        async with db.begin():
            await db.execute(
                insert(RevokedToken).values([
                    {"jti": jti} for jti in jti_list
                ])
            )
    except SQLAlchemyError as e:
        logger.error(f"Failed to revoke tokens: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke tokens"
        )
```

These patterns ensure:

- Proper connection handling and resource cleanup
- Atomic transactions where needed
- Efficient query execution
- Proper error handling and logging
- Prevention of N+1 query problems
- Scalable bulk operations

All authentication endpoints (`/token`, `/refresh-token`, `/logout`, registration, password reset) implement these patterns to maintain optimal performance and reliability.

## 4. Implementation Plan

- **Phase 1: Setup**

  - Create `RevokedToken` and `key_history` database tables.
  - Update User model (if necessary).
  - Configure dependencies and environment variables (`KEY_ROTATION_INTERVAL`, `KEY_ROTATION_GRACE_PERIOD`, rate limiting variables, `MASTER_KEY`, Redis connection details).
  - Set `ALGORITHM = "RS256"`.

- **Phase 2: Implementation**

  - Develop token endpoints (`/token`, `/refresh-token`, `/logout`), including `jti` and `kid` handling.
  - Implement token lifecycle management (creation, refresh, revocation, key rotation background task).
  - Implement rate limiting:
    - Create the `get_redis` dependency in `app/core/redis.py`.
    - Integrate the `get_redis` dependency into the relevant endpoints (`/token`, `/password-reset`, etc.).
    - Implement rate limiting logic within the endpoints using the injected Redis client.
  - Integrate logging.
  - Update `get_current_user` with `jti` validation and key rotation logic.
  - Implement encryption/decryption for private keys in the `key_history` table.

- **Phase 3: Testing**

  - Unit test core functions (`create_access_token`, `create_refresh_token`, `verify_password`, `get_current_user`, key rotation functions, encryption/decryption functions, etc.).
  - Integration test endpoints (`/token`, `/refresh-token`, `/logout`, protected endpoints).
  - Integration test token revocation and reuse detection (including `jti` checks).
  - Validate using pytest.
  - Test key rotation, including grace period and fallback logic.
  - Test rate limiting.

- **Phase 4: Deployment**
  - Deploy updates.
  - Monitor authentication logs and rate limiting.

## 5. Open Questions/Considerations

- Async database session management - _Addressed in the Async Database Sessions PRD._

## 6. Non-Functional Requirements

- **Performance:** The `/token` endpoint should respond within 200ms under normal load.
- **Scalability:** The system should handle increased load gracefully, leveraging connection pooling, async operations, and Redis for rate limiting.
- **Security:** The system adheres to OAuth2 and JWT best practices, including secure token storage, refresh token rotation, `jti` validation, key rotation with encryption at rest, and protection against common attacks.
- **Maintainability:** The code is well-structured, documented, and follows established coding standards.
- **Testability:** The system is thoroughly tested with unit and integration tests.

## 7. Acceptance Criteria

- All API endpoints requiring authentication are protected by the `get_current_user` dependency.
- Successful login attempts return a JSON response with an access token and set an HttpOnly, Secure, `SameSite=Strict` cookie containing the refresh token. Both tokens include a `jti` claim. The access token includes a `kid` claim.
- Attempting to access a protected endpoint with an expired or invalid token results in a 401 Unauthorized response.
- Attempting to access a protected endpoint with insufficient scope results in a 403 Forbidden response.
- Successful token refresh results in a new access token and a new refresh token (with the old refresh token being revoked and its `jti` added to the `RevokedToken` table).
- Attempting to reuse a revoked refresh token (based on its `jti`) results in a 401 Unauthorized response.
- Rate limiting is enforced for login and password reset attempts, resulting in a 429 Too Many Requests response with a `Retry-After` header when limits are exceeded.
- All authentication-related events are logged with the specified fields, including `jti` and `kid` where appropriate.
- Unit and integration tests cover all authentication and authorization scenarios, including key rotation, `jti` validation, and error handling.
- Key rotation occurs automatically and transparently, with no disruption to authenticated users during the grace period.
- Private keys in the `key_history` table are encrypted at rest.

---

**References:**

- WorkOS: OAuth and JWT - How To Use Together + Best Practices
