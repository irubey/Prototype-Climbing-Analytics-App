"""
Centralized exception handling module.

This module provides consistent error handling across the application with:
- Structured error responses
- Detailed logging
- HTTP status code mapping
- Error documentation for OpenAPI
"""

from typing import Any, Dict, Union
from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import stripe
import traceback

from app.core.exceptions import (
    SendSageException,
    DatabaseError,
    AuthenticationError,
    AuthorizationError,
    PaymentRequired,
    ResourceNotFound,
    ValidationError,
    RateLimitExceeded,
    ExternalServiceError,
    ServiceUnavailable,
    LogbookProcessingError,
    LogbookConnectionError,
    ScrapingError,
    SSEError
)
from app.core.logging import logger

def create_error_response(
    status_code: int,
    message: str,
    error_type: str,
    details: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response dictionary.
    
    Args:
        status_code: HTTP status code
        message: Error message
        error_type: Type of error
        details: Additional error details
        
    Returns:
        Structured error response dictionary
    """
    response = {
        "error": {
            "status_code": status_code,
            "message": message,
            "type": error_type
        }
    }
    if details:
        response["error"]["details"] = details
    return response

async def send_sage_exception_handler(
    request: Request,
    exc: SendSageException
) -> JSONResponse:
    """Handle custom Send Sage exceptions with structured logging."""
    logger.error(
        "SendSage application error",
        extra={
            "error_type": exc.__class__.__name__,
            "error": str(exc.detail),
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code
        }
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            status_code=exc.status_code,
            message=str(exc.detail),
            error_type=exc.__class__.__name__
        )
    )

async def sqlalchemy_error_handler(
    request: Request,
    exc: SQLAlchemyError
) -> JSONResponse:
    """Handle database-related errors with proper logging."""
    error_details = {
        "traceback": traceback.format_exc(),
        "statement": str(getattr(exc, 'statement', 'No statement available')),
        "params": str(getattr(exc, 'params', 'No parameters available'))
    }
    
    logger.error(
        "Database error",
        extra={
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "path": request.url.path,
            "method": request.method,
            **error_details
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Database error occurred",
            error_type="DatabaseError",
            details=error_details
        )
    )

async def stripe_error_handler(
    request: Request,
    exc: stripe.StripeError
) -> JSONResponse:
    """Handle Stripe payment processing errors."""
    error_details = {
        "code": getattr(exc, 'code', None),
        "param": getattr(exc, 'param', None),
        "stripe_id": getattr(exc, 'stripe_id', None)
    }
    
    logger.error(
        "Stripe payment error",
        extra={
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "path": request.url.path,
            "method": request.method,
            **error_details
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content=create_error_response(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            message=str(exc),
            error_type="PaymentError",
            details=error_details
        )
    )

async def validation_error_handler(
    request: Request,
    exc: ValidationError
) -> JSONResponse:
    """Handle data validation errors."""
    logger.warning(
        "Validation error",
        extra={
            "error_type": "ValidationError",
            "error": str(exc),
            "path": request.url.path,
            "method": request.method,
            "validation_errors": exc.errors() if hasattr(exc, 'errors') else None
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=str(exc),
            error_type="ValidationError",
            details={"errors": exc.errors() if hasattr(exc, 'errors') else None}
        )
    )

async def logbook_error_handler(
    request: Request,
    exc: Union[LogbookProcessingError, LogbookConnectionError]
) -> JSONResponse:
    """Handle logbook-related errors."""
    logger.error(
        "Logbook error",
        extra={
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "path": request.url.path,
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(exc),
            error_type=exc.__class__.__name__
        )
    )

async def scraping_error_handler(
    request: Request,
    exc: ScrapingError
) -> JSONResponse:
    """Handle web scraping errors."""
    logger.error(
        "Scraping error",
        extra={
            "error_type": "ScrapingError",
            "error": str(exc),
            "path": request.url.path,
            "method": request.method,
            "url": getattr(exc, 'url', None)
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=create_error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message=str(exc),
            error_type="ScrapingError",
            details={"url": getattr(exc, 'url', None)}
        )
    )

async def sse_error_handler(
    request: Request,
    exc: SSEError
) -> JSONResponse:
    """Handle Server-Sent Events errors."""
    error_details = {
        "user_id": exc.context.get("user_id"),
        "connection_state": exc.context.get("connection_state"),
        "queue_size": exc.context.get("queue_size")
    }
    
    logger.error(
        "SSE error",
        extra={
            "error_type": "SSEError",
            "error": str(exc),
            "path": request.url.path,
            "method": request.method,
            **error_details
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(exc),
            error_type="SSEError",
            details=error_details
        )
    )

async def general_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handle any unhandled exceptions."""
    logger.error(
        "Unhandled exception",
        extra={
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc()
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="An unexpected error occurred",
            error_type="InternalServerError",
            details={"error": str(exc)} if not isinstance(exc, SendSageException) else None
        )
    )

def get_error_responses(endpoint_name: str) -> Dict[int, Dict[str, Any]]:
    """
    Get OpenAPI documentation for possible error responses.
    
    Args:
        endpoint_name: Name of the endpoint to get error responses for
        
    Returns:
        Dictionary mapping status codes to response schemas
    """
    common_responses = {
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "example": create_error_response(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        message="Could not validate credentials",
                        error_type="AuthenticationError"
                    )
                }
            }
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": create_error_response(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        message="An unexpected error occurred",
                        error_type="InternalServerError"
                    )
                }
            }
        }
    }
    
    # Add endpoint-specific error responses
    if endpoint_name == "logbook_connect":
        common_responses[status.HTTP_503_SERVICE_UNAVAILABLE] = {
            "description": "Logbook service unavailable",
            "content": {
                "application/json": {
                    "example": create_error_response(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        message="Could not connect to logbook service",
                        error_type="LogbookConnectionError"
                    )
                }
            }
        }
    
    return common_responses 