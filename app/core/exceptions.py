"""
Custom exception classes for the Send Sage application.

This module defines a hierarchy of application-specific exceptions that:
- Provide consistent error handling
- Map to appropriate HTTP status codes
- Include detailed error messages
- Support additional context and headers
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException, status

class SendSageException(HTTPException):
    """
    Base exception class for Send Sage application.
    
    All application-specific exceptions should inherit from this class
    to ensure consistent error handling and response formatting.
    """
    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the exception with status code, detail message, and optional context.
        
        Args:
            status_code: HTTP status code
            detail: Error message
            headers: Optional response headers
            context: Optional additional context for logging
        """
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.context = context or {}

class DatabaseError(SendSageException):
    """Raised when database operations fail."""
    def __init__(
        self,
        detail: str = "Database operation failed",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            context=context
        )

class AuthenticationError(SendSageException):
    """Raised for authentication-related failures."""
    def __init__(
        self,
        detail: str = "Authentication failed",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
            context=context
        )

class AuthorizationError(SendSageException):
    """Raised when user lacks required permissions."""
    def __init__(
        self,
        detail: str = "Not authorized",
        headers: Optional[Dict[str, str]] = None
    ) -> None:
        """Initialize the exception with status code 403."""
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            headers=headers
        )

class PaymentRequired(SendSageException):
    """Raised when attempting to access premium features without subscription."""
    def __init__(
        self,
        detail: str = "Premium subscription required",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail,
            context=context
        )

class ResourceNotFound(SendSageException):
    """Raised when requested resource does not exist."""
    def __init__(
        self,
        detail: str = "Resource not found",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            context=context
        )

class ValidationError(SendSageException):
    """Raised when request data fails validation."""
    def __init__(
        self,
        detail: str = "Validation error",
        errors: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        context = context or {}
        if errors:
            context["validation_errors"] = errors
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            context=context
        )

class RateLimitExceeded(SendSageException):
    """Raised when request rate limit is exceeded."""
    def __init__(
        self,
        detail: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers=headers,
            context=context
        )

class ExternalServiceError(SendSageException):
    """Raised when external service integration fails."""
    def __init__(
        self,
        detail: str = "External service error",
        service_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        context = context or {}
        if service_name:
            context["service_name"] = service_name
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
            context=context
        )

class ServiceUnavailable(SendSageException):
    """Raised when service is temporarily unavailable."""
    def __init__(
        self,
        detail: str = "Service temporarily unavailable",
        retry_after: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            headers=headers,
            context=context
        )

class DataSourceError(SendSageException):
    """Raised when external data source operations fail."""
    def __init__(self, detail: str = "Data source operation failed"):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail
        )

class LogbookProcessingError(SendSageException):
    """Raised when logbook data processing fails."""
    def __init__(
        self,
        detail: str = "Logbook processing failed",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            context=context
        )

class LogbookConnectionError(SendSageException):
    """Raised when connection to logbook service fails."""
    def __init__(
        self,
        detail: str = "Failed to connect to logbook service",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            context=context
        )

class ScrapingError(SendSageException):
    """Raised when web scraping operations fail."""
    def __init__(
        self,
        detail: str = "Web scraping operation failed",
        url: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        context = context or {}
        if url:
            context["url"] = url
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            context=context
        ) 