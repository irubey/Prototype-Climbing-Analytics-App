"""
8a.nu data processor.

This module provides functionality for:
- Processing 8a.nu JSON data
- Converting to standardized format
- Classifying climbing data
- Calculating performance metrics
"""

# Standard library imports
from uuid import UUID
import traceback
import numpy as np
import asyncio

# Third-party imports
import pandas as pd

# Application imports
from app.core.exceptions import DataSourceError
from app.core.logging import logger
from app.models.enums import (
    LogbookType,
    ClimbingDiscipline,
    GradingSystem,
    CruxAngle,
    CruxEnergyType
)
from app.services.logbook.processing.base_csv_processor import BaseCSVProcessor
from app.services.utils.grade_service import GradeService

class EightANuProcessor(BaseCSVProcessor):
    """Processor for 8a.nu JSON data to convert it to standardized format"""
    
    def __init__(self, user_id: UUID):
        super().__init__(user_id)
        logger.info("Initializing 8a.nu processor", extra={
            "user_id": str(user_id)
        })
        self.grade_service = GradeService.get_instance()
        
    async def process_raw_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process raw 8a.nu JSON data into standardized format matching Mountain Project"""
        try:
            logger.info("Starting 8a.nu data processing", extra={
                "user_id": str(self.user_id),
                "row_count": len(df),
                "columns": df.columns.tolist()
            })
            
            # Validate DataFrame is not empty
            if df.empty or len(df.columns) == 0:
                raise DataSourceError("No data found in 8a.nu response")
            
            # Add logbook type
            df['logbook_type'] = LogbookType.EIGHT_A_NU
            
            # Process locations
            logger.debug("Processing locations")
            df['location'] = df.apply(
                lambda x: f"{x['cragName']}, {x['areaName']}" if pd.notna(x['areaName']) else x['cragName'],
                axis=1
            )
            df['location_raw'] = None
            
            # Process route quality (convert rating 1-5 scale to 0-1 scale)
            logger.debug("Processing route quality")
            df['route_quality'] = df['rating'].apply(
                lambda x: float(x) / 5.0 if pd.notna(x) else None
            )
            df['user_quality'] = df['route_quality']  # 8a.nu only has one rating
            
            # Process route name and grade
            df['route_name'] = df['zlaggableName']
            
            # Keep original grades for all climbs
            df['route_grade'] = df['difficulty']
            df['user_grade'] = df['route_grade']  # 8a.nu doesn't separate user and route grades
            
            # Process disciplines first
            df = self._classify_disciplines(df)
            
            # Convert grades based on discipline
            logger.debug("Converting grades to YDS/V-scale")
            converted_grades = []
            binned_codes = []
            binned_grades = []
            for idx, row in df.iterrows():
                if row['discipline'] == ClimbingDiscipline.BOULDER:
                    # Font to V-scale
                    converted = await self.grade_service.convert_grade_system(
                        row['route_grade'],
                        GradingSystem.FONT,
                        GradingSystem.V_SCALE
                    )
                else:
                    # French to YDS
                    converted = await self.grade_service.convert_grade_system(
                        row['route_grade'],
                        GradingSystem.FRENCH,
                        GradingSystem.YDS
                    )
                converted = converted if converted else row['route_grade']
                converted_grades.append(converted)
                
                # Get binned code and grade for the converted grade
                code = await self.grade_service.convert_to_code(
                    converted,
                    GradingSystem.YDS if row['discipline'] != ClimbingDiscipline.BOULDER else GradingSystem.V_SCALE,
                    row['discipline']
                )
                binned_codes.append(code)
                
                # Get the binned grade (plus/minus version) from the code
                binned_grade = self.grade_service.get_grade_from_code(code)
                binned_grades.append(binned_grade)
            
            df['route_grade'] = converted_grades
            df['user_grade'] = df['route_grade']  # Update user grade to match converted grade
            df['binned_code'] = binned_codes
            df['binned_grade'] = binned_grades  # Use the plus/minus version for binned grades
            
            # Process send types and styles
            df = self._classify_sends(df)
            
            # Process route characteristics
            df = await self._process_route_characteristics(df)
            
            # Process length (8a.nu doesn't provide length)
            df['length'] = 0
            df['pitches'] = 1
            
            # Process dates
            df['tick_date'] = pd.to_datetime(df['date'])
            
            # Calculate difficulty categories
            logger.debug("Calculating difficulty categories")
            df['difficulty_category'] = self._calculate_difficulty_category(df)
            
            logger.info("8a.nu data processing completed", extra={
                "user_id": str(self.user_id),
                "processed_rows": len(df),
                "disciplines": df['discipline'].value_counts().to_dict(),
                "difficulty_categories": df['difficulty_category'].value_counts().to_dict(),
                "send_types": df['lead_style'].value_counts().to_dict()
            })
            
            return df
            
        except Exception as e:
            logger.error("Error processing 8a.nu data", extra={
                "user_id": str(self.user_id),
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise DataSourceError(f"Error processing 8a.nu data: {str(e)}")
            
    def _classify_disciplines(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify climbing disciplines based on category"""
        try:
            # Map 8a.nu categories to our disciplines
            discipline_map = {
                0: ClimbingDiscipline.SPORT,  # Sport climbing
                1: ClimbingDiscipline.BOULDER  # Bouldering
            }
            
            # First map based on category
            df['discipline'] = df['category'].map(discipline_map)
            
            # Override with TRAD for traditional routes
            df.loc[df['traditional'], 'discipline'] = ClimbingDiscipline.TRAD
            
            # Derive route_type from category and traditional flag
            df['route_type'] = df.apply(
                lambda x: 'Trad' if x['traditional'] else (
                    'Boulder' if x['category'] == 1 else 'Sport'
                ),
                axis=1
            )
            
            # Add lead_style based on type and traditional flag
            df['lead_style'] = df.apply(
                lambda x: 'Trad' if x['traditional'] else (
                    'Boulder' if x['category'] == 1 else 'Sport'
                ),
                axis=1
            )
            
            # Initialize notes column if not present
            if 'notes' not in df.columns:
                df['notes'] = ''
            
            discipline_counts = df['discipline'].value_counts()
            logger.info("Discipline classification completed", extra={
                "discipline_counts": discipline_counts.to_dict()
            })
            
            return df
            
        except Exception as e:
            logger.error("Error classifying disciplines", extra={
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise DataSourceError(f"Error classifying disciplines: {str(e)}")
            
    def _classify_sends(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify whether attempts were successful sends"""
        try:
            # In 8a.nu:
            # - project=True means it's not a send
            # - type='attempt' means it's not a send
            # - type='rp'/'os'/'fl' means it's a send
            df['send_bool'] = ~(df['project'] | (df['type'] == 'attempt'))
            
            # Classify send types based on 8a.nu's type field
            send_types = {
                'os': 'Onsight',
                'fl': 'Flash',
                'rp': 'Redpoint',
                'attempt': 'Project',
                'repeat': 'Repeat'
            }
            
            # Map the type to lead_style, defaulting to the original type if not in mapping
            df['lead_style'] = df['type'].map(send_types).fillna(df['type'])
            
            # For routes marked as traditional, add 'Trad' to the lead_style
            df.loc[df['traditional'], 'lead_style'] = df.loc[df['traditional'], 'lead_style'] + ' Trad'
            
            logger.info("Send classification completed", extra={
                "send_count": df['send_bool'].sum(),
                "project_count": (~df['send_bool']).sum(),
                "lead_style_distribution": df['lead_style'].value_counts().to_dict()
            })
            
            return df
            
        except Exception as e:
            logger.error(f"Error classifying sends: {str(e)}")
            raise DataSourceError(f"Error classifying sends: {str(e)}")
            
    async def _process_route_characteristics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process route characteristics from 8a.nu specific fields"""
        try:
            # Create crux angle based on route characteristics
            df['crux_angle'] = pd.NA
            
            # Priority order for angle classification with column existence check
            angle_conditions = []
            if 'isRoof' in df.columns and df['isRoof'].any():
                angle_conditions.append(('isRoof', CruxAngle.ROOF))
            if 'isOverhang' in df.columns and df['isOverhang'].any():
                angle_conditions.append(('isOverhang', CruxAngle.OVERHANG))
            if 'isVertical' in df.columns and df['isVertical'].any():
                angle_conditions.append(('isVertical', CruxAngle.VERTICAL))
            if 'isSlab' in df.columns and df['isSlab'].any():
                angle_conditions.append(('isSlab', CruxAngle.SLAB))
            
            # Apply angle classification
            for col, angle in angle_conditions:
                # Fill NA values with False and convert to boolean
                mask = df[col].fillna(False).astype(bool)
                df.loc[mask, 'crux_angle'] = angle
            
            # Create crux energy based on route characteristics
            df['crux_energy'] = pd.NA
            
            # Priority order for energy classification with column existence check
            energy_conditions = []
            if 'isAthletic' in df.columns and df['isAthletic'].any():
                energy_conditions.append(('isAthletic', CruxEnergyType.POWER))
            if 'isEndurance' in df.columns and df['isEndurance'].any():
                energy_conditions.append(('isEndurance', CruxEnergyType.ENDURANCE))
            if 'isCruxy' in df.columns and df['isCruxy'].any():
                energy_conditions.append(('isCruxy', CruxEnergyType.POWER))
            
            # Apply energy classification
            for col, energy in energy_conditions:
                # Fill NA values with False and convert to boolean
                mask = df[col].fillna(False).astype(bool)
                df.loc[mask, 'crux_energy'] = energy
            
            # Process additional characteristics and generate notes
            df['notes'] = df.apply(self._generate_notes, axis=1)
            
            # Log route characteristics
            angle_dist = df['crux_angle'].value_counts().to_dict()
            energy_dist = df['crux_energy'].value_counts().to_dict()
            grade_dist = df['route_grade'].value_counts().to_dict()
            
            logger.info("Route characteristics processed", extra={
                "angle_distribution": angle_dist,
                "energy_distribution": energy_dist,
                "grade_distribution": grade_dist
            })
            
            return df
            
        except Exception as e:
            logger.error("Error processing route characteristics", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise DataSourceError(f"Error processing route characteristics: {str(e)}")
            
    def _generate_notes(self, row: pd.Series) -> str:
        """Generate notes from route characteristics"""
        comment = ""
        characteristics = []
        
        # Add comment if exists, removing any existing pipe characters
        if 'comment' in row and pd.notna(row['comment']):
            comment = row['comment'].replace('|', '')
        
        # Add recommended tag first
        if 'recommended' in row and pd.notna(row['recommended']) and row['recommended']:
            characteristics.append('#recommended')
        
        # Route type characteristics second
        route_fields = {
            'traditional': '#trad'
        }
        
        for field, tag in route_fields.items():
            if field in row and pd.notna(row[field]) and row[field]:
                characteristics.append(tag)
        
        # Add angle characteristics third
        if 'isRoof' in row and pd.notna(row['isRoof']) and row['isRoof']:
            characteristics.append('#roof')
        elif 'isOverhang' in row and pd.notna(row['isOverhang']) and row['isOverhang']:
            characteristics.append('#overhang')
        elif 'isVertical' in row and pd.notna(row['isVertical']) and row['isVertical']:
            characteristics.append('#vertical')
        elif 'isSlab' in row and pd.notna(row['isSlab']) and row['isSlab']:
            characteristics.append('#slab')
        
        # Style characteristics fourth
        style_fields = {
            'isCrimpy': '#crimpy',
            'isSloper': '#slopers',
            'isTechnical': '#technical',
            'isAthletic': '#athletic',
            'isEndurance': '#endurance',
            'isCruxy': '#cruxy'
        }
        
        for field, tag in style_fields.items():
            if field in row and pd.notna(row[field]) and row[field]:
                characteristics.append(tag)
        
        # Additional characteristics fifth
        additional_fields = {
            'withKneepad': '#kneebar',
            'firstAscent': '#fa',
            'chipped': '#chipped',
            'isHard': '#sandbagged',
            'isSoft': '#soft'
        }
        
        for field, tag in additional_fields.items():
            if field in row and pd.notna(row[field]) and row[field]:
                characteristics.append(tag)
        
        # Warning tags last
        warning_fields = {
            'looseRock': '#looserock',
            'highFirstBolt': '#highfirstbolt',
            'badAnchor': '#badanchor',
            'badBolts': '#badbolts',
            'isDanger': '#dangerous',
            'badClippingPosition': '#badclips'
        }
        
        for field, tag in warning_fields.items():
            if field in row and pd.notna(row[field]) and row[field]:
                characteristics.append(tag)
        
        # Combine comment and characteristics with a single pipe separator
        comment = comment.strip()
        hashtags = ' '.join(characteristics).strip()
        return f"{comment} | {hashtags}" if comment and hashtags else (comment or hashtags)
            
    def _calculate_difficulty_category(self, df: pd.DataFrame) -> pd.Series:
        """Calculate difficulty categories based on grade indices."""
        conditions = [
            (df['binned_code'] <= 20),  # Beginner: up to 6b+
            (df['binned_code'] <= 24),  # Intermediate: up to 7a+
            (df['binned_code'] <= 28),  # Advanced: up to 7c
            (df['binned_code'] > 28)    # Elite: 7c+ and above
        ]
        choices = ['Beginner', 'Intermediate', 'Advanced', 'Elite']
        return pd.Series(np.select(conditions, choices, default='Unknown'), index=df.index)
