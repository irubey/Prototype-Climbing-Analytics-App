from typing import Dict, Any
from datetime import datetime
import platform
import logging

logger = logging.getLogger(__name__)

class ContextEnhancer:
    def enhance_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance the context with additional information."""
        try:
            logger.info("Starting context enhancement", module="context")
            enhanced_context = context.copy()
            
            # Add timestamp
            enhanced_context["timestamp"] = datetime.utcnow().isoformat()
            logger.debug("Added timestamp to context", module="context")
            
            # Add system information
            enhanced_context["system_info"] = {
                "platform": platform.system(),
                "python_version": platform.python_version(),
                "hostname": platform.node()
            }
            logger.debug("Added system information to context", module="context")
            
            # Add request information if available
            if "request" in context:
                request = context["request"]
                enhanced_context["request_info"] = {
                    "method": request.method,
                    "path": request.path,
                    "remote_addr": request.remote_addr,
                    "user_agent": request.user_agent.string
                }
                logger.debug("Added request information to context", module="context")
            
            logger.info("Context enhancement completed", module="context")
            return enhanced_context
            
        except Exception as e:
            logger.error(f"Error enhancing context: {str(e)}", module="context")
            return context 