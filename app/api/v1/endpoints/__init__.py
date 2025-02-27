"""
API v1 endpoints package.

This package contains all the API endpoints for version 1 of the application.
Endpoints are organized by resource type and functionality.
"""

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.context import router as context_router
from app.api.v1.endpoints.data import router as data_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.logbook import router as logbook_router
from app.api.v1.endpoints.payment import router as payment_router
from app.api.v1.endpoints.user import router as user_router
from app.api.v1.endpoints.view_routes import router as view_router
from app.api.v1.endpoints.visualization import router as visualization_router

__all__ = [
    "auth_router",
    "chat_router",
    "context_router",
    "data_router",
    "health_router",
    "logbook_router",
    "payment_router",
    "user_router",
    "view_router",
    "visualization_router"
]
