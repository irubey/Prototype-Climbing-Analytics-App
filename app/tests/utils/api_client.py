"""
Enhanced API client for testing REST endpoints.

This module provides a customized API client for testing HTTP endpoints
with additional helpers for authentication, request handling, and response validation.
"""

from httpx import AsyncClient, Response, ASGITransport
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import create_access_token


class TestApiClient:
    """
    API test client with authentication and request helpers.
    
    This class provides an enhanced HTTP client for testing API endpoints
    with built-in support for authentication, common request patterns,
    and test-specific utilities.
    """

    def __init__(self, app: FastAPI, base_url: str = "http://test"):
        """
        Initialize test client.

        Args:
            app: The FastAPI application
            base_url: Base URL for requests
        """
        self.app = app
        self.base_url = base_url
        # Create AsyncClient directly with ASGITransport
        self.client = AsyncClient(
            base_url=base_url,
            transport=ASGITransport(app=app)
        )
        self.auth_headers = {}

    @property
    def headers(self) -> Dict[str, str]:
        """Get the current headers."""
        return self.auth_headers

    async def authenticate(
        self,
        user_id: Union[int, str],
        scopes: Optional[List[str]] = None,
        db_session = None
    ):
        """
        Authenticate client with user credentials.

        Args:
            user_id: User ID to authenticate as
            scopes: Optional authorization scopes
            db_session: Database session for token creation

        Returns:
            Self for method chaining
        """
        if scopes is None:
            scopes = ["user"]

        # Commented out to avoid dependency on create_access_token
        # which requires a complex setup for testing
        # token = await create_access_token(
        #     subject=str(user_id),
        #     scopes=scopes,
        #     jti=str(uuid4()),
        #     db=db_session
        # )

        # Using a mock token for testing
        token = f"mock_token_{user_id}"

        self.auth_headers = {"Authorization": f"Bearer {token}"}
        return self

    async def get(
        self, 
        url: str, 
        authenticated: bool = True, 
        **kwargs
    ) -> Response:
        """
        Perform GET request.

        Args:
            url: Endpoint URL
            authenticated: Whether to include auth headers
            **kwargs: Additional request parameters

        Returns:
            Response object
        """
        headers = kwargs.get("headers", {})
        if authenticated:
            headers.update(self.auth_headers)
        kwargs["headers"] = headers

        return await self.client.get(url, **kwargs)

    async def post(
        self, 
        url: str, 
        data: Any = None, 
        json: Dict = None,
        authenticated: bool = True, 
        **kwargs
    ) -> Response:
        """
        Perform POST request.

        Args:
            url: Endpoint URL
            data: Form data
            json: JSON payload
            authenticated: Whether to include auth headers
            **kwargs: Additional request parameters

        Returns:
            Response object
        """
        headers = kwargs.get("headers", {})
        if authenticated:
            headers.update(self.auth_headers)
        kwargs["headers"] = headers

        return await self.client.post(url, data=data, json=json, **kwargs)

    async def put(
        self, 
        url: str, 
        data: Any = None, 
        json: Dict = None,
        authenticated: bool = True, 
        **kwargs
    ) -> Response:
        """
        Perform PUT request.

        Args:
            url: Endpoint URL
            data: Form data
            json: JSON payload
            authenticated: Whether to include auth headers
            **kwargs: Additional request parameters

        Returns:
            Response object
        """
        headers = kwargs.get("headers", {})
        if authenticated:
            headers.update(self.auth_headers)
        kwargs["headers"] = headers

        return await self.client.put(url, data=data, json=json, **kwargs)

    async def patch(
        self, 
        url: str, 
        data: Any = None, 
        json: Dict = None,
        authenticated: bool = True, 
        **kwargs
    ) -> Response:
        """
        Perform PATCH request.

        Args:
            url: Endpoint URL
            data: Form data
            json: JSON payload
            authenticated: Whether to include auth headers
            **kwargs: Additional request parameters

        Returns:
            Response object
        """
        headers = kwargs.get("headers", {})
        if authenticated:
            headers.update(self.auth_headers)
        kwargs["headers"] = headers

        return await self.client.patch(url, data=data, json=json, **kwargs)

    async def delete(
        self, 
        url: str, 
        authenticated: bool = True, 
        **kwargs
    ) -> Response:
        """
        Perform DELETE request.

        Args:
            url: Endpoint URL
            authenticated: Whether to include auth headers
            **kwargs: Additional request parameters

        Returns:
            Response object
        """
        headers = kwargs.get("headers", {})
        if authenticated:
            headers.update(self.auth_headers)
        kwargs["headers"] = headers

        return await self.client.delete(url, **kwargs)
    
    async def close(self):
        """Close the client session."""
        await self.client.aclose()
    
    # Additional helper methods for common testing patterns
    
    async def paginated_get(
        self, 
        url: str, 
        page: int = 1, 
        page_size: int = 10, 
        **kwargs
    ) -> Response:
        """
        Perform a GET request with pagination parameters.
        
        Args:
            url: Endpoint URL
            page: Page number
            page_size: Number of items per page
            **kwargs: Additional request parameters
            
        Returns:
            Response object
        """
        params = kwargs.get("params", {})
        params.update({"page": page, "page_size": page_size})
        kwargs["params"] = params
        
        return await self.get(url, **kwargs)
    
    async def upload_file(
        self, 
        url: str, 
        file_path: str, 
        field_name: str = "file", 
        data: Dict[str, Any] = None,
        **kwargs
    ) -> Response:
        """
        Upload a file to the specified endpoint.
        
        Args:
            url: Endpoint URL
            file_path: Path to the file to upload
            field_name: Form field name for the file
            data: Additional form data
            **kwargs: Additional request parameters
            
        Returns:
            Response object
        """
        files = {field_name: open(file_path, "rb")}
        try:
            return await self.post(url, data=data, files=files, **kwargs)
        finally:
            for f in files.values():
                f.close()

    async def parse_response(self, response: Response) -> Dict[str, Any]:
        """
        Parse response body as JSON.
        
        Args:
            response: Response object from a request
            
        Returns:
            Parsed JSON data as dictionary
        """
        try:
            return response.json()
        except ValueError:
            # Return empty dict if response is not valid JSON
            return {} 