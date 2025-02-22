"""
Email service module.

This module provides email functionality using FastMail with support for:
- Template-based emails
- Structured error handling
- Async operation
- Logging and monitoring
"""

from typing import Optional, Dict, Any
from pathlib import Path
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr

from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import logger

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=settings.GMAIL_USERNAME,
    MAIL_PASSWORD=settings.GMAIL_PASSWORD,
    MAIL_FROM=settings.GMAIL_DEFAULT_SENDER,
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    TEMPLATE_FOLDER=Path(__file__).parent.parent / "templates" / "email",
    SUPPRESS_SEND=settings.TESTING  # Suppress email sending in test environment
)

fastmail = FastMail(conf)

async def send_email(
    email_to: str,
    subject: str,
    body: str,
    template_name: Optional[str] = None,
    template_body: Optional[Dict[str, Any]] = None
) -> None:
    """
    Send an email using FastMail with comprehensive error handling.
    
    Args:
        email_to: Recipient email address
        subject: Email subject
        body: Plain text body (used if template_name is None)
        template_name: Optional template file name
        template_body: Optional template variables
        
    Raises:
        ExternalServiceError: If email sending fails
    """
    try:
        message = MessageSchema(
            subject=subject,
            recipients=[email_to],
            body=body,
            template_body=template_body or {},
            subtype="html"
        )
        
        logger.info(
            "Sending email",
            extra={
                "recipient": email_to,
                "subject": subject,
                "template": template_name,
                "has_template_body": bool(template_body)
            }
        )

        # Skip actual email sending in test environment
        if settings.TESTING:
            logger.info(
                "Email sending suppressed in test environment",
                extra={
                    "recipient": email_to,
                    "subject": subject
                }
            )
            return

        if template_name:
            await fastmail.send_message(message, template_name=template_name)
        else:
            await fastmail.send_message(message)
            
        logger.info(
            "Email sent successfully",
            extra={
                "recipient": email_to,
                "subject": subject
            }
        )
        
    except Exception as e:
        error_context = {
            "recipient": email_to,
            "subject": subject,
            "template": template_name,
            "error": str(e),
            "error_type": type(e).__name__
        }
        logger.error("Failed to send email", extra=error_context)
        
        # Don't raise error in test environment
        if not settings.TESTING:
            raise ExternalServiceError(
                detail="Failed to send email",
                service_name="email",
                context=error_context
            )

async def send_password_reset_email(
    email_to: EmailStr,
    token: str,
    username: str
) -> None:
    """
    Send password reset email with token.
    
    Args:
        email_to: User's email address
        token: Password reset token
        username: User's username
        
    Raises:
        ExternalServiceError: If email sending fails
    """
    reset_link = f"{settings.SERVER_HOST}/reset-password?token={token}"
    
    template_body = {
        "username": username,
        "reset_link": reset_link,
        "project_name": settings.PROJECT_NAME,
        "support_email": settings.GMAIL_DEFAULT_SENDER
    }
    
    await send_email(
        email_to=email_to,
        subject=f"{settings.PROJECT_NAME} - Password Reset Request",
        body="",  # Body will be provided by template
        template_name="reset_password.html",
        template_body=template_body
    )

async def send_new_account_email(
    email_to: EmailStr,
    username: str
) -> None:
    """
    Send welcome email for new account registration.
    
    Args:
        email_to: User's email address
        username: User's username
        
    Raises:
        ExternalServiceError: If email sending fails
    """
    template_body = {
        "username": username,
        "project_name": settings.PROJECT_NAME,
        "login_link": f"{settings.SERVER_HOST}/login",
        "support_email": settings.GMAIL_DEFAULT_SENDER
    }
    
    await send_email(
        email_to=email_to,
        subject=f"Welcome to {settings.PROJECT_NAME}",
        body="",  # Body will be provided by template
        template_name="new_account.html",
        template_body=template_body
    ) 