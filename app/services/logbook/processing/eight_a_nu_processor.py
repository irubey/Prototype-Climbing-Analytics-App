"""
8a.nu data processor.

This module provides functionality for:
- Processing 8a.nu JSON data
- Converting to standardized format matching UserTicks schema
- Classifying climbing data
- Calculating performance metrics
"""

# Standard library imports
from uuid import UUID
import traceback
import numpy as np
import asyncio
from typing import Optional

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
    """Processor for 8a.nu JSON data to convert it to standardized format for UserTicks."""

    def __init__(self, user_id: UUID):
        super().__init__(user_id)
        logger.info("Initializing 8a.nu processor", extra={"user_id": str(user_id)})
        self.grade_service = GradeService.get_instance()

    async def process_raw_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process raw 8a.nu JSON data into standardized format matching UserTicks."""
        try:
            logger.info("Starting 8a.nu data processing", extra={
                "user_id": str(self.user_id),
                "row_count": len(df),
                "columns": df.columns.tolist()
            })

            # Validate DataFrame
            if df.empty or len(df.columns) == 0:
                raise DataSourceError("No data found in 8a.nu response")

            # Set logbook type
            df['logbook_type'] = LogbookType.EIGHT_A_NU

            # Process locations
            logger.debug("Processing locations")
            df['location'] = df.apply(
                lambda x: f"{x['cragName']}, {x['areaName']}" if pd.notna(x['areaName']) else x['cragName'],
                axis=1
            )
            df['location_raw'] = None  # 8a.nu doesn't provide full raw location strings

            # Process route quality (convert 0-5 rating to 0-1 scale)
            logger.debug("Processing route quality")
            df['route_quality'] = df['rating'].apply(
                lambda x: float(x) / 5.0 if pd.notna(x) and x > 0 else None
            )
            df['user_quality'] = df['route_quality']  # 8a.nu uses a single rating

            # Process route name
            df['route_name'] = df['zlaggableName']

            # Keep original grades
            df['route_grade'] = df['difficulty']
            df['user_grade'] = df['route_grade']  # 8a.nu doesn't distinguish user vs. route grades

            # Classify disciplines (uses existing 'discipline' from scraper)
            df = self._classify_disciplines(df)

            # Convert grades to YDS/V-scale and bin them
            logger.debug("Converting grades to YDS/V-scale")
            converted_grades = []
            binned_codes = []
            binned_grades = []
            for idx, row in df.iterrows():
                source_system = GradingSystem.FONT if row['discipline'] == ClimbingDiscipline.BOULDER else GradingSystem.FRENCH
                target_system = GradingSystem.V_SCALE if row['discipline'] == ClimbingDiscipline.BOULDER else GradingSystem.YDS
                converted = await self.grade_service.convert_grade_system(
                    row['route_grade'],
                    source_system,
                    target_system
                )
                converted = converted if converted else row['route_grade']
                converted_grades.append(converted)

                code = await self.grade_service.convert_to_code(
                    converted,
                    target_system,
                    row['discipline']
                )
                binned_codes.append(code)

                binned_grade = self.grade_service.get_grade_from_code(code)
                binned_grades.append(binned_grade)

            df['route_grade'] = converted_grades
            df['user_grade'] = df['route_grade']
            df['binned_code'] = binned_codes
            df['binned_grade'] = binned_grades

            # Process send types and styles
            df = self._classify_sends(df)

            # Process route characteristics and notes
            df = await self._process_route_characteristics(df)

            # Process length and pitches (8a.nu doesn't provide these)
            df['length'] = 0
            df['pitches'] = 1

            # Process dates
            df['tick_date'] = pd.to_datetime(df['date']).dt.date  # Convert to date-only for UserTicks

            # Calculate difficulty categories
            logger.debug("Calculating difficulty categories")
            df['difficulty_category'] = self._calculate_difficulty_category(df)

            # Set defaults for fields not provided by 8a.nu
            df['route_url'] = df['zlaggableSlug'].apply(
                lambda x: f"https://www.8a.nu/crags/{x}" if pd.notna(x) else None
            )
            df['cur_max_rp_sport'] = None  # Computed later in PyramidBuilder
            df['cur_max_rp_trad'] = None
            df['cur_max_boulder'] = None
            df['length_category'] = None  # Requires length data
            df['season_category'] = None  # Requires tick_date analysis downstream

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
        """Classify climbing disciplines using existing 'discipline' from scraper."""
        try:
            if 'discipline' not in df.columns:
                raise DataSourceError("Discipline column missing from input data")

            # Map scraper's string discipline to enum
            discipline_map = {
                'sport': ClimbingDiscipline.SPORT,
                'boulder': ClimbingDiscipline.BOULDER
            }
            df['discipline'] = df['discipline'].map(discipline_map)

            # Override with TRAD for traditional routes
            df.loc[df['traditional'], 'discipline'] = ClimbingDiscipline.TRAD

            # Derive route_type
            df['route_type'] = df.apply(
                lambda x: 'Trad' if x['traditional'] else (
                    'Boulder' if x['discipline'] == ClimbingDiscipline.BOULDER else 'Sport'
                ),
                axis=1
            )

            # Initialize lead_style (will be refined in _classify_sends)
            df['lead_style'] = df['route_type']

            # Initialize notes column
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
        """Classify send status and styles based on 8a.nu 'type' and other fields."""
        try:
            # Determine if it's a send: not a project and not an attempt
            df['send_bool'] = ~(df['project'] | (df['type'] == 'attempt'))

            # Map 8a.nu send types to lead_style
            send_types = {
                'os': 'Onsight',
                'fl': 'Flash',  # Sport
                'f': 'Flash',   # Boulder
                'rp': 'Redpoint',
                'tr': 'Toprope',
                'attempt': 'Project',
                'repeat': 'Repeat'
            }

            # Apply send type mapping
            df['lead_style'] = df['type'].map(send_types).fillna(df['type'])

            # Adjust for traditional routes
            df.loc[df['traditional'], 'lead_style'] = df.loc[df['traditional'], 'lead_style'].apply(
                lambda x: f"{x} Trad" if x in ['Onsight', 'Flash', 'Redpoint', 'Toprope'] else x
            )

            logger.info("Send classification completed", extra={
                "send_count": df['send_bool'].sum(),
                "project_count": (~df['send_bool']).sum(),
                "lead_style_distribution": df['lead_style'].value_counts().to_dict()
            })

            return df

        except Exception as e:
            logger.error("Error classifying sends", extra={
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise DataSourceError(f"Error classifying sends: {str(e)}")

    async def _process_route_characteristics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process route characteristics and generate notes."""
        try:
            # Crux angle (priority: Roof > Overhang > Vertical > Slab)
            df['crux_angle'] = pd.NA
            for col, angle in [
                ('isRoof', CruxAngle.ROOF),
                ('isOverhang', CruxAngle.OVERHANG),
                ('isVertical', CruxAngle.VERTICAL),
                ('isSlab', CruxAngle.SLAB)
            ]:
                if col in df.columns:
                    mask = df[col].fillna(False).astype(bool)
                    df.loc[mask & df['crux_angle'].isna(), 'crux_angle'] = angle

            # Crux energy (priority: Endurance > Athletic/Cruxy as Power)
            df['crux_energy'] = pd.NA
            for col, energy in [
                ('isEndurance', CruxEnergyType.ENDURANCE),
                ('isAthletic', CruxEnergyType.POWER),
                ('isCruxy', CruxEnergyType.POWER)
            ]:
                if col in df.columns:
                    mask = df[col].fillna(False).astype(bool)
                    df.loc[mask & df['crux_energy'].isna(), 'crux_energy'] = energy

            # Generate notes
            df['notes'] = df.apply(self._generate_notes, axis=1)

            logger.info("Route characteristics processed", extra={
                "angle_distribution": df['crux_angle'].value_counts().to_dict(),
                "energy_distribution": df['crux_energy'].value_counts().to_dict(),
                "grade_distribution": df['route_grade'].dropna().value_counts().to_dict()
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
        """Generate notes from comments and characteristics."""
        comment = row['comment'].replace('|', '').strip() if pd.notna(row['comment']) else ""
        characteristics = []

        # Recommended
        if row.get('recommended', False):
            characteristics.append('#recommended')

        # Route type
        if row.get('traditional', False):
            characteristics.append('#trad')

        # Angle (single tag based on crux_angle priority)
        angle_tags = {
            CruxAngle.ROOF: '#roof',
            CruxAngle.OVERHANG: '#overhang',
            CruxAngle.VERTICAL: '#vertical',
            CruxAngle.SLAB: '#slab'
        }
        if pd.notna(row.get('crux_angle')):
            characteristics.append(angle_tags.get(row['crux_angle']))

        # Style characteristics
        style_fields = {
            'isCrimpy': '#crimpy',
            'isSloper': '#slopers',
            'isTechnical': '#technical',
            'isAthletic': '#athletic',
            'isEndurance': '#endurance',
            'isCruxy': '#cruxy'
        }
        for field, tag in style_fields.items():
            if row.get(field, False):
                characteristics.append(tag)

        # Additional characteristics
        additional_fields = {
            'withKneepad': '#kneebar',
            'firstAscent': '#fa',
            'chipped': '#chipped',
            'isHard': '#sandbagged',
            'isSoft': '#soft'
        }
        for field, tag in additional_fields.items():
            if row.get(field, False):
                characteristics.append(tag)

        # Warning tags
        warning_fields = {
            'looseRock': '#looserock',
            'highFirstBolt': '#highfirstbolt',
            'badAnchor': '#badanchor',
            'badBolts': '#badbolts',
            'isDanger': '#dangerous',
            'badClippingPosition': '#badclips'
        }
        for field, tag in warning_fields.items():
            if row.get(field, False):
                characteristics.append(tag)

        hashtags = ' '.join(characteristics).strip()
        return f"{comment} | {hashtags}" if comment and hashtags else (comment or hashtags)

    def _calculate_difficulty_category(self, df: pd.DataFrame) -> pd.Series:
        """Calculate difficulty categories based on binned_code."""
        conditions = [
            (df['binned_code'] <= 20),  # Beginner: up to ~6b+/V3
            (df['binned_code'] <= 24),  # Intermediate: up to ~7a+/V5
            (df['binned_code'] <= 28),  # Advanced: up to ~7c/V7
            (df['binned_code'] > 28)    # Elite: 7c+/V8 and above
        ]
        choices = ['Beginner', 'Intermediate', 'Advanced', 'Elite']
        return pd.Series(np.select(conditions, choices, default='Unknown'), index=df.index)