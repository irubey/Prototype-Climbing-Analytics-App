"""
Tests for the API response validators.

This module verifies that our API response validators correctly
identify valid and invalid API responses.
"""

import pytest
from fastapi import status
from unittest.mock import MagicMock

from app.tests.utils.validators import (
    validate_pagination,
    validate_user_response,
    validate_climb_response,
    validate_response_structure,
    validate_error_response,
    validate_auth_response
)


class TestPaginationValidator:
    """Test the pagination validator functionality."""
    
    def test_valid_pagination(self):
        """Test validation of a valid pagination structure."""
        # Create a valid pagination data structure
        data = {
            "pagination": {
                "page": 1,
                "page_size": 10,
                "total": 100,
                "total_pages": 10
            },
            "items": [{"id": i} for i in range(10)]
        }
        
        # Should not raise any exceptions
        validate_pagination(data, expected_page=1, expected_page_size=10, expected_total=100)
        
    def test_missing_pagination(self):
        """Test validation of a response with missing pagination."""
        data = {"items": [{"id": 1}]}
        
        with pytest.raises(AssertionError):
            validate_pagination(data, expected_page=1, expected_page_size=10, expected_total=100)
            
    def test_incorrect_pagination_values(self):
        """Test validation with incorrect pagination values."""
        data = {
            "pagination": {
                "page": 2,  # Expected page is 1
                "page_size": 10,
                "total": 100,
                "total_pages": 10
            },
            "items": [{"id": i} for i in range(10)]
        }
        
        with pytest.raises(AssertionError):
            validate_pagination(data, expected_page=1, expected_page_size=10, expected_total=100)


class TestUserResponseValidator:
    """Test the user response validator functionality."""
    
    def test_valid_user_response(self):
        """Test validation of a valid user response."""
        # Create a valid user data structure
        user_data = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "created_at": "2023-01-01T00:00:00Z"
        }
        
        # Should not raise any exceptions
        validate_user_response(user_data)
        
    def test_missing_required_fields(self):
        """Test validation of a user response missing required fields."""
        user_data = {
            "id": 1,
            "username": "testuser"
            # Missing email and created_at
        }
        
        with pytest.raises(AssertionError):
            validate_user_response(user_data)
            
    def test_contains_sensitive_fields(self):
        """Test validation of a user response containing sensitive fields."""
        user_data = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "created_at": "2023-01-01T00:00:00Z",
            "password_hash": "securehashedpassword"  # Sensitive field
        }
        
        with pytest.raises(AssertionError):
            validate_user_response(user_data)


class TestClimbResponseValidator:
    """Test the climb response validator functionality."""
    
    def test_valid_climb_response(self):
        """Test validation of a valid climb response."""
        # Create a valid climb data structure
        climb_data = {
            "id": 1,
            "user_id": 1,
            "grade": "5.10a",
            "date": "2023-01-01",
            "route": "Test Route",
            "send_status": "Redpoint",
            "notes": "Great climb!"
        }
        
        # Should not raise any exceptions
        validate_climb_response(climb_data)
        
    def test_missing_required_fields(self):
        """Test validation of a climb response missing required fields."""
        climb_data = {
            "id": 1,
            "user_id": 1,
            # Missing grade, date, route, send_status
            "notes": "Great climb!"
        }
        
        with pytest.raises(AssertionError):
            validate_climb_response(climb_data)


class TestResponseStructureValidator:
    """Test the response structure validator functionality."""
    
    def test_valid_response_structure(self):
        """Test validation of a valid response structure."""
        # Create a mock response
        response = MagicMock()
        response.status_code = status.HTTP_200_OK
        
        # Create a valid data structure
        data = {
            "id": 1,
            "name": "Test",
            "description": "Test description"
        }
        
        # Should not raise any exceptions
        validate_response_structure(
            response,
            data,
            expected_status_code=status.HTTP_200_OK,
            expected_keys=["id", "name"]
        )
        
    def test_incorrect_status_code(self):
        """Test validation with incorrect status code."""
        response = MagicMock()
        response.status_code = status.HTTP_201_CREATED  # Not expected status
        
        data = {"id": 1, "name": "Test"}
        
        with pytest.raises(AssertionError):
            validate_response_structure(
                response,
                data,
                expected_status_code=status.HTTP_200_OK,
                expected_keys=["id", "name"]
            )
            
    def test_missing_expected_keys(self):
        """Test validation with missing expected keys."""
        response = MagicMock()
        response.status_code = status.HTTP_200_OK
        
        data = {"id": 1}  # Missing "name" key
        
        with pytest.raises(AssertionError):
            validate_response_structure(
                response,
                data,
                expected_status_code=status.HTTP_200_OK,
                expected_keys=["id", "name"]
            )


class TestErrorResponseValidator:
    """Test the error response validator functionality."""
    
    def test_valid_error_response(self):
        """Test validation of a valid error response."""
        # Create a mock response
        response = MagicMock()
        response.status_code = status.HTTP_400_BAD_REQUEST
        
        # Create a valid error data structure
        data = {
            "detail": "Validation error",
            "errors": [
                {"loc": ["body", "username"], "msg": "Field required"}
            ]
        }
        
        # Should not raise any exceptions
        validate_error_response(
            response,
            data,
            expected_status_code=status.HTTP_400_BAD_REQUEST
        )
        
    def test_missing_detail_field(self):
        """Test validation of an error response missing the detail field."""
        response = MagicMock()
        response.status_code = status.HTTP_400_BAD_REQUEST
        
        data = {"message": "Error occurred"}  # Missing "detail" key
        
        with pytest.raises(AssertionError):
            validate_error_response(
                response,
                data,
                expected_status_code=status.HTTP_400_BAD_REQUEST
            )
            
    def test_incorrect_error_status(self):
        """Test validation with incorrect error status code."""
        response = MagicMock()
        response.status_code = status.HTTP_404_NOT_FOUND  # Not expected status
        
        data = {"detail": "Resource not found"}
        
        with pytest.raises(AssertionError):
            validate_error_response(
                response,
                data,
                expected_status_code=status.HTTP_400_BAD_REQUEST
            )


class TestAuthResponseValidator:
    """Test the authentication response validator functionality."""
    
    def test_valid_auth_response(self):
        """Test validation of a valid authentication response."""
        # Create a mock response
        response = MagicMock()
        response.status_code = status.HTTP_200_OK
        
        # Create a valid auth data
        data = {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "user": {
                "id": 1,
                "username": "testuser",
                "email": "test@example.com"
            }
        }
        
        # Should not raise any exceptions
        validate_auth_response(response, data)
        
    def test_missing_token(self):
        """Test validation of an auth response missing the token."""
        response = MagicMock()
        response.status_code = status.HTTP_200_OK
        
        data = {
            "token_type": "bearer",
            "user": {
                "id": 1,
                "username": "testuser",
                "email": "test@example.com"
            }
        }
        
        with pytest.raises(AssertionError):
            validate_auth_response(response, data)
            
    def test_empty_token(self):
        """Test validation of an auth response with an empty token."""
        response = MagicMock()
        response.status_code = status.HTTP_200_OK
        
        data = {
            "access_token": "",
            "token_type": "bearer",
            "user": {
                "id": 1,
                "username": "testuser",
                "email": "test@example.com"
            }
        }
        
        with pytest.raises(AssertionError):
            validate_auth_response(response, data) 