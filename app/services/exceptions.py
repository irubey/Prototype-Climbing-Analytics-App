import logging

logger = logging.getLogger(__name__)

class DataProcessingError(Exception):
    """Custom exception for data processing errors"""
    def __init__(self, message):
        self.message = message
        logger.error(f"DataProcessingError: {message}")
        super().__init__(self.message) 