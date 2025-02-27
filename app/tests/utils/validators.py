"""
Response validation utilities for API tests.

This module provides helper functions for validating API responses,
ensuring proper structure, content, and compliance with expected formats.
"""

from typing import Any, Dict, List, Optional, Union
import json
from httpx import Response


def validate_pagination(
    response_data: Dict[str, Any],
    expected_page: int = 1,
    expected_page_size: int = 10,
    expected_total: Optional[int] = None
):
    """
    Validate pagination metadata in response.

    Args:
        response_data: The response data dictionary
        expected_page: Expected current page
        expected_page_size: Expected page size
        expected_total: Optional expected total items

    Raises:
        AssertionError: If validation fails
    """
    assert "pagination" in response_data, "Response missing pagination metadata"
    pagination = response_data["pagination"]

    assert pagination["page"] == expected_page, f"Expected page {expected_page}, got {pagination['page']}"
    assert pagination["page_size"] == expected_page_size, f"Expected page_size {expected_page_size}, got {pagination['page_size']}"

    if expected_total is not None:
        assert pagination["total"] == expected_total, f"Expected total {expected_total}, got {pagination['total']}"


def validate_user_response(
    user_data: Dict[str, Any], 
    expected_fields: Optional[List[str]] = None,
    unexpected_fields: Optional[List[str]] = None
):
    """
    Validate user object in response.

    Args:
        user_data: User data dictionary
        expected_fields: List of fields that should be present
        unexpected_fields: List of fields that should not be present

    Raises:
        AssertionError: If validation fails
    """
    # Default expected fields
    if expected_fields is None:
        expected_fields = ["id", "username", "email", "created_at"]

    # Default sensitive fields that should not be present
    if unexpected_fields is None:
        unexpected_fields = ["password", "password_hash", "hashed_password"]

    # Validate expected fields
    for field in expected_fields:
        assert field in user_data, f"User data missing expected field: {field}"

    # Validate that sensitive fields are not present
    for field in unexpected_fields:
        assert field not in user_data, f"User data contains sensitive field: {field}"


def validate_climb_response(
    climb_data: Dict[str, Any],
    expected_fields: Optional[List[str]] = None
):
    """
    Validate climbing session object in response.

    Args:
        climb_data: Climb data dictionary
        expected_fields: List of fields that should be present

    Raises:
        AssertionError: If validation fails
    """
    # Default expected fields
    if expected_fields is None:
        expected_fields = ["id", "user_id", "grade", "date", "route", "send_status"]

    # Validate expected fields
    for field in expected_fields:
        assert field in climb_data, f"Climb data missing expected field: {field}"


def validate_response_structure(
    response: Response,
    data: Dict[str, Any],
    expected_status_code: int,
    expected_keys: Optional[List[str]] = None
):
    """
    Validate the overall structure of an API response.

    Args:
        response: The HTTP response object
        data: The parsed response data
        expected_status_code: Expected HTTP status code
        expected_keys: List of top-level keys expected in the response

    Raises:
        AssertionError: If validation fails
    """
    # Validate status code
    assert response.status_code == expected_status_code, \
        f"Expected status code {expected_status_code}, got {response.status_code}"

    if expected_keys:
        for key in expected_keys:
            assert key in data, f"Response missing expected key: {key}"


def validate_error_response(
    response: Response,
    data: Dict[str, Any],
    expected_status_code: int,
    expected_error_type: Optional[str] = None,
    expected_detail_contains: Optional[str] = None
):
    """
    Validate an error response.

    Args:
        response: The HTTP response object
        data: The parsed response data
        expected_status_code: Expected HTTP status code
        expected_error_type: Expected error type string
        expected_detail_contains: Text that should be in the detail message

    Raises:
        AssertionError: If validation fails
    """
    # Validate status code
    assert response.status_code == expected_status_code, \
        f"Expected status code {expected_status_code}, got {response.status_code}"
    
    # Check that the response contains detail field
    assert "detail" in data, "Error response missing 'detail' field"
    
    # If error type is specified, validate it
    if expected_error_type:
        if isinstance(data["detail"], list) and len(data["detail"]) > 0:
            # Pydantic validation errors
            has_expected_type = any(
                item.get("type") == expected_error_type for item in data["detail"]
            )
            assert has_expected_type, f"Error response doesn't contain expected type: {expected_error_type}"
        elif isinstance(data["detail"], dict):
            # Custom error format
            assert data["detail"].get("type") == expected_error_type, \
                f"Expected error type {expected_error_type}, got {data['detail'].get('type')}"
    
    # If detail content is specified, validate it
    if expected_detail_contains:
        if isinstance(data["detail"], str):
            assert expected_detail_contains in data["detail"], \
                f"Error detail doesn't contain: {expected_detail_contains}"
        elif isinstance(data["detail"], dict) and "msg" in data["detail"]:
            assert expected_detail_contains in data["detail"]["msg"], \
                f"Error detail doesn't contain: {expected_detail_contains}"
        elif isinstance(data["detail"], list) and len(data["detail"]) > 0:
            has_expected_detail = any(
                expected_detail_contains in str(item.get("msg", "")) for item in data["detail"]
            )
            assert has_expected_detail, f"Error details don't contain: {expected_detail_contains}"


def validate_auth_response(
    response: Response,
    data: Dict[str, Any],
    expected_token_type: str = "bearer"
):
    """
    Validate an authentication response.

    Args:
        response: The HTTP response object
        data: The parsed response data
        expected_token_type: Expected token type

    Raises:
        AssertionError: If validation fails
    """
    # Validate status code
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    
    # Check token structure
    assert "access_token" in data, "Auth response missing access_token"
    assert "token_type" in data, "Auth response missing token_type"
    
    # Validate token type
    assert data["token_type"].lower() == expected_token_type.lower(), \
        f"Expected token type {expected_token_type}, got {data['token_type']}"
    
    # Validate token is non-empty
    assert data["access_token"], "Empty access token" 