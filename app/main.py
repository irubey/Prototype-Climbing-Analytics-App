# At startup (e.g., in run_fastapi.py or main.py)
import sys
from loguru import logger

# for name, mod in sys.modules.items():  # Remove this debugging code
#     if name.startswith("app.models"):
#         logger.debug(f"Loaded module: {name}; id: {id(mod)}; file: {getattr(mod, '__file__', None)}")

# logger.debug("DEBUG level test: this message should appear if DEBUG is enabled")

"""
Main FastAPI application module.

This module initializes the FastAPI application with all its middleware,
routers, and lifecycle management.
"""

import os  # Import the os module
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError
import stripe

from app.api.v1.router import api_router
from app.core.config import (
    settings,)
from app.core.exceptions import (
    SendSageException,
    ValidationError,
)
from app.core.error_handlers import (
    send_sage_exception_handler,
    sqlalchemy_error_handler,
    stripe_error_handler,
    validation_error_handler,
    general_exception_handler,
    )
from app.core.logging import logger
from app.db.init_db import init_db, dispose_db
from app.db.session import DatabaseSessionManager, sessionmanager # Import sessionmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.

    Handles database initialization on startup and cleanup on shutdown.
    """
    try:
        # Startup
        logger.info("Initializing application...")
        
        # Apply Redis patches for development/testing environments
        if settings.ENVIRONMENT.lower() in ("development", "testing"):
            from app.core.redis_patch import apply_redis_patches
            apply_redis_patches()
            logger.info(f"Applied Redis mocking patches for {settings.ENVIRONMENT} environment")
        
        # Use the global sessionmanager instance
        db_manager = sessionmanager
        db_manager.init(
            settings.DATABASE_URL,
            engine_kwargs={
                "echo": False,
                "pool_pre_ping": True
            }
        )
        app.state.db_manager = db_manager

        # Conditionally initialize the database based on an environment variable
        # DO NOT set SKIP_DB_INIT=True in your .env file or system environment.
        # It is set temporarily by run.py during reloads.
        if os.environ.get("SKIP_DB_INIT") != "True":
            await init_db()
            logger.info("Application initialized successfully")
        else:
            logger.info("Skipping database initialization on reload")

        yield  # Application runtime

    except Exception as e:
        logger.error(
            "Error during application startup",
            extra={
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise
    finally:
        # Shutdown
        logger.info("Shutting down application...")
        await dispose_db()
        logger.info("Application shutdown complete")

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    # --- FastAPI App Creation ---
    logger.info("Creating FastAPI application...")
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Send Sage API - FastAPI Implementation",
        version=settings.VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan  # Use lifespan here
    )

    # Register exception handlers
    app.add_exception_handler(SendSageException, send_sage_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    app.add_exception_handler(stripe.StripeError, stripe_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Security middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS or ["*"]
    )

    # Set up CORS
    if settings.BACKEND_CORS_ORIGINS:
        # Print CORS origins for debugging
        origin_list = [str(origin).rstrip('/') for origin in settings.BACKEND_CORS_ORIGINS]
        print(f"Configuring CORS with the following origins: {origin_list}")
        logger.info(f"CORS configuration applied with origins: {origin_list}")
        
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Static files and templates configuration
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    templates = Jinja2Templates(directory="app/templates")

    # Register API routes
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app

app = create_app()  # Create the app *after* the explicit import

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log all HTTP requests and responses with relevant context.
    """
    logger.info(
        "Incoming request",
        extra={
            "method": request.method,
            "url": str(request.url),
            "client_host": request.client.host if request.client else None,
            "headers": dict(request.headers)
        }
    )
    
    response = await call_next(request)
    
    logger.info(
        "Outgoing response",
        extra={
            "status_code": response.status_code,
            "method": request.method,
            "url": str(request.url)
        }
    )
    
    return response 