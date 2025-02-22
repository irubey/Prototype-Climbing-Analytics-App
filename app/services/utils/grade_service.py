"""
Grade conversion and management service.

This module provides services for:
- Grade system conversions
- Grade standardization
- Performance metrics calculation
- Grade validation and normalization
"""

from typing import Dict, List, Optional, Union, Literal, ClassVar
from enum import Enum
from functools import lru_cache

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
        GradeService._instance = self

    def _initialize_grade_mappings(self) -> None:
        """Initialize grade conversion and mapping tables."""
        self.binned_code_dict = { 
            1: ["5.0","5.0-","5.0+"], 
            2: ["5.1","5.1-","5.1+"],
            3: ["5.2","5.2-","5.2+"], 
            4: ["5.3","5.3-","5.3+"], 
            5: ["5.4","5.4-","5.4+"], 
            6: ["5.5","5.5-","5.5+"], 
            7: ["5.6","5.6-","5.6+"], 
            8: ["5.7","5.7-","5.7+"], 
            9: ["5.8","5.8-","5.8+"], 
            10: ["5.9","5.9-","5.9+"],
            11: ["5.10-","5.10a","5.10a/b"],
            12: ["5.10","5.10b","5.10c","5.10b/c"],
            13: ["5.10+","5.10c/d", "5.10d"],
            14: ["5.11-","5.11a","5.11a/b"],
            15: ["5.11","5.11b","5.11c","5.11b/c"],
            16: ["5.11+","5.11c/d", "5.11d"],
            17: ["5.12-","5.12a","5.12a/b"],
            18: ["5.12","5.12b","5.12c","5.12b/c"],
            19: ["5.12+","5.12c/d",  "5.12d"],
            20: ["5.13-","5.13a","5.13a/b"],
            21: ["5.13","5.13b","5.13c","5.13b/c"],
            22: ["5.13+", "5.13c/d", "5.13d"],
            23: ["5.14-","5.14a","5.14a/b"],
            24: ["5.14","5.14b","5.14c","5.14b/c"],
            25: [ "5.14+","5.14c/d", "5.14d"],
            26: ["5.15-","5.15a","5.15a/b"],
            27: ["5.15","5.15b","5.15c","5.15b/c"],
            28: ["5.15+","5.15c/d",  "5.15d"],
            101: ["V-easy"],
            102: ["V0","V0-","V0+","V0-1"],
            103: ["V1","V1-","V1+","V1-2"],
            104: ["V2","V2-","V2+","V2-3"],
            105: ["V3","V3-","V3+","V3-4"],
            106: ["V4","V4-","V4+","V4-5"],
            107: ["V5","V5-","V5+","V5-6"],
            108: ["V6","V6-","V6+","V6-7"],
            109: ["V7","V7-","V7+","V7-8"],
            110: ["V8","V8-","V8+","V8-9"],
            111: ["V9","V9-","V9+","V9-10"],
            112: ["V10","V10-","V10+","V10-11"],
            113: ["V11","V11-","V11+","V11-12"],
            114: ["V12","V12-","V12+","V12-13"],
            115: ["V13","V13-","V13+","V13-14"],
            116: ["V14","V14-","V14+","V14-15"],
            117: ["V15","V15-","V15+","V15-16"],
            118: ["V16","V16-","V16+"],
            119: ["V17","V17-","V17+"],
            120: ["V18"]
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
            "4": "5.5", "4+": "5.6",
            "5a": "5.7", "5b": "5.8", "5c": "5.9",
            "6a": "5.10a", "6a+": "5.10b",
            "6b": "5.10c", "6b+": "5.10d",
            "6c": "5.11a", "6c+": "5.11c",
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

    @lru_cache(maxsize=1024)
    async def _convert_single_grade_to_code(
        self, 
        grade: str,
        discipline: Optional[ClimbingDiscipline] = None
    ) -> int:
        """Convert a single grade to its numeric code.
        
        Returns 0 for invalid or unrecognized grades."""
        try:
            for code, grade_list in self.binned_code_dict.items():
                if grade in grade_list:
                    return code
            logger.warning(f"Unrecognized grade format: {grade}, defaulting to 0")
            return 0
        except Exception as e:
            logger.error(f"Error converting grade to code: {e}")
            return 0

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
                
                # Convert batch using list comprehension - faster than gather for CPU-bound tasks
                batch_codes = [
                    await self._convert_single_grade_to_code(grade, discipline) 
                    for grade in batch
                ]
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
        if discipline in [ClimbingDiscipline.BOULDER, ClimbingDiscipline.MIXED_BOULDER]:
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

    @staticmethod
    def get_instance() -> 'GradeService':
        """Get the singleton instance of GradeService.
        
        Returns:
            The singleton GradeService instance
            
        Creates the instance if it doesn't exist.
        """
        if GradeService._instance is None:
            GradeService()
        return GradeService._instance 