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
import json
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


def setup_logging(log_dir: str = "logs", console_log_level: str = "DEBUG") -> None:
    """
    Configure Loguru logging.

    Intercepts standard logging and adds custom sinks:
    - Console output (stdout)
    - File-based logging with rotation

    Args:
        log_dir: The directory to store log files.
        console_log_level: The log level for console output.
    """

    # First, configure the root logger to suppress file change notifications
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    root_logger.propagate = False

    # Remove default handler
    logger.remove()

    # Create logs directory
    log_directory = Path(log_dir)
    log_directory.mkdir(exist_ok=True)

    # Common log configuration
    log_config: Dict[str, Any] = {
        "rotation": "1 day",
        "retention": "7 days",
        "compression": "zip",
        "backtrace": True,
        "diagnose": True,
        "serialize": True,  # Keep JSON serialization for file logs
        "catch": True,
        "enqueue": True,
        "format": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}\n{extra}",
    }

    # Add console handler with custom format to stdout
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>\n<yellow>{extra}</yellow>",
        level=console_log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
        serialize=False,  # Disable JSON serialization for console output
        catch=True,  # Catch exceptions during logging
        enqueue=True,  # Use queue for thread safety
    )

    # Context-specific log
    logger.add(
        log_directory / "context.log",
        level="DEBUG",
        filter=lambda record: (
            record["extra"].get("module") == "context" or
            "context" in record["name"].lower() or
            "context" in str(record["message"]).lower()
        ),
        **log_config
    )

    # Error log with all log levels and details
    logger.add(
        log_directory / "error.log",
        level="DEBUG",
        **log_config
    )

    # Configure standard library logging interception
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Silence noisy loggers
    for logger_name in logging.root.manager.loggerDict:
        if logger_name.startswith(("uvicorn", "gunicorn", "sqlalchemy")):
            logging.getLogger(logger_name).handlers = []
            
    # Set logging module to WARNING level to reduce internal logging noise
    logging.getLogger("logging").setLevel(logging.WARNING)
    logging.getLogger("logging").propagate = False
    
    # Disable file watching
    logging.getLogger("logging.handlers").setLevel(logging.WARNING)
    logging.getLogger("logging.handlers").propagate = False
