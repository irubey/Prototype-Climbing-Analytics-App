"""Endpoints for rendering templates."""
from typing import Any
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    get_current_active_user,
)
from app.core.logging import logger
from app.db.session import get_db
from app.models import User
from app.services.dashboard.dashboard_analytics import (
    get_dashboard_base_metrics,
    get_dashboard_performance_metrics
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> Any:
    """Render the index/landing page."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

@router.get("/logbook-connection", response_class=HTMLResponse)
async def logbook_connection(request: Request) -> Any:
    """Render the logbook connection page."""
    return templates.TemplateResponse(
        "logbook_connection.html",
        {"request": request}
    )

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Render the dashboard/visualization page.
    Requires authentication and mountain project connection.
    """
    if not current_user.mountain_project_url:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/logbook-connection"}
        )
    
    try:
        base_metrics = await get_dashboard_base_metrics(db, current_user.id)
        performance_metrics = await get_dashboard_performance_metrics(
            db,
            current_user.id
        )
        
        return templates.TemplateResponse(
            "viz/dashboard.html",
            {
                "request": request,
                "user_id": current_user.id,
                "username": current_user.username,
                "base_metrics": base_metrics,
                "performance_metrics": performance_metrics
            }
        )
    except Exception as e:
        logger.error(
            "Error fetching visualization data",
            extra={
                "error": str(e),
                "user_id": str(current_user.id),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/"}
        )

@router.get("/terms-privacy", response_class=HTMLResponse)
async def terms_and_privacy(request: Request) -> Any:
    """Render the terms and privacy page."""
    return templates.TemplateResponse(
        "termsAndPrivacy.html",
        {"request": request}
    )