"""
Unit tests for email service module.

These tests verify that the email service functions work correctly,
including template handling, error conditions, and specialized email types.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from pathlib import Path
from pydantic import EmailStr

from app.core.email import (
    send_email, send_password_reset_email, 
    send_password_change_email, send_new_account_email,
    conf, fastmail
)
from app.core.exceptions import ExternalServiceError


@pytest.mark.asyncio
@patch("app.core.email.fastmail")
@patch("app.core.email.logger")
@patch("app.core.email.settings")
async def test_send_email_basic(mock_settings, mock_logger, mock_fastmail):
    """Test basic email sending functionality."""
    # Setup
    mock_settings.TESTING = False
    mock_fastmail.send_message = AsyncMock()
    
    # Execute
    await send_email(
        email_to="test@example.com",
        subject="Test Subject",
        body="Test Body"
    )
    
    # Verify
    mock_fastmail.send_message.assert_called_once()
    mock_logger.info.assert_any_call(
        "Sending email",
        extra={
            "recipient": "test@example.com",
            "subject": "Test Subject",
            "template": None,
            "has_template_body": False
        }
    )
    mock_logger.info.assert_any_call(
        "Email sent successfully",
        extra={
            "recipient": "test@example.com",
            "subject": "Test Subject"
        }
    )


@pytest.mark.asyncio
@patch("app.core.email.fastmail")
@patch("app.core.email.logger")
@patch("app.core.email.settings")
async def test_send_email_with_template(mock_settings, mock_logger, mock_fastmail):
    """Test email sending with a template."""
    # Setup
    mock_settings.TESTING = False
    mock_fastmail.send_message = AsyncMock()
    
    template_body = {"name": "Test User", "link": "https://example.com"}
    
    # Execute
    await send_email(
        email_to="test@example.com",
        subject="Test Subject",
        body="Test Body",
        template_name="test_template.html",
        template_body=template_body
    )
    
    # Verify
    mock_fastmail.send_message.assert_called_once()
    # Verify template_name was passed to send_message
    assert mock_fastmail.send_message.call_args[1]["template_name"] == "test_template.html"
    mock_logger.info.assert_any_call(
        "Sending email",
        extra={
            "recipient": "test@example.com",
            "subject": "Test Subject",
            "template": "test_template.html",
            "has_template_body": True
        }
    )


@pytest.mark.asyncio
@patch("app.core.email.fastmail")
@patch("app.core.email.logger")
@patch("app.core.email.settings")
async def test_send_email_testing_mode(mock_settings, mock_logger, mock_fastmail):
    """Test email sending in testing mode (should suppress actual sending)."""
    # Setup
    mock_settings.TESTING = True
    mock_fastmail.send_message = AsyncMock()
    
    # Execute
    await send_email(
        email_to="test@example.com",
        subject="Test Subject",
        body="Test Body"
    )
    
    # Verify
    mock_fastmail.send_message.assert_not_called()
    mock_logger.info.assert_any_call(
        "Email sending suppressed in test environment",
        extra={
            "recipient": "test@example.com",
            "subject": "Test Subject"
        }
    )


@pytest.mark.asyncio
@patch("app.core.email.fastmail")
@patch("app.core.email.logger")
@patch("app.core.email.settings")
async def test_send_email_error_handling(mock_settings, mock_logger, mock_fastmail):
    """Test error handling during email sending."""
    # Setup
    mock_settings.TESTING = False
    mock_fastmail.send_message = AsyncMock(side_effect=Exception("SMTP error"))
    
    # Execute and verify exception is raised
    with pytest.raises(ExternalServiceError) as excinfo:
        await send_email(
            email_to="test@example.com",
            subject="Test Subject",
            body="Test Body"
        )
    
    # Verify error is properly logged
    assert "Failed to send email" in str(excinfo.value.detail)
    mock_logger.error.assert_called_once_with(
        "Failed to send email",
        extra={
            "recipient": "test@example.com",
            "subject": "Test Subject",
            "template": None,
            "error": "SMTP error",
            "error_type": "Exception",
            "service_name": "email"
        }
    )


@pytest.mark.asyncio
@patch("app.core.email.fastmail")
@patch("app.core.email.logger")
@patch("app.core.email.settings")
async def test_send_email_error_in_testing_mode(mock_settings, mock_logger, mock_fastmail):
    """Test error handling during email sending in testing mode (should not raise)."""
    # Setup
    mock_settings.TESTING = True
    mock_fastmail.send_message = AsyncMock(side_effect=Exception("SMTP error"))
    
    # Execute - should not raise an exception in testing mode
    await send_email(
        email_to="test@example.com",
        subject="Test Subject",
        body="Test Body"
    )
    
    # Verify error is logged but exception is not propagated
    mock_logger.error.assert_not_called()  # Error logging is skipped because send_message is never called
    mock_fastmail.send_message.assert_not_called()


@pytest.mark.asyncio
@patch("app.core.email.send_email")
@patch("app.core.email.settings")
async def test_send_password_reset_email(mock_settings, mock_send_email):
    """Test password reset email functionality."""
    # Setup
    mock_settings.SERVER_HOST = "https://example.com"
    mock_settings.PROJECT_NAME = "Test Project"
    mock_settings.GMAIL_DEFAULT_SENDER = "support@example.com"
    mock_send_email.return_value = None
    
    # Execute
    await send_password_reset_email(
        email_to="user@example.com",
        token="test-reset-token",
        username="testuser"
    )
    
    # Verify
    mock_send_email.assert_called_once()
    call_args = mock_send_email.call_args[1]
    
    assert call_args["email_to"] == "user@example.com"
    assert "Password Reset" in call_args["subject"]
    assert call_args["template_name"] == "reset_password.html"
    
    # Verify template variables
    template_body = call_args["template_body"]
    assert template_body["username"] == "testuser"
    assert "test-reset-token" in template_body["reset_link"]
    assert template_body["project_name"] == "Test Project"
    assert template_body["support_email"] == "support@example.com"


@pytest.mark.asyncio
@patch("app.core.email.send_email")
@patch("app.core.email.settings")
async def test_send_password_change_email(mock_settings, mock_send_email):
    """Test password change email functionality."""
    # Setup
    mock_settings.SERVER_HOST = "https://example.com"
    mock_settings.PROJECT_NAME = "Test Project"
    mock_settings.GMAIL_DEFAULT_SENDER = "support@example.com"
    mock_send_email.return_value = None
    
    # Execute
    await send_password_change_email(
        email_to="user@example.com",
        username="testuser"
    )
    
    # Verify
    mock_send_email.assert_called_once()
    call_args = mock_send_email.call_args[1]
    
    assert call_args["email_to"] == "user@example.com"
    assert "Password Changed" in call_args["subject"]
    assert call_args["template_name"] == "password_change.html"
    
    # Verify template variables
    template_body = call_args["template_body"]
    assert template_body["username"] == "testuser"
    assert template_body["project_name"] == "Test Project"
    assert "login_link" in template_body
    assert template_body["support_email"] == "support@example.com"


@pytest.mark.asyncio
@patch("app.core.email.send_email")
@patch("app.core.email.settings")
async def test_send_new_account_email(mock_settings, mock_send_email):
    """Test new account email functionality."""
    # Setup
    mock_settings.SERVER_HOST = "https://example.com"
    mock_settings.PROJECT_NAME = "Test Project"
    mock_settings.GMAIL_DEFAULT_SENDER = "support@example.com"
    mock_send_email.return_value = None
    
    # Execute
    await send_new_account_email(
        email_to="newuser@example.com",
        username="newuser"
    )
    
    # Verify
    mock_send_email.assert_called_once()
    call_args = mock_send_email.call_args[1]
    
    assert call_args["email_to"] == "newuser@example.com"
    assert "Welcome" in call_args["subject"]
    assert call_args["template_name"] == "new_account.html"
    
    # Verify template variables
    template_body = call_args["template_body"]
    assert template_body["username"] == "newuser"
    assert template_body["project_name"] == "Test Project"
    assert "login_link" in template_body
    assert template_body["support_email"] == "support@example.com"


@pytest.mark.asyncio
@patch("app.core.email.MessageSchema")
@patch("app.core.email.fastmail")
@patch("app.core.email.logger")
@patch("app.core.email.settings")
async def test_message_schema_creation(mock_settings, mock_logger, mock_fastmail, mock_message_schema):
    """Test that MessageSchema is created with correct parameters."""
    # Setup
    mock_settings.TESTING = False
    mock_fastmail.send_message = AsyncMock()
    mock_message_schema.return_value = "test_message_object"
    
    # Execute
    await send_email(
        email_to="test@example.com",
        subject="Test Subject",
        body="Test Body"
    )
    
    # Verify MessageSchema creation
    mock_message_schema.assert_called_once_with(
        subject="Test Subject",
        recipients=["test@example.com"],
        body="Test Body",
        template_body={},
        subtype="html"
    )


def test_fastmail_configuration():
    """Test that FastMail is configured correctly."""
    # Verify configuration
    assert conf.MAIL_PORT == 587
    assert conf.MAIL_SERVER == "smtp.gmail.com"
    assert conf.MAIL_STARTTLS is True
    assert conf.MAIL_SSL_TLS is False
    assert conf.USE_CREDENTIALS is True
    
    # Verify template folder is a Path object and points to the right location
    assert isinstance(conf.TEMPLATE_FOLDER, Path)
    assert "templates" in str(conf.TEMPLATE_FOLDER)
    assert "email" in str(conf.TEMPLATE_FOLDER) 