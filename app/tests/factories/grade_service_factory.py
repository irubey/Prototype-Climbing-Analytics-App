"""
Factory for creating GradeService instances for testing.

This module provides a factory class for creating GradeService instances
configured for testing purposes with different mocking options.
"""

from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, Optional, Any
import asyncio
from functools import wraps

from app.services.utils.grade_service import GradeService, GradingSystem
from app.models.enums import ClimbingDiscipline


class GradeServiceFactory:
    """Factory for creating pre-configured GradeService instances for testing."""

    @classmethod
    def create_service(
        cls,
        mock_cache: bool = True,
        grade_conversion_map: Optional[Dict[str, Dict[str, str]]] = None,
        conversion_delay: float = 0.0
    ) -> GradeService:
        """
        Create a GradeService instance with configurable mocks for testing.

        Args:
            mock_cache: Whether to mock the LRU cache functionality.
            grade_conversion_map: Custom grade conversion mappings to use.
            conversion_delay: Artificial delay for conversion operations (for testing cache performance).

        Returns:
            A configured GradeService instance with mocks assigned to _test_mocks attribute.
        """
        # Create test mocks
        mocks = {}

        # Create a fresh instance
        with patch('app.services.utils.grade_service.GradeService._instance', None):
            service = GradeService.get_instance()

        # Store the original methods for restoration
        original_convert_grade = service.convert_grade_system
        original_convert_to_code = service._convert_single_grade_to_code

        # Add a simple conversion map to the service for testing
        if grade_conversion_map:
            mocks["grade_conversion_map"] = grade_conversion_map
        else:
            # Default simple conversion map for testing
            mocks["grade_conversion_map"] = {
                "yds": {"code_1": "5.9", "code_2": "5.10a", "code_3": "5.10b", "code_4": "5.10c"},
                "french": {"code_1": "6a", "code_2": "6a+", "code_3": "6b", "code_4": "6b+"},
                "v_scale": {"code_1": "V0", "code_2": "V1", "code_3": "V2", "code_4": "V3"}
            }

        # Mock caching if requested
        if mock_cache:
            # Create an async method that replaces the original
            async def mock_convert_grade_system(grade, source_system, target_system):
                """Mock implementation of convert_grade_system."""
                conversion_map = mocks["grade_conversion_map"]
                source_grades = conversion_map.get(source_system.value, {})
                target_grades = conversion_map.get(target_system.value, {})
                
                # Introduce artificial delay if specified
                if conversion_delay > 0:
                    await asyncio.sleep(conversion_delay)
                    
                # Simple conversion - find the code and map to target
                source_code = None
                for code, value in source_grades.items():
                    if value == grade:
                        source_code = code
                        break
                
                if source_code and source_code in target_grades:
                    return target_grades[source_code]
                return None
            
            # Create async method for grade to code conversion
            async def mock_convert_to_code(grade, discipline):
                """Mock implementation of _convert_single_grade_to_code."""
                # Introduce artificial delay if specified
                if conversion_delay > 0:
                    await asyncio.sleep(conversion_delay)
                
                # Simple mapping for testing
                grade_to_code = {
                    "5.9": 10, "5.10a": 11, "5.10b": 12, "5.10c": 13,
                    "V0": 100, "V1": 101, "V2": 102, "V3": 103
                }
                return grade_to_code.get(grade, 0)
            
            # Replace with our mock versions
            service.convert_grade_system = mock_convert_grade_system
            service._convert_single_grade_to_code = mock_convert_to_code
            
            # Store the originals for restore if needed
            mocks["original_convert_grade"] = original_convert_grade
            mocks["original_convert_to_code"] = original_convert_to_code

        # Attach the mocks to the service for test assertions
        service._test_mocks = mocks
        
        return service 