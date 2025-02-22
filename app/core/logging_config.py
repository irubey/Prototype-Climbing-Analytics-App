"""
Separate logging configuration to avoid circular dependencies.

This module is responsible for:
- Setting up Loguru's handlers (sinks)
- Configuring the InterceptHandler for standard library logging
- Defining the core logging setup (setup_logging function)

It does NOT:
- Provide a logger instance directly (to avoid circular imports)
- Contain any application-specific logging logic
"""
import logging
import sys
from typing import Any, Dict
from pathlib import Path

from loguru import logger
from app.core.config import settings

class InterceptHandler(logging.Handler):
    """
    Intercept standard logging messages and route them to Loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record.
        """
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(log_dir: str = "logs", console_log_level: str = "INFO") -> None:
    """
    Configure Loguru logging.

    Intercepts standard logging and adds custom sinks:
    - Console output (stdout)
    - File-based logging with rotation

    Args:
        log_dir: The directory to store log files.
        console_log_level: The log level for console output.
    """

    # Remove default handler
    logger.remove()

    # Determine log level based on environment (from settings)
    console_log_level = "DEBUG" if settings.ENVIRONMENT == "testing" else "INFO"
    # Add console handler with custom format to stdout
    logger.add(
        sys.stdout,  # Use sys.stdout instead of sys.stderr
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message} | {extra}",
        level=console_log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # Create logs directory
    log_directory = Path(log_dir)
    log_directory.mkdir(exist_ok=True)

    # Common log configuration
    log_config: Dict[str, Any] = {
        "rotation": "1 day",  # Rotate logs daily
        "retention": "7 days",  # Keep logs for 7 days
        "compression": "zip",  # Compress old log files
        "backtrace": True,  # Capture stack traces for debugging
        "diagnose": True,  # Show variable values in stack traces
    }

    # Error log with all log levels and details
    logger.add(
        log_directory / "error.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message} | {extra}",
        level="DEBUG",  # Log everything to the error log
        **log_config,
    )

    # Scraping-specific log (example)
    logger.add(
        log_directory / "scraping.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message} | {extra}",
        level="DEBUG",
        filter=lambda record: "scraping" in record["extra"].get("error_type", "").lower(),
        **log_config,
    )

    # API request log (example)
    logger.add(
        log_directory / "api.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message} | {extra}",
        level="INFO",
        filter=lambda record: record["extra"].get("type") == "api_request",
        **log_config,
    )

    # Configure standard library logging interception
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Silence noisy loggers (optional, but good practice)
    for logger_name in logging.root.manager.loggerDict:
        if logger_name.startswith(("uvicorn", "gunicorn", "sqlalchemy")):
            logging.getLogger(logger_name).handlers = []
