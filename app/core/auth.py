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
from cryptography.fernet import Fernet
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

# Initialize Fernet cipher for credential encryption
credential_cipher = Fernet(settings.CREDENTIAL_KEY.encode())

# Redis client for rate limiting
_redis_client: Optional[redis.Redis] = None

async def get_redis() -> redis.Redis:
    """Get Redis client instance or a mock if Redis is unavailable."""
    global _redis_client
    if _redis_client is None:
        from app.core.config import settings
        
        # Always use mock Redis in development mode
        if settings.ENVIRONMENT.lower() in ("development", "testing"):
            from app.core.redis_mock import MockRedis
            logger.info(f"Using mock Redis implementation in {settings.ENVIRONMENT} environment")
            _redis_client = MockRedis()
        else:
            try:
                _redis_client = redis.from_url(settings.REDIS_URL)
                # Test the connection
                await _redis_client.ping()
                logger.info("Connected to Redis successfully")
            except (redis.ConnectionError, redis.RedisError) as e:
                logger.warning(
                    f"Redis connection failed: {str(e)}. Using mock implementation."
                )
                # Fall back to mock Redis client if connection fails
                from app.core.redis_mock import MockRedis
                _redis_client = MockRedis()
    
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
        
        # Use first() instead of scalar_one_or_none() to avoid errors if duplicate keys exist
        result = await db.execute(
            select(KeyHistory).filter(KeyHistory.kid == kid)
        )
        key_record = result.scalar_one_or_none()

        if not key_record:
            logger.warning(f"Key with kid {kid} not found in database")
            return None, None

        decrypted_private_key = await decrypt_private_key(key_record.private_key)
        
        logger.debug(f"Retrieved key with kid: {kid}")
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

        # Get current key (most recent key by created_at)
        current_key = await db.execute(
            select(KeyHistory).order_by(KeyHistory.created_at.desc()).limit(1)
        )
        current_key_record = current_key.scalar_one_or_none()

        if not current_key_record:
            raise AuthenticationError("No active key found. Key rotation required.")

        private_key = await decrypt_private_key(current_key_record.private_key)
        kid = current_key_record.kid  # Use kid, not id for the header

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
            headers={"kid": kid}
        )

        logger.debug(
            "Created access token",
            extra={
                "user_id": str(subject),
                "scopes": scopes,
                "jti": jti,
                "kid": kid,
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

        # Get current key (most recent key by created_at)
        current_key = await db.execute(
            select(KeyHistory).order_by(KeyHistory.created_at.desc()).limit(1)
        )
        current_key_record = current_key.scalar_one_or_none()

        if not current_key_record:
            raise AuthenticationError("No active key found. Key rotation required.")

        private_key = await decrypt_private_key(current_key_record.private_key)
        kid = current_key_record.kid  # Use kid, not id for the header

        to_encode = {
            "sub": str(subject),
            "exp": expire,
            "type": "refresh",
            "scopes": scopes,
            "jti": jti,
        }

        encoded_jwt = encode_jwt(
            to_encode,
            private_key,
            algorithm=settings.ALGORITHM,
            headers={"kid": kid}
        )

        logger.debug(
            "Created refresh token",
            extra={
                "user_id": str(subject),
                "scopes": scopes,
                "jti": jti,
                "kid": kid,
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
    """Verify token and return token data."""
    from app.core.config import settings

    try:
        # If db is not provided, get a session
        if db is None:
            from app.db.session import sessionmanager
            async with sessionmanager.session() as session:
                db = session
                
        # Get the kid from the token header
        try:
            headers = jwt.get_unverified_headers(token)
            logger.debug(f"Token headers: {headers}")
            kid = headers.get("kid")
            if not kid:
                logger.error("Token missing kid in header")
                raise AuthenticationError(detail="Invalid token format: missing kid")
        except Exception as e:
            logger.error(f"Error extracting token headers: {str(e)}")
            raise AuthenticationError(detail="Could not parse token")

        # Get the key from database - using execute and scalar_one_or_none for more reliable retrieval
        logger.debug(f"Looking for key with kid: {kid}")
        
        # Try to get the most recent key with this kid first
        result = await db.execute(
            select(KeyHistory)
            .filter(KeyHistory.kid == kid)
            .order_by(KeyHistory.created_at.desc())
        )
        key_record = result.scalar_one_or_none()
        
        # Debug key lookup
        if key_record:
            logger.debug(f"Found key record with kid: {kid}, created at: {key_record.created_at}")
        else:
            logger.warning(f"No key found with kid: {kid}")

        if not key_record:
            # Log all keys in database for debugging
            keys_result = await db.execute(
                select(KeyHistory.kid, KeyHistory.created_at)
                .order_by(KeyHistory.created_at.desc())
            )
            keys_list = keys_result.all()
            logger.debug(f"Available keys in database: {keys_list}")
            
            # Fallback to legacy key from settings as a backup
            logger.warning(f"Key with kid {kid} not found, trying SECRET_KEY")
            try:
                # Try using the SECRET_KEY as fallback
                payload = jwt.decode(
                    token,
                    settings.SECRET_KEY,
                    algorithms=["HS256", settings.ALGORITHM]
                )
                logger.debug(f"Token decoded with SECRET_KEY: {payload}")
            except Exception as e:
                logger.error(f"Fallback decode failed: {str(e)}")
                raise AuthenticationError(detail="Invalid token or key not found")
        else:
            # Load the public key for verification
            try:
                logger.debug(f"Using public key from database for kid: {kid}")
                # Decode the token with the public key
                public_key_pem = key_record.public_key
                logger.debug(f"Using public key: {public_key_pem[:50]}...")
                
                # Attempt to decode token with the public key
                payload = jwt.decode(
                    token,
                    public_key_pem,
                    algorithms=[settings.ALGORITHM]
                )
                logger.debug(f"Token payload successfully decoded: {payload}")
            except jwt.InvalidTokenError as e:
                logger.error(f"JWT validation error: {str(e)}")
                raise AuthenticationError(detail=f"Invalid token: {str(e)}")
            except Exception as e:
                logger.error(f"Error verifying token: {str(e)}", exc_info=True)
                raise AuthenticationError(detail=f"Invalid token signature: {str(e)}")

        # Validate required claims
        sub = payload.get("sub")
        jti = payload.get("jti")
        token_type = payload.get("type")
        scopes = payload.get("scopes")
        
        # Log all claims for debugging
        logger.debug(f"Token claims - sub: {sub}, jti: {jti}, type: {token_type}, scopes: {scopes}")
        
        if not sub:
            logger.error("Token missing sub claim")
            raise AuthenticationError(detail="Invalid token: missing sub claim")
            
        if not jti:
            logger.error("Token missing jti claim")
            raise AuthenticationError(detail="Invalid token: missing jti claim")
        
        # Normalize expected type for comparison
        normalized_expected = expected_type
        if expected_type == "access_token":
            normalized_expected = "access"
        elif expected_type == "refresh_token":
            normalized_expected = "refresh"
            
        # Validate token type
        logger.debug(f"Token type: {token_type}, expected: {expected_type} (normalized: {normalized_expected})")
        if token_type != normalized_expected:
            raise AuthenticationError(
                detail=f"Invalid token type. Expected {expected_type}, got {token_type}"
            )

        # Check if token has been revoked
        revoked_result = await db.execute(
            select(RevokedToken).filter(RevokedToken.jti == jti)
        )
        revoked = revoked_result.scalar_one_or_none()
        if revoked:
            logger.warning(f"Token with jti {jti} has been revoked")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token has been revoked"
            )

        # Extract user_id from sub claim
        try:
            user_id = UUID(sub)
        except ValueError:
            logger.error(f"Invalid user_id format in token: {sub}")
            raise AuthenticationError(detail="Invalid user_id format in token")

        # Create and return token data
        token_data = TokenData(
            user_id=user_id,
            scopes=scopes or [],
            type=token_type,
            jti=jti
        )
        
        logger.debug(f"Successfully verified token for user: {user_id}")
        return token_data

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
    """Extract token from Authorization header or cookie."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]
    
    if settings.USE_COOKIE_AUTH:
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            return refresh_token
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid Authorization header",
        headers={"WWW-Authenticate": "Bearer"}
    )

async def encrypt_credential(credential: str) -> str:
    """Encrypt a credential using Fernet."""
    try:
        return credential_cipher.encrypt(credential.encode()).decode()
    except Exception as e:
        logger.error(f"Error encrypting credential: {str(e)}")
        raise AuthenticationError("Failed to encrypt credential")

async def decrypt_credential(encrypted_credential: str) -> str:
    """Decrypt a credential using Fernet."""
    try:
        return credential_cipher.decrypt(encrypted_credential.encode()).decode()
    except Exception as e:
        logger.error(f"Error decrypting credential: {str(e)}")
        raise AuthenticationError("Failed to decrypt credential")