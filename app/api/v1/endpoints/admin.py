"""
Admin endpoints for Send Sage application.

This module provides admin-only endpoints for:
- Testing admin access
- System administration
- User management
"""

from fastapi import APIRouter, Depends, Security
from app.core.auth import get_current_admin
from app.models.user import User

admin_router = APIRouter()

@admin_router.get("/test")
async def test_admin_access(
    current_user: User = Security(get_current_admin, scopes=["admin"])
) -> dict:
    """Test endpoint for admin access."""
    return {
        "message": "Admin access successful",
        "user_id": str(current_user.id)
    } 