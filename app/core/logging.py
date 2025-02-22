"""
Centralized logging module for the application.

Provides a pre-configured Loguru logger instance for use throughout
the application.  This module avoids circular dependencies by:

- Importing the logging *configuration* from logging_config.py
- Providing the logger *instance* here.

This ensures that other modules can import the logger without
triggering the import of models or other components that might
cause circular dependencies.
"""

from loguru import logger
from app.core.logging_config import setup_logging

# Initialize logging (call the setup function)
setup_logging()

# The 'logger' object is now ready for use.  Other modules can import it:
# from app.core.logging import logger

# Example of adding application-specific logging functions (optional):
# def log_request(request_id: str, message: str):
#     logger.bind(request_id=request_id).info(message) 