"""
Authentication and authorization utilities for Send Sage application.

This module provides functionality for:
- Password hashing and verification
- JWT token creation and validation with key rotation
- User authentication and authorization based on roles and scopes
- Dependency injection for getting the current user in API routes
"""

# Standard library imports
from datetime import datetime, timedelta, timezone, UTC
from typing import Union, Optional, Annotated, Dict, Any
from uuid import UUID, uuid4
import base64
import os

# Third-party imports
from fastapi import Depends, HTTPException, status, Security, Request
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import ValidationError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import redis.asyncio as redis

# Application imports
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DatabaseError,
    PaymentRequired
)
from app.core.logging import logger
from app.core import settings
from app.db.session import get_db
from app.models import User
from app.models.auth import RevokedToken, KeyHistory
from app.schemas.auth import TokenData
from app.schemas.user import UserCreate
from sqlalchemy import select, or_, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

# Security configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Redis client for rate limiting
_redis_client: Optional[redis.Redis] = None

async def get_redis() -> redis.Redis:
    """Get Redis client instance."""
    global _redis_client
    if _redis_client is None:
        from app.core.config import settings
        _redis_client = redis.from_url(settings.REDIS_URL)
    return _redis_client

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(str(password))

async def generate_key_pair() -> tuple[str, str, str]:
    """Generate a new RSA key pair and return (private_key, public_key, kid)."""
    # Generate RSA key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    # Generate kid as UUID
    kid = str(uuid4())

    # Serialize private key in PKCS8 format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()

    # Serialize public key in SubjectPublicKeyInfo format
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    # Log key generation
    logger.debug(
        "Generated new key pair",
        extra={
            "kid": kid,
            "private_key_format": "PKCS8",
            "public_key_format": "SubjectPublicKeyInfo"
        }
    )

    return private_pem, public_pem, kid

async def encrypt_private_key(private_key: str) -> bytes:
    """Encrypt private key using AESGCM with MASTER_KEY."""
    from app.core.config import settings
    aesgcm = AESGCM(base64.b64decode(settings.MASTER_KEY))
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, private_key.encode(), None)
    return nonce + ciphertext  # Prepend nonce to ciphertext

async def decrypt_private_key(encrypted_key: bytes) -> str:
    """Decrypt private key using AESGCM with MASTER_KEY."""
    from app.core.config import settings
    aesgcm = AESGCM(base64.b64decode(settings.MASTER_KEY))
    nonce = encrypted_key[:12]
    ciphertext = encrypted_key[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()

async def get_key(kid: str, db: Optional[AsyncSession] = None) -> tuple[Optional[str], Optional[str]]:
    """Retrieve key pair by KID from KeyHistory and decrypt private key."""
    try:
        # If db is not provided, get a session
        if db is None:
            from app.db.session import sessionmanager
            async with sessionmanager.session() as session:
                db = session
        
        result = await db.execute(
            select(KeyHistory).filter(KeyHistory.id == kid)
        )
        key_record = result.scalar_one_or_none()

        if not key_record:
            return None, None

        decrypted_private_key = await decrypt_private_key(key_record.private_key)

        return decrypted_private_key, key_record.public_key

    except Exception as e:
        logger.error(
            "Error retrieving key",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "kid": kid
            }
        )
        return None, None

def encode_jwt(payload: dict, key: str, algorithm: str, headers: dict = None) -> str:
    """
    Wrapper around jwt.encode that uses timezone-aware UTC timestamps.
    This avoids the deprecation warning from jwt.encode's use of utcnow().
    """
    # If payload has an 'exp' or 'iat' claim, ensure they're timezone-aware
    if 'exp' in payload and isinstance(payload['exp'], datetime):
        payload = {**payload, 'exp': payload['exp'].astimezone(UTC)}
    if 'iat' in payload and isinstance(payload['iat'], datetime):
        payload = {**payload, 'iat': payload['iat'].astimezone(UTC)}
    
    # For RSA algorithms, we need to load the private key properly
    if algorithm.startswith('RS'):
        try:
            private_key = serialization.load_pem_private_key(
                key.encode(),
                password=None
            )
            key = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
        except Exception as e:
            logger.error(f"Error loading private key: {str(e)}")
            raise AuthenticationError("Failed to load private key")
    
    return jwt.encode(payload, key, algorithm=algorithm, headers=headers)

async def create_access_token(
    subject: Union[str, UUID],
    scopes: list[str],
    jti: str,
    db: Optional[AsyncSession] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token with scopes and JTI."""
    from app.core.config import settings

    try:
        # If db is not provided, get a session
        if db is None:
            from app.db.session import sessionmanager
            async with sessionmanager.session() as session:
                db = session
                
        expire = datetime.now(timezone.utc) + (
            expires_delta if expires_delta
            else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        # Get current key (DO NOT generate a new one here)
        current_key = await db.execute(
            select(KeyHistory).order_by(KeyHistory.created_at.desc()).limit(1)
        )
        current_key_record = current_key.scalar_one_or_none()

        if not current_key_record:
            raise AuthenticationError("No active key found. Key rotation required.")

        private_key = await decrypt_private_key(current_key_record.private_key)
        key_id = current_key_record.id

        to_encode = {
            "sub": str(subject),
            "exp": expire,
            "type": "access",
            "scopes": scopes,
            "jti": jti,
        }

        encoded_jwt = encode_jwt(
            to_encode,
            private_key,
            algorithm=settings.ALGORITHM,
            headers={"kid": key_id}
        )

        logger.debug(
            "Created access token",
            extra={
                "user_id": str(subject),
                "scopes": scopes,
                "jti": jti,
                "kid": key_id,
                "expires": expire.isoformat()
            }
        )

        return encoded_jwt

    except Exception as e:
        logger.error(
            "Failed to create access token",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "user_id": str(subject)
            }
        )
        raise AuthenticationError(
            detail="Could not create access token",
            context={"user_id": str(subject)}
        )

async def create_refresh_token(
    subject: Union[str, UUID],
    scopes: list[str],
    jti: str,
    db: Optional[AsyncSession] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT refresh token with scopes and JTI."""
    from app.core.config import settings

    try:
        # If db is not provided, get a session
        if db is None:
            from app.db.session import sessionmanager
            async with sessionmanager.session() as session:
                db = session
                
        expire = datetime.now(timezone.utc) + (
            expires_delta
            if expires_delta
            else timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60)  # Convert days to minutes
        )

        # Get current key (DO NOT generate a new one here)
        current_key = await db.execute(
            select(KeyHistory).order_by(KeyHistory.created_at.desc()).limit(1)
        )
        current_key_record = current_key.scalar_one_or_none()

        if not current_key_record:
            raise AuthenticationError("No active key found. Key rotation required.")

        private_key = await decrypt_private_key(current_key_record.private_key)
        key_id = current_key_record.id

        to_encode = {
            "sub": str(subject),
            "exp": expire,
            "type": "refresh",  # Correct type
            "scopes": scopes,
            "jti": jti,
        }

        encoded_jwt = encode_jwt(
            to_encode,
            private_key,
            algorithm=settings.ALGORITHM,
            headers={"kid": key_id}
        )

        logger.debug(
            "Created refresh token",
            extra={
                "user_id": str(subject),
                "scopes": scopes,
                "jti": jti,
                "kid": key_id,
                "expires": expire.isoformat()
            }
        )

        return encoded_jwt

    except Exception as e:
        logger.error(
            "Failed to create refresh token",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "user_id": str(subject)
            }
        )
        raise AuthenticationError(
            detail="Could not create refresh token",
            context={"user_id": str(subject)}
        )

async def verify_token(
    token: str,
    db: Optional[AsyncSession] = None,
    expected_type: str = "access"
) -> TokenData:
    """
    Verify a JWT token and return its data.
    Handles key rotation and JTI validation.
    """
    from app.core.config import settings

    try:
        # If db is not provided, get a session
        if db is None:
            from app.db.session import sessionmanager
            async with sessionmanager.session() as session:
                db = session
                
        # Get the KID from the header *before* attempting to decode
        headers = jwt.get_unverified_headers(token)
        kid = headers.get("kid")
        if not kid:
            raise AuthenticationError(detail="Invalid token format: Missing KID")

        # Get key pair based on KID
        result = await db.execute(
            select(KeyHistory).filter(KeyHistory.id == kid)
        )
        key_record = result.scalar_one_or_none()
        
        if not key_record:
            logger.error(f"Key not found for KID: {kid}")
            raise AuthenticationError(detail="Invalid token: Key not found")

        # Check if key has expired
        if key_record.expires_at < datetime.now(timezone.utc):
            logger.error(f"Key has expired for KID: {kid}")
            raise AuthenticationError(detail="Invalid token: Key has expired")

        # Load the public key for verification
        try:
            public_key = serialization.load_pem_public_key(
                key_record.public_key.encode()
            )
            public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode()

            # Use public key for verification
            payload = jwt.decode(
                token,
                public_key_pem,
                algorithms=[settings.ALGORITHM]
            )
        except (ValueError, JWTError) as e:
            logger.error(f"Error verifying token: {str(e)}")
            raise AuthenticationError(detail="Invalid token signature")

        # Validate token type
        if payload.get("type") != expected_type:
            raise AuthenticationError(
                detail=f"Invalid token type. Expected {expected_type}, got {payload.get('type')}"
            )

        # Check if token has been revoked
        jti = payload.get("jti")
        revoked = await db.scalar(
            select(RevokedToken).filter(RevokedToken.jti == jti)
        )
        if revoked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token has been revoked"
            )

        # Create and return token data
        return TokenData(
            user_id=UUID(payload["sub"]),
            scopes=payload.get("scopes", []),
            type=payload["type"],
            jti=jti
        )

    except HTTPException:
        raise
    except AuthenticationError:
        raise
    except Exception as e:
        logger.exception("An unexpected error occurred during token verification")
        raise AuthenticationError(detail=f"Token verification failed: {str(e)}")

def get_oauth2_scheme() -> OAuth2PasswordBearer:
    """Get OAuth2 password bearer scheme with scopes."""
    from app.core.config import settings

    return OAuth2PasswordBearer(
        tokenUrl=f"{settings.API_V1_STR}/auth/token",
        scopes={
            "user": "Basic user access",
            "basic_user": "Basic tier access",
            "premium_user": "Premium tier access",
            "admin": "Admin access"
        }
    )

async def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(get_oauth2_scheme()),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current user from token."""
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"

    try:
        # Verify token and get token data
        token_data = await verify_token(token, db)

        # Get user from database
        result = await db.execute(
            select(User).filter(User.id == token_data.user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise AuthenticationError(detail="User not found")

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )

        # Validate scopes
        if security_scopes.scopes:
            for scope in security_scopes.scopes:
                if scope not in token_data.scopes:
                    raise AuthorizationError(
                        detail="Not enough permissions",
                        headers={"WWW-Authenticate": f"Bearer scope={security_scopes.scope_str}"}
                    )

        # Attach scopes to user object for convenience
        user.token_scopes = token_data.scopes
        return user

    except HTTPException as e:
        # Re-raise HTTP exceptions (like 403 for inactive users)
        raise
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": authenticate_value}
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
            headers=e.headers
        )

# Convenience dependencies for common scopes
async def get_current_active_user(
    current_user: User = Security(get_current_user, scopes=["user"])
) -> User:
    """Get current active user with basic scope."""
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    return current_user

async def get_current_basic_user(
    current_user: User = Security(get_current_user, scopes=["basic_user"])
) -> User:
    """Get current user with basic tier scope."""
    return current_user

async def get_current_premium_user(
    current_user: User = Security(get_current_user, scopes=["premium_user"])
) -> User:
    """Get current user with premium tier scope."""
    return current_user

async def get_current_admin(
    current_user: User = Security(get_current_user, scopes=["admin"])
) -> User:
    """Get current user with admin scope."""
    return current_user

async def authenticate_user(
    email: str,
    password: str,
    db: Optional[AsyncSession] = None
) -> Optional["User"]:
    """Authenticate user by email/username and password."""
    try:
        # If db is not provided, get a session
        if db is None:
            from app.db.session import sessionmanager
            async with sessionmanager.session() as session:
                db = session
                
        logger.debug(f"Authenticating user with email/username: {email}")
        result = await db.execute(
            select(User).filter(
                or_(User.email == email, User.username == email)
            )
        )
        logger.debug(f"Result: {result}")
        user = result.scalar_one_or_none()
        logger.debug(f"User: {user}")

        if not user or not verify_password(password, user.hashed_password):
            logger.warning(
                "Failed login attempt",
                extra={
                    "email": email,
                    "reason": "invalid_credentials"
                }
            )
            return None

        logger.info(
            "Successful login",
            extra={"user_id": str(user.id)}
        )
        return user

    except Exception as e:
        logger.error(
            "Error during authentication",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "email": email
            }
        )
        return None

async def create_user(
    user_create: UserCreate,
    scopes: list[str] = ["user"],
    is_active: bool = True,
    db: Optional[AsyncSession] = None
) -> "User":
    """Create a new user with specified scopes."""
    try:
        # If db is not provided, get a session
        if db is None:
            from app.db.session import sessionmanager
            async with sessionmanager.session() as session:
                db = session
                
        hashed_password = get_password_hash(user_create.password.get_secret_value())
        logger.debug(f"Hashed password: {hashed_password}")
        # Use model_dump to get a dictionary, which will apply validators and defaults
        user_data = user_create.model_dump(exclude_unset=True)
        logger.debug(f"User data: {user_data}")
        # Update the dictionary with the hashed password
        user_data["hashed_password"] = hashed_password
        logger.debug(f"User data after hashing: {user_data}")
        # Remove plain text password, mountain_project_url, and eight_a_nu_url
        user_data.pop("password", None)
        logger.debug(f"User data after removing plain text password: {user_data}")
        db_user = User(
            **user_data,
            is_active=is_active,
            tier="free",
            payment_status="inactive"
        )
        logger.debug(f"User data after creating User object: {user_data}")
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        logger.debug(f"User data after committing to database: {user_data}")
        logger.info(
            "Created new user",
            extra={
                "user_id": str(db_user.id),
                "email": db_user.email,
                "scopes": scopes
            }
        )

        return db_user

    except Exception as e:
        await db.rollback()
        logger.error(
            "Failed to create user",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "email": user_create.email
            }
        )
        raise DatabaseError(detail="Could not create user")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_token_from_header(request: Request) -> str:
    """Extract token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return auth_header.split(" ")[1]