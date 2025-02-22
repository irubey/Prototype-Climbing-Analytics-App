import json
import csv
from io import StringIO
from typing import Dict, Optional, Union, AsyncGenerator, Any
import logging
from datetime import datetime, UTC
from .model_client import Grok3Client
from ..context.orchestrator import ContextOrchestrator
from ..events.manager import EventManager, EventType
from app.core.config import settings

logger = logging.getLogger(__name__)

class FileValidationError(Exception):
    """Raised when file validation fails."""
    pass

class PremiumChatService:
    """Premium tier chat service with advanced features."""

    # Maximum file size (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    # Supported file types and their validation rules
    SUPPORTED_FILE_TYPES = {
        "csv": {"required_columns": ["grade"]},
        "txt": {},
        "json": {}
    }

    def __init__(
        self,
        model_client: Grok3Client,
        context_manager: ContextOrchestrator,
        event_manager: EventManager,
    ):
        """Initialize the service."""
        self.model_client = model_client
        self.context_manager = context_manager
        self.event_manager = event_manager

    def _validate_file_size(self, file: bytes, filename: str) -> None:
        """Validate file size is within limits."""
        if len(file) > self.MAX_FILE_SIZE:
            raise FileValidationError(
                f"File '{filename}' exceeds maximum size of 10MB. Please upload a smaller file."
            )

    def _validate_file_type(self, filename: str) -> str:
        """Validate file type is supported and return the type."""
        file_type = filename.split(".")[-1].lower()
        if file_type not in self.SUPPORTED_FILE_TYPES:
            supported_types = ", ".join(self.SUPPORTED_FILE_TYPES.keys())
            raise FileValidationError(
                f"Unsupported file type: '{file_type}'. Please upload one of: {supported_types}"
            )
        return file_type

    def _validate_csv_content(self, reader: csv.DictReader, filename: str) -> None:
        """Validate CSV content meets requirements."""
        missing_columns = set(self.SUPPORTED_FILE_TYPES["csv"]["required_columns"]) - set(reader.fieldnames)
        if missing_columns:
            raise FileValidationError(
                f"CSV file '{filename}' is missing required columns: {', '.join(missing_columns)}. "
                "Please ensure your CSV includes these columns and try again."
            )

    def _validate_json_content(self, data: Union[Dict, list], filename: str) -> None:
        """Validate JSON content structure."""
        if not isinstance(data, (dict, list)):
            raise FileValidationError(
                f"JSON file '{filename}' must contain either an object or array. "
                "Please check the file format and try again."
            )

    async def preprocess_file(self, file: bytes, filename: str) -> Dict:
        """Process uploaded files with enhanced validation and error handling."""
        try:
            # Validate file size first
            self._validate_file_size(file, filename)
            
            # Validate file type
            file_type = self._validate_file_type(filename)
            
            # Decode content
            try:
                content = file.decode("utf-8")
            except UnicodeDecodeError:
                raise FileValidationError(
                    f"File '{filename}' appears to be binary or corrupted. "
                    "Please ensure you're uploading a valid text file."
                )
                
            # Process based on file type with specific validation
            if file_type == "csv":
                try:
                    reader = csv.DictReader(StringIO(content))
                    self._validate_csv_content(reader, filename)
                    return {"type": "csv", "data": list(reader)}
                except csv.Error:
                    raise FileValidationError(
                        f"CSV file '{filename}' is malformed. "
                        "Please check the file format and ensure it's a valid CSV."
                    )
                    
            elif file_type == "txt":
                if not content.strip():
                    raise FileValidationError(
                        f"Text file '{filename}' is empty. "
                        "Please upload a file with content."
                    )
                return {"type": "txt", "data": content}
                
            elif file_type == "json":
                try:
                    data = json.loads(content)
                    self._validate_json_content(data, filename)
                    return {"type": "json", "data": data}
                except json.JSONDecodeError:
                    raise FileValidationError(
                        f"JSON file '{filename}' is malformed. "
                        "Please check the file format and ensure it's valid JSON."
                    )
                    
            return {"type": file_type, "data": content}
            
        except FileValidationError as e:
            logger.warning(
                f"File validation error: {str(e)}",
                extra={"error_type": "validation"}
            )
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing file {filename}: {str(e)}", exc_info=True)
            raise FileValidationError(
                f"An unexpected error occurred while processing '{filename}'. "
                "Please try again or contact support if the issue persists."
            )

    async def process(
        self,
        user_id: str,
        query: str,
        conversation_id: str,
        file: Optional[bytes] = None,
        filename: Optional[str] = None,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Process a chat request with optional file upload."""
        try:
            start_time = datetime.now(UTC)
            context = await self.context_manager.get_context(user_id, conversation_id)

            if file and filename:
                try:
                    processed_content = await self.preprocess_file(file, filename)
                    context["uploads"].append(processed_content)
                    await self.event_manager.publish(user_id, "file_upload", {"status": "success"})
                except ValueError as e:
                    await self.event_manager.publish(user_id, "file_upload", {"status": "error", "message": str(e)})
                    return "Error processing file: " + str(e)

            await self.event_manager.publish(user_id, "processing_start", {"status": "Processing request..."})

            if stream:
                return self._stream_response(user_id, query, context, start_time)
            
            response = await self.model_client.generate_response(query, context)
            processing_time = (datetime.now(UTC) - start_time).total_seconds()
            
            await self.event_manager.publish(
                user_id,
                "processing_complete",
                {"status": "success", "processing_time": processing_time}
            )
            return response

        except Exception as e:
            logger.error("Error processing request", extra={"error": str(e)})
            await self.event_manager.publish(
                user_id,
                "processing_complete",
                {"status": "error", "message": str(e)}
            )
            return "An error occurred while processing your request."

    async def _stream_response(
        self,
        user_id: str,
        query: str,
        context: Dict[str, Any],
        start_time: datetime
    ) -> AsyncGenerator[str, None]:
        """Handle streaming response."""
        try:
            response_generator = await self.model_client.generate_response(query, context, stream=True)
            async for chunk in response_generator:
                if chunk:
                    yield chunk

            processing_time = (datetime.now(UTC) - start_time).total_seconds()
            await self.event_manager.publish(
                user_id,
                "processing_complete",
                {"status": "success", "processing_time": processing_time}
            )
        except Exception as e:
            logger.error("Error in streaming response")
            yield "An error occurred while generating the response."
            await self.event_manager.publish(
                user_id,
                "processing_complete",
                {"status": "error", "message": str(e)}
            )
