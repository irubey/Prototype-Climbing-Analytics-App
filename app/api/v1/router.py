"""
Main router for API v1.

This module aggregates all endpoint routers and configures their prefixes and tags.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin_router,
    auth_router,
    chat_router,
    context_router,
    data_router,
    health_router,
    logbook_router,
    payment_router,
    user_router,
    view_router,
    visualization_router
)

api_router = APIRouter()

# Include all route modules with their prefixes and tags
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(context_router, prefix="/context", tags=["context"])
api_router.include_router(data_router, prefix="/data", tags=["data"])
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(logbook_router, prefix="/logbook", tags=["logbook"])
api_router.include_router(payment_router, prefix="/payment", tags=["payment"])
api_router.include_router(user_router, prefix="/users", tags=["users"])
api_router.include_router(visualization_router, prefix="/visualization", tags=["visualization"])
api_router.include_router(view_router, tags=["views"])  # No prefix for view routes as they serve frontend pages 