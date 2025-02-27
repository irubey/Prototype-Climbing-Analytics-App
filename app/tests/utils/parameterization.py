"""
Test parameterization utilities.

This module provides utilities for creating structured, parameterized tests
that improve readability, maintainability, and test coverage.
"""

from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple, Union
import pytest

# To avoid pytest collection issues, use a plain class instead of NamedTuple
class ParamTestCase:
    """
    Structured test case definition for parameterized tests.
    
    This class provides a consistent structure for defining test cases
    used in parameterized tests, making tests more organized and maintainable.
    """
    __test__ = False  # Prevent pytest from collecting this class as a test
    
    def __init__(
        self,
        id: str,
        input: Dict[str, Any],
        expected: Dict[str, Any],
        description: Optional[str] = None,
        marks: Optional[List[Callable]] = None
    ):
        self.id = id  # Unique identifier for the test case
        self.input = input  # Input parameters
        self.expected = expected  # Expected results  
        self.description = description  # Optional description
        self.marks = marks  # Optional pytest marks


# For backward compatibility
TestCase = ParamTestCase


def auth_test_cases() -> List[TestCase]:
    """
    Generate authentication test cases.
    
    This function provides common test cases for authentication endpoints,
    covering various scenarios like valid login, invalid credentials, etc.
    
    Returns:
        List of TestCase objects for testing authentication
    """
    return [
        TestCase(
            id="valid_credentials",
            input={"email": "test@example.com", "password": "ValidPassword123!"},
            expected={"status_code": 200, "token_type": "bearer"},
            description="Login with valid credentials succeeds"
        ),
        TestCase(
            id="invalid_password",
            input={"email": "test@example.com", "password": "WrongPassword"},
            expected={"status_code": 401, "detail": "Invalid credentials"},
            description="Login with invalid password fails"
        ),
        TestCase(
            id="non_existent_user",
            input={"email": "nonexistent@example.com", "password": "AnyPassword123!"},
            expected={"status_code": 401, "detail": "Invalid credentials"},
            description="Login with non-existent user fails"
        ),
        TestCase(
            id="missing_email",
            input={"password": "ValidPassword123!"},
            expected={"status_code": 422, "detail": "field required"},
            description="Login without email fails validation"
        ),
        TestCase(
            id="missing_password",
            input={"email": "test@example.com"},
            expected={"status_code": 422, "detail": "field required"},
            description="Login without password fails validation"
        ),
        TestCase(
            id="invalid_email_format",
            input={"email": "invalid-email", "password": "ValidPassword123!"},
            expected={"status_code": 422, "detail": "valid email"},
            description="Login with invalid email format fails validation"
        )
    ]


def user_profile_test_cases() -> List[TestCase]:
    """
    Generate user profile test cases.
    
    This function provides common test cases for user profile endpoints,
    covering scenarios like profile updates, validation errors, etc.
    
    Returns:
        List of TestCase objects for testing user profiles
    """
    return [
        TestCase(
            id="valid_update",
            input={
                "username": "updated_username",
                "experience_level": "advanced",
                "location": "Boulder, CO"
            },
            expected={
                "status_code": 200,
                "username": "updated_username",
                "experience_level": "advanced"
            },
            description="Valid profile update succeeds"
        ),
        TestCase(
            id="invalid_username",
            input={
                "username": "a",  # Too short
                "experience_level": "advanced"
            },
            expected={
                "status_code": 422,
                "detail": "ensure this value has at least"
            },
            description="Update with invalid username fails validation"
        ),
        TestCase(
            id="invalid_experience_level",
            input={
                "username": "valid_username",
                "experience_level": "super_elite"  # Invalid enum value
            },
            expected={
                "status_code": 422,
                "detail": "permitted values"
            },
            description="Update with invalid experience level fails validation"
        ),
        TestCase(
            id="empty_update",
            input={},
            expected={
                "status_code": 400,
                "detail": "No valid fields to update"
            },
            description="Empty update fails with appropriate error"
        )
    ]


def subscription_test_cases() -> List[TestCase]:
    """
    Generate subscription management test cases.
    
    This function provides common test cases for subscription endpoints,
    covering scenarios like upgrades, downgrades, payment errors, etc.
    
    Returns:
        List of TestCase objects for testing subscriptions
    """
    return [
        TestCase(
            id="valid_subscription",
            input={
                "payment_method_id": "pm_valid_123",
                "plan": "premium_monthly"
            },
            expected={
                "status_code": 200,
                "status": "active",
                "tier": "PREMIUM"
            },
            description="Valid subscription creation succeeds"
        ),
        TestCase(
            id="invalid_payment_method",
            input={
                "payment_method_id": "pm_invalid_123",
                "plan": "premium_monthly"
            },
            expected={
                "status_code": 400,
                "detail": "Invalid payment method"
            },
            description="Subscription with invalid payment method fails"
        ),
        TestCase(
            id="missing_plan",
            input={
                "payment_method_id": "pm_valid_123"
            },
            expected={
                "status_code": 422,
                "detail": "field required"
            },
            description="Subscription without plan fails validation"
        ),
        TestCase(
            id="invalid_plan",
            input={
                "payment_method_id": "pm_valid_123",
                "plan": "ultra_premium"  # Non-existent plan
            },
            expected={
                "status_code": 400,
                "detail": "Invalid plan"
            },
            description="Subscription with invalid plan fails"
        ),
        TestCase(
            id="subscription_cancellation",
            input={
                "cancel": True
            },
            expected={
                "status_code": 200,
                "status": "canceled"
            },
            description="Subscription cancellation succeeds"
        )
    ]


def pagination_test_cases() -> List[TestCase]:
    """
    Generate pagination test cases.
    
    This function provides common test cases for paginated endpoints,
    covering various page sizes, page numbers, and edge cases.
    
    Returns:
        List of TestCase objects for testing pagination
    """
    return [
        TestCase(
            id="default_pagination",
            input={},
            expected={
                "status_code": 200,
                "page": 1,
                "page_size": 10,
                "has_items": True
            },
            description="Default pagination parameters work correctly"
        ),
        TestCase(
            id="custom_page_size",
            input={
                "page_size": 25
            },
            expected={
                "status_code": 200,
                "page": 1,
                "page_size": 25,
                "has_items": True
            },
            description="Custom page size works correctly"
        ),
        TestCase(
            id="second_page",
            input={
                "page": 2,
                "page_size": 5
            },
            expected={
                "status_code": 200,
                "page": 2,
                "page_size": 5
            },
            description="Navigating to second page works correctly"
        ),
        TestCase(
            id="page_out_of_bounds",
            input={
                "page": 9999
            },
            expected={
                "status_code": 200,
                "page": 9999,
                "page_size": 10,
                "has_items": False,
                "items": []
            },
            description="Page beyond available data returns empty list, not error"
        ),
        TestCase(
            id="invalid_page",
            input={
                "page": -1
            },
            expected={
                "status_code": 422,
                "detail": "greater than or equal to 1"
            },
            description="Negative page number fails validation"
        ),
        TestCase(
            id="invalid_page_size",
            input={
                "page_size": 1001  # Exceeds maximum
            },
            expected={
                "status_code": 422,
                "detail": "less than or equal to"
            },
            description="Page size exceeding maximum fails validation"
        )
    ] 