"""
Grade conversion and management service.

This module provides services for:
- Grade system conversions
- Grade standardization
- Performance metrics calculation
- Grade validation and normalization
"""

from typing import Dict, List, Optional, Union, Literal, ClassVar, Tuple, Any, Callable
from enum import Enum
from functools import lru_cache, wraps
import asyncio
from collections import OrderedDict

from app.core.logging import logger
from app.models.enums import (
    ClimbingDiscipline
)
from app.schemas.visualization import PerformancePyramidData

class GradingSystem(str, Enum):
    """Supported climbing grade systems."""
    YDS = "yds"  # Yosemite Decimal System
    FRENCH = "french"  # French Sport
    V_SCALE = "v_scale"  # Hueco/V Scale
    FONT = "font"  # Fontainebleau

    @property
    def display_name(self) -> str:
        """Get human-readable name of grading system."""
        return {
            self.YDS: "Yosemite Decimal System",
            self.FRENCH: "French Sport",
            self.V_SCALE: "Hueco/V Scale",
            self.FONT: "Fontainebleau"
        }[self]

# Custom async cache decorator to replace lru_cache for async functions
def async_lru_cache(maxsize: int = 128):
    """Simple LRU cache for async functions.
    
    This decorator caches the results of async function calls based on the
    arguments passed. It maintains a simple LRU cache with the specified maximum size.
    
    Args:
        maxsize: Maximum number of entries to keep in the cache
    
    Returns:
        A decorator function that wraps the original async function
    """
    
    def decorator(func):
        cache = {}  # {key: result}
        keys_order = []  # LRU tracking - oldest first
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate a cache key by stringifying all arguments
            # For the first argument, check if it's a class instance and use class name
            arg_list = list(args)
            if args and hasattr(args[0], '__class__') and not isinstance(args[0], (str, int, float, bool, bytes)):
                arg_list[0] = args[0].__class__.__name__
                
            # Create a hashable key from all arguments
            key = str((tuple(str(a) for a in arg_list), 
                      tuple(sorted((k, str(v)) for k, v in kwargs.items()))))
            
            # Check if result is in cache
            if key in cache:
                # Move key to the end of keys_order (most recently used)
                keys_order.remove(key)
                keys_order.append(key)
                return cache[key]
            
            # Not in cache, call the original function
            result = await func(*args, **kwargs)
            
            # Add result to cache
            cache[key] = result
            keys_order.append(key)
            
            # If cache exceeds maxsize, remove the oldest entry
            if len(cache) > maxsize:
                oldest_key = keys_order.pop(0)
                del cache[oldest_key]
                
            return result
            
        # Add a method to clear the cache
        async def cache_clear():
            """Clear the function's cache."""
            nonlocal cache, keys_order
            cache.clear()
            keys_order.clear()
            
        # Make cache_clear available both as async and non-async
        def sync_cache_clear():
            cache.clear()
            keys_order.clear()
            
        wrapper.cache_clear = sync_cache_clear
        wrapper.async_cache_clear = cache_clear
        
        return wrapper
    
    return decorator

class GradeService:
    """Service for handling all grade-related processing and conversions.
    
    This service provides methods for:
    - Converting between different grading systems
    - Standardizing grades for comparison
    - Generating grade pyramids
    - Validating grade inputs
    
    The service is implemented as a singleton to ensure consistent grade handling
    across the application.
    """
    
    _instance: ClassVar[Optional['GradeService']] = None
    
    def __init__(self) -> None:
        if GradeService._instance is not None:
            raise RuntimeError("GradeService is a singleton - use get_instance()")
            
        self._initialize_grade_mappings()
        # Initialize cache for grade conversion
        self._grade_code_cache = OrderedDict()
        self._cache_size = 1024
        GradeService._instance = self

    def _initialize_grade_mappings(self) -> None:
        """Initialize grade conversion and mapping tables."""
        self.binned_code_dict = { 
            1: ["5.0","5.0-","5.0+", "3"], 
            2: ["5.1","5.1-","5.1+", "3+"],
            3: ["5.2","5.2-","5.2+", "4a"], 
            4: ["5.3","5.3-","5.3+", "4b"], 
            5: ["5.4","5.4-","5.4+", "4c"], 
            6: ["5.5","5.5-","5.5+", "5a"], 
            7: ["5.6","5.6-","5.6+", "5a+"], 
            8: ["5.7","5.7-","5.7+", "5b"], 
            9: ["5.8","5.8-","5.8+", "5c"], 
            10: ["5.9","5.9-","5.9+", "5c+"],
            11: ["5.10-","5.10a","5.10a/b", "6a"],
            12: ["5.10","5.10b","5.10c","5.10b/c", "6a+"],
            13: ["5.10+","5.10c/d", "5.10d", "6b"],
            14: ["5.11-","5.11a","5.11a/b", "6b+"],
            15: ["5.11","5.11b","5.11c","5.11b/c", "6c"],
            16: ["5.11+","5.11c/d", "5.11d", "6c+"],
            17: ["5.12-","5.12a","5.12a/b", "7a"],
            18: ["5.12","5.12b","5.12c","5.12b/c", "7a+"],
            19: ["5.12+","5.12c/d",  "5.12d", "7b"],
            20: ["5.13-","5.13a","5.13a/b", "7b+"],
            21: ["5.13","5.13b","5.13c","5.13b/c", "7c"],
            22: ["5.13+", "5.13c/d", "5.13d", "7c+"],
            23: ["5.14-","5.14a","5.14a/b", "8a"],
            24: ["5.14","5.14b","5.14c","5.14b/c", "8a+"],
            25: [ "5.14+","5.14c/d", "5.14d", "8b"],
            26: ["5.15-","5.15a","5.15a/b", "8b+"],
            27: ["5.15","5.15b","5.15c","5.15b/c", "8c"],
            28: ["5.15+","5.15c/d",  "5.15d", "9a"],
            101: ["V-easy"],
            102: ["V0","V0-","V0+","V0-1", "f3", "Font 3"],
            103: ["V1","V1-","V1+","V1-2", "f4", "Font 4"],
            104: ["V2","V2-","V2+","V2-3", "f5", "Font 5"],
            105: ["V3","V3-","V3+","V3-4", "f6A", "f6A+"],
            106: ["V4","V4-","V4+","V4-5", "f6B", "f6B+"],
            107: ["V5","V5-","V5+","V5-6", "V6", "V6-", "f6C", "f6C+"],
            108: ["V6+","V6-7", "f7A"],
            109: ["V7","V7-","V7+","V7-8", "f7A+"],
            110: ["V8","V8-","V8+","V8-9", "f7B"],
            111: ["V9","V9-","V9+","V9-10", "f7B+"],
            112: ["V10","V10-","V10+","V10-11", "f7C"],
            113: ["V11","V11-","V11+","V11-12", "f7C+"],
            114: ["V12","V12-","V12+","V12-13", "f8A"],
            115: ["V13","V13-","V13+","V13-14", "f8A+"],
            116: ["V14","V14-","V14+","V14-15", "f8B"],
            117: ["V15","V15-","V15+","V15-16", "f8B+"],
            118: ["V16","V16-","V16+", "f8C"],
            119: ["V17","V17-","V17+", "f8C+"],
            120: ["V18", "f9A"]
        }
        
        self.routes_grade_list = [
            "5.0-","5.0","5.0+","5.1-","5.1","5.1+",
            "5.2-","5.2","5.2+","5.3-","5.3","5.3+",
            "5.4-","5.4","5.4+","5.5-","5.5","5.5+",
            "5.6-","5.6","5.6+","5.7-","5.7","5.7+",
            "5.8-","5.8","5.8+","5.9-","5.9","5.9+",
            "5.10a","5.10-","5.10a/b","5.10b","5.10", 
            "5.10b/c", "5.10c","5.10c/d","5.10+", "5.10d",
            "5.11a","5.11-","5.11a/b","5.11b","5.11", 
            "5.11b/c", "5.11c","5.11c/d","5.11+", "5.11d",
            "5.12a","5.12-","5.12a/b","5.12b","5.12", 
            "5.12b/c", "5.12c","5.12c/d","5.12+", "5.12d",
            "5.13a","5.13-","5.13a/b","5.13b","5.13", 
            "5.13b/c", "5.13c","5.13c/d","5.13+", "5.13d",
            "5.14a","5.14-","5.14a/b","5.14b","5.14", 
            "5.14b/c", "5.14c","5.14c/d","5.14+", "5.14d",
            "5.15a","5.15-","5.15a/b","5.15b","5.15", 
            "5.15b/c", "5.15c","5.15c/d","5.15+", "5.15d"
        ]
        
        self.boulders_grade_list = [
            "V-easy", 
            "V0-","V0","V0+","V0-1",
            "V1-","V1","V1+","V1-2",
            "V2-","V2","V2+","V2-3",
            "V3-","V3","V3+","V3-4",
            "V4-","V4","V4+","V4-5",
            "V5-","V5","V5+","V5-6",
            "V6-","V6","V6+","V6-7",
            "V7-","V7","V7+","V7-8",
            "V8-","V8","V8+","V8-9",
            "V9-","V9","V9+","V9-10",
            "V10-","V10","V10+","V10-11",
            "V11-","V11","V11+","V11-12",
            "V12-","V12","V12+","V12-13",
            "V13-","V13","V13+","V13-14",
            "V14-","V14","V14+","V14-15",
            "V15-","V15","V15+","V15-16",
            "V16-","V16","V16+",
            "V17-","V17","V17+",
        ]

        # French to YDS conversion mapping
        self.french_to_yds = {
            "3": "5.4", "3+": "5.5",
            "4a": "5.2", "4b": "5.3", "4c": "5.4",
            "5a": "5.5", "5a+": "5.6", "5b": "5.7", "5c": "5.8", "5c+": "5.9",
            "6a": "5.10a", "6a+": "5.10b",
            "6b": "5.10c", "6b+": "5.10d",
            "6c": "5.11b", "6c+": "5.11c",
            "7a": "5.11d", "7a+": "5.12a",
            "7b": "5.12b", "7b+": "5.12c",
            "7c": "5.12d", "7c+": "5.13a",
            "8a": "5.13b", "8a+": "5.13c",
            "8b": "5.13d", "8b+": "5.14a",
            "8c": "5.14b", "8c+": "5.14c",
            "9a": "5.14d", "9a+": "5.15a",
            "9b": "5.15b", "9b+": "5.15c",
            "9c": "5.15d"
        }
        
        # Font to V-scale conversion mapping
        self.font_to_v = {
            "3": "V0-", "4": "V0",
            "4+": "V0+", "5": "V1",
            "5+": "V2", "6A": "V3",
            "6A+": "V3+", "6B": "V4",
            "6B+": "V4+", "6C": "V5",
            "6C+": "V5+", "7A": "V6",
            "7A+": "V7", "7B": "V8",
            "7B+": "V8+", "7C": "V9",
            "7C+": "V10", "8A": "V11",
            "8A+": "V12", "8B": "V13",
            "8B+": "V14", "8C": "V15",
            "8C+": "V16", "9A": "V17"
        }

    @async_lru_cache(maxsize=1024)
    async def _convert_single_grade_to_code(
        self, 
        grade: str,
        discipline: Optional[ClimbingDiscipline] = None
    ) -> int:
        """Convert a single grade to its numeric code.
        
        Returns 0 for invalid or unrecognized grades."""
        try:
            if not grade:
                return 0
                
            # Clean up the grade by removing qualifiers and other non-grade information
            cleaned_grade = self._clean_grade_format(grade)
            
            # If not in cache, perform conversion
            result = 0
            for code, grade_list in self.binned_code_dict.items():
                if cleaned_grade in grade_list:
                    result = code
                    break
            
            if result == 0:
                logger.warning(f"Unrecognized grade format: {grade}, defaulting to 0")
            
            return result
        except Exception as e:
            logger.error(f"Error converting grade to code: {e}")
            return 0
            
    def _clean_grade_format(self, grade: str) -> str:
        """Clean grade string by removing qualifiers and non-grade information.
        
        This handles mixed formats like '5.10b/c R', '5.9 PG13', 'V1 PG13', etc.
        """
        if not grade:
            return ""
            
        try:
            # Extract just the core grade information
            if grade.startswith('5.'):
                # YDS grade format (5.xx)
                parts = grade.split()
                core_grade = parts[0]
                # Handle cases like "5.10b/c"
                if '/' in core_grade and len(core_grade) <= 8:
                    return core_grade
                # Remove any suffixes with non-grade characters
                for suffix in ['R', 'X', 'PG13', 'PG', 'C0', 'C1', 'C2', 'A0', 'A1', 'A2']:
                    if suffix in core_grade:
                        core_grade = core_grade.replace(suffix, '').strip()
                return core_grade
                
            elif grade.startswith('V') and not grade.startswith('Very'):
                # V-scale format (Vx)
                parts = grade.split()
                core_grade = parts[0]
                # Handle ranges like V2-3
                if '-' in core_grade and len(core_grade) <= 5:
                    return core_grade
                # Remove any qualifiers
                for suffix in ['R', 'X', 'PG13', 'PG']:
                    if suffix in core_grade:
                        core_grade = core_grade.replace(suffix, '').strip()
                return core_grade
                
            elif grade.startswith('f') and len(grade) >= 2:
                # Font boulder grade format (f6A, f7C+, etc)
                import re
                match = re.match(r'^f(\d+[A-C]\+?)', grade)
                if match:
                    return "f" + match.group(1)
                return grade
                
            elif any(grade.startswith(prefix) for prefix in ['3', '4', '5', '6', '7', '8', '9']):
                # Might be French/European grade format (4a, 5c+, 6a, 7c, etc.)
                import re
                
                # Match standard form like "5c+" or "6a"
                match = re.match(r'^(\d+[a-c]\+?)', grade)
                if match:
                    return match.group(1)
                    
                # Match variations like "5.c+" or "6.a"
                match = re.match(r'^(\d+)\.([a-c])(\+?)', grade)
                if match:
                    return match.group(1) + match.group(2) + match.group(3)
                    
                # Match Font boulder grades like "7A+" or "6C"
                match = re.match(r'^(\d+[A-C]\+?)', grade)
                if match:
                    return "f" + match.group(1)  # Add 'f' prefix for Font system
                    
                # Handle "Easy 5th" and similar descriptions
                if "Easy" in grade and "5th" in grade:
                    return "5.0"  # Map to YDS equivalent
                    
            # If we can't recognize a specific format, return as is
            return grade
            
        except Exception as e:
            logger.warning(f"Error cleaning grade format '{grade}': {e}")
            return grade

    async def convert_grades_to_codes(
        self, 
        grades: List[str], 
        discipline: Optional[ClimbingDiscipline] = None
    ) -> List[int]:
        """Convert a list of grades to their numeric codes for comparison.
        
        Args:
            grades: List of grades to convert
            discipline: Optional climbing discipline for context
            
        Returns:
            List of numeric grade codes (0 for invalid grades)
        """
        BATCH_SIZE = 100  # Optimal batch size for grade conversion
        codes = []
        
        try:
            # Process in batches to avoid memory spikes
            for i in range(0, len(grades), BATCH_SIZE):
                batch = grades[i:i + BATCH_SIZE]
                
                # Process batch individually to avoid coroutine reuse issues
                batch_codes = []
                for grade in batch:
                    code = await self._convert_single_grade_to_code(grade, discipline)
                    batch_codes.append(code)
                
                codes.extend(batch_codes)
                
                logger.debug(
                    "Processed grade batch", 
                    extra={
                        "batch_size": len(batch),
                        "total_processed": len(codes),
                        "total_grades": len(grades)
                    }
                )
            
            return codes
            
        except Exception as e:
            logger.error(
                "Error in batch grade conversion", 
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "batch_size": BATCH_SIZE,
                    "total_grades": len(grades)
                }
            )
            # Return zeros for all grades on error
            return [0] * len(grades)

    @lru_cache(maxsize=1024)
    def get_grade_from_code(self, code: int) -> str:
        """Get the canonical grade string for a numeric code.
        
        Args:
            code: The numeric grade code
            
        Returns:
            The canonical grade string for valid codes, or 'Invalid Grade' for code 0
        """
        if code == 0:
            return "Invalid Grade"
        try:
            return self.binned_code_dict[code][0]
        except KeyError:
            raise ValueError(f"Invalid grade code: {code}")

    def get_grade_sorting_list(self, discipline: ClimbingDiscipline) -> List[str]:
        """Get the ordered list of grades for a discipline.
        
        Args:
            discipline: The climbing discipline
            
        Returns:
            Ordered list of grades from easiest to hardest
        """
        if discipline == ClimbingDiscipline.BOULDER:
            return self.boulders_grade_list
        return self.routes_grade_list

    async def convert_grade_system(
        self,
        grade: str,
        from_system: GradingSystem,
        to_system: GradingSystem
    ) -> Optional[str]:
        """Convert a grade from one system to another
        
        Args:
            grade: Grade to convert
            from_system: Source grading system
            to_system: Target grading system
            
        Returns:
            Converted grade or None if conversion not possible
        """
        try:
            grade = grade.strip()
            
            # Handle sport climbing grade conversions
            if from_system == GradingSystem.FRENCH and to_system == GradingSystem.YDS:
                return self.french_to_yds.get(grade)
                
            elif from_system == GradingSystem.YDS and to_system == GradingSystem.FRENCH:
                return next(
                    (french for french, yds in self.french_to_yds.items() 
                     if yds == grade),
                    None
                )
                
            # Handle bouldering grade conversions    
            elif from_system == GradingSystem.FONT and to_system == GradingSystem.V_SCALE:
                return self.font_to_v.get(grade)
                
            elif from_system == GradingSystem.V_SCALE and to_system == GradingSystem.FONT:
                return next(
                    (font for font, v in self.font_to_v.items() 
                     if v == grade),
                    None
                )
                
            return None
            
        except Exception as e:
            logger.error(
                "Error converting grade system", 
                extra={
                    "error": str(e),
                    "from_system": from_system,
                    "to_system": to_system,
                    "grade": grade
                }
            )
            return None

    async def convert_grades_batch(
        self,
        grades: List[str],
        from_system: GradingSystem,
        to_system: GradingSystem
    ) -> List[Optional[str]]:
        """Convert a batch of grades between grading systems.
        
        Args:
            grades: List of grades to convert
            from_system: Source grading system
            to_system: Target grading system
            
        Returns:
            List of converted grades (None for failed conversions)
        """
        BATCH_SIZE = 100
        converted_grades = []
        
        try:
            for i in range(0, len(grades), BATCH_SIZE):
                batch = grades[i:i + BATCH_SIZE]
                
                # Process batch using list comprehension
                batch_converted = [
                    await self.convert_grade_system(grade, from_system, to_system)
                    for grade in batch
                ]
                converted_grades.extend(batch_converted)
                
                logger.debug(
                    "Processed grade system conversion batch",
                    extra={
                        "batch_size": len(batch),
                        "total_processed": len(converted_grades),
                        "total_grades": len(grades),
                        "from_system": from_system,
                        "to_system": to_system
                    }
                )
            
            return converted_grades
            
        except Exception as e:
            logger.error(
                "Error in batch grade system conversion",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "batch_size": BATCH_SIZE,
                    "total_grades": len(grades),
                    "from_system": from_system,
                    "to_system": to_system
                }
            )
            return [None] * len(grades)

    async def convert_to_code(
        self,
        grade: str,
        system: GradingSystem,
        discipline: Optional[ClimbingDiscipline] = None
    ) -> int:
        """Convert a grade from any supported system to numeric code
        
        Args:
            grade: Grade to convert
            system: Source grading system
            discipline: Optional discipline to ensure correct code range
            
        Returns:
            Numeric grade code
        """
        # Convert to YDS/V-scale first if needed
        if system == GradingSystem.FRENCH:
            yds_grade = await self.convert_grade_system(
                grade, 
                GradingSystem.FRENCH, 
                GradingSystem.YDS
            )
            if yds_grade:
                return (await self.convert_grades_to_codes([yds_grade], discipline))[0]
                
        elif system == GradingSystem.FONT:
            v_grade = await self.convert_grade_system(
                grade,
                GradingSystem.FONT,
                GradingSystem.V_SCALE
            )
            if v_grade:
                return (await self.convert_grades_to_codes([v_grade], discipline))[0]
                
        # Direct conversion for YDS/V-scale
        return (await self.convert_grades_to_codes([grade], discipline))[0]

    async def get_equivalent_grades(
        self,
        grade: str,
        system: GradingSystem
    ) -> Dict[str, str]:
        """Get grade equivalents in all supported systems
        
        Args:
            grade: Grade to convert
            system: Source grading system
            
        Returns:
            Dictionary of equivalent grades in all systems
        """
        result = {system.value: grade}
        
        if system in [GradingSystem.YDS, GradingSystem.FRENCH]:
            if system == GradingSystem.YDS:
                french = await self.convert_grade_system(grade, GradingSystem.YDS, GradingSystem.FRENCH)
                result[GradingSystem.FRENCH.value] = french or "N/A"
            else:
                yds = await self.convert_grade_system(grade, GradingSystem.FRENCH, GradingSystem.YDS)
                result[GradingSystem.YDS.value] = yds or "N/A"
                
        elif system in [GradingSystem.V_SCALE, GradingSystem.FONT]:
            if system == GradingSystem.V_SCALE:
                font = await self.convert_grade_system(grade, GradingSystem.V_SCALE, GradingSystem.FONT)
                result[GradingSystem.FONT.value] = font or "N/A"
            else:
                v_scale = await self.convert_grade_system(grade, GradingSystem.FONT, GradingSystem.V_SCALE)
                result[GradingSystem.V_SCALE.value] = v_scale or "N/A"
                
        return result

    @classmethod
    def get_instance(cls) -> 'GradeService':
        """Get the singleton instance of GradeService."""
        if cls._instance is None:
            cls._instance = GradeService()
        return cls._instance
        
    def clear_cache(self):
        """Clear all caches used by the service."""
        self._grade_code_cache.clear()
        # Clear the lru_cache for the get_grade_from_code method
        self.get_grade_from_code.cache_clear()
        # Clear the async_lru_cache for _convert_single_grade_to_code if available
        if hasattr(self._convert_single_grade_to_code, 'cache_clear'):
            self._convert_single_grade_to_code.cache_clear()  # Non-awaited version 