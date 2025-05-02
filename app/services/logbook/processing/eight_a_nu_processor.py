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
from datetime import datetime, timezone
import re

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
            # Log raw data structure in detail
            if not df.empty:
                sample_row = df.iloc[0]
                logger.info("Raw 8a.nu data structure", extra={
                    "columns": df.columns.tolist(),
                    "sample_row": sample_row.to_dict(),
                    "boolean_fields": {
                        col: df[col].sum() 
                        for col in df.columns 
                        if df[col].dtype == bool
                    }
                })

            logger.info("Starting 8a.nu data processing", extra={
                "user_id": str(self.user_id),
                "row_count": len(df),
                "columns": df.columns.tolist()
            })

            # Validate DataFrame
            if df.empty or len(df.columns) == 0:
                raise DataSourceError("No data found in 8a.nu response")

            # Create standardized DataFrame with all required columns
            standardized_df = pd.DataFrame(index=df.index)
            logger.info("Created empty standardized DataFrame", extra={
                "index_size": len(standardized_df.index)
            })

            # Required fields from UserTicks model
            standardized_df['id'] = None  # Will be set by database
            standardized_df['user_id'] = self.user_id
            standardized_df['logbook_type'] = LogbookType.EIGHT_A_NU
            standardized_df['created_at'] = datetime.now(timezone.utc)
            logger.info("Added basic required fields", extra={
                "fields_added": ['id', 'user_id', 'logbook_type', 'created_at']
            })

            # Route information (direct mappings)
            standardized_df['route_name'] = df['zlaggableName']
            standardized_df['tick_date'] = pd.to_datetime(df['date'], utc=True)
            standardized_df['length'] = 0  # 8a.nu doesn't provide length
            standardized_df['pitches'] = 1  # Default for 8a.nu
            standardized_df['route_url'] = df['zlaggableSlug'].apply(
                lambda x: f"https://www.8a.nu/crags/{x}" if pd.notna(x) else None
            )

            # Copy boolean fields from raw data
            boolean_fields = [
                'firstAscent', 'chipped', 'withKneepad', 'badAnchor', 'badBolts',
                'highFirstBolt', 'looseRock', 'badClippingPosition', 'isHard',
                'isSoft', 'isBoltedByMe', 'isOverhang', 'isVertical', 'isSlab',
                'isRoof', 'isAthletic', 'isEndurance', 'isCrimpy', 'isCruxy',
                'isSloper', 'isTechnical', 'isDanger'
            ]
            
            for field in boolean_fields:
                if field in df.columns:
                    standardized_df[field] = df[field]
                    logger.debug(f"Copied boolean field {field}", extra={
                        "field": field,
                        "true_count": df[field].sum() if field in df.columns else 0,
                        "dtype": str(df[field].dtype)
                    })

            logger.info("Copied boolean fields", extra={
                "fields_copied": [f for f in boolean_fields if f in df.columns],
                "sample_boolean_values": {f: df[f].sum() for f in boolean_fields if f in df.columns},
                "available_fields": df.columns.tolist()
            })

            # Location processing
            def extract_state(area_name):
                if pd.isna(area_name):
                    return None
                # Look for state in parentheses
                match = re.search(r'\((.*?)\)', area_name)
                if match:
                    return match.group(1)
                return None

            def format_location(row):
                area_name = row['areaName']
                crag_name = row['cragName']
                country_name = row['countryName']
                state = extract_state(area_name)
                
                if pd.notna(area_name):
                    # Remove state from area name if present
                    area_name = re.sub(r'\s*\(.*?\)', '', area_name)
                    if state:
                        return f"{area_name}, {state}"
                    else:
                        return f"{area_name}, {country_name}"
                return crag_name

            standardized_df['location'] = df.apply(format_location, axis=1)
            
            # Format location_raw with state if present
            standardized_df['location_raw'] = df.apply(
                lambda x: ' > '.join(filter(None, [
                    x.get('countryName'),
                    extract_state(x.get('areaName')) if pd.notna(x.get('areaName')) else None,
                    re.sub(r'\s*\(.*?\)', '', x.get('areaName')) if pd.notna(x.get('areaName')) else None,
                    x.get('cragName'),
                    x.get('sectorName')
                ])),
                axis=1
            )
            logger.info("Processed location information", extra={
                "location_count": standardized_df['location'].notna().sum(),
                "location_raw_count": standardized_df['location_raw'].notna().sum(),
                "sample_location": standardized_df['location'].iloc[0] if len(standardized_df) > 0 else None,
                "sample_location_raw": standardized_df['location_raw'].iloc[0] if len(standardized_df) > 0 else None
            })

            # Style and quality fields
            standardized_df['lead_style'] = df['type'].map({
                'os': 'Onsight',
                'fl': 'Flash',  # Sport
                'f': 'Flash',   # Boulder
                'rp': 'Redpoint',
                'tr': None,  # Toprope is a discipline, not a lead style
                'attempt': 'Fell/Hung',
                'repeat': 'Fell/Hung'
            })

            # Set discipline based on lead style
            standardized_df['discipline'] = df['discipline'].map({
                'sport': ClimbingDiscipline.SPORT,
                'boulder': ClimbingDiscipline.BOULDER
            })
            standardized_df.loc[df['traditional'], 'discipline'] = ClimbingDiscipline.TRAD
            # Override discipline to TR if it's a toprope
            standardized_df.loc[df['type'] == 'tr', 'discipline'] = ClimbingDiscipline.TR

            standardized_df['route_type'] = df.apply(
                lambda x: 'Trad' if x['traditional'] else (
                    'Boulder' if x['discipline'] == ClimbingDiscipline.BOULDER else 'Sport'
                ),
                axis=1
            )
            logger.info("Processed style information", extra={
                "lead_style_distribution": standardized_df['lead_style'].value_counts().to_dict(),
                "route_type_distribution": standardized_df['route_type'].value_counts().to_dict(),
                "discipline_distribution": standardized_df['discipline'].value_counts().to_dict()
            })

            # Process route quality (convert 0-5 rating to 0-1 scale)
            standardized_df['route_quality'] = df['rating'].apply(
                lambda x: float(x) / 5.0 if pd.notna(x) and x > 0 else None
            )
            standardized_df['user_quality'] = standardized_df['route_quality']  # 8a.nu uses a single rating
            logger.info("Processed quality ratings", extra={
                "quality_ratings_count": standardized_df['route_quality'].notna().sum(),
                "quality_range": {
                    "min": standardized_df['route_quality'].min(),
                    "max": standardized_df['route_quality'].max()
                } if standardized_df['route_quality'].notna().any() else None
            })

            # Initialize classification fields
            standardized_df['send_bool'] = ~(df['project'] | (df['type'] == 'attempt'))
            standardized_df['length_category'] = None  # Requires length data
            standardized_df['season_category'] = None  # Requires tick_date analysis downstream
            logger.info("Initialized classification fields", extra={
                "discipline_distribution": standardized_df['discipline'].value_counts().to_dict(),
                "send_rate": f"{(standardized_df['send_bool'].sum() / len(standardized_df)) * 100:.1f}%"
            })

            # Process notes and tags
            standardized_df['notes'] = df['comment'].fillna('') if 'comment' in df.columns else ''
            
            # Generate tags and ensure they're properly assigned
            tags = standardized_df.apply(self._generate_tags, axis=1)
            standardized_df['tags'] = tags
            
            # Log tag generation results with limited samples
            logger.info("Processed notes and tags", extra={
                "notes_count": standardized_df['notes'].notna().sum(),
                "tags_count": tags.notna().sum(),
                "sample_notes": standardized_df['notes'].head(10).tolist() if len(standardized_df) > 0 else None,
                "sample_tags": tags.head(10).tolist() if len(tags) > 0 else None,
                "tags_distribution": {
                    "total_rows": len(tags),
                    "rows_with_tags": tags.notna().sum(),
                    "sample_tag_values": tags.head(10).tolist()
                }
            })

            # Initialize grade processing fields
            standardized_df['binned_grade'] = None
            standardized_df['binned_code'] = None
            standardized_df['difficulty_category'] = None
            standardized_df['cur_max_sport'] = 0
            standardized_df['cur_max_trad'] = 0
            standardized_df['cur_max_boulder'] = 0
            standardized_df['cur_max_tr'] = 0
            standardized_df['cur_max_alpine'] = 0
            standardized_df['cur_max_winter_ice'] = 0
            standardized_df['cur_max_aid'] = 0
            standardized_df['cur_max_mixed'] = 0

            # Convert grades to YDS/V-scale and bin them
            logger.info("Starting grade conversion process", extra={
                "total_grades": len(df),
                "sample_original_grades": df['difficulty'].head().tolist()
            })

            converted_grades = []
            binned_codes = []
            binned_grades = []
            
            # Process grades in batches for better performance
            BATCH_SIZE = 100
            for i in range(0, len(standardized_df), BATCH_SIZE):
                batch_df = standardized_df.iloc[i:i + BATCH_SIZE]
                logger.debug(f"Processing grade batch {i//BATCH_SIZE + 1}", extra={
                    "batch_start": i,
                    "batch_end": min(i + BATCH_SIZE, len(standardized_df)),
                    "batch_size": len(batch_df)
                })
                
                for idx, row in batch_df.iterrows():
                    source_system = GradingSystem.FONT if row['discipline'] == ClimbingDiscipline.BOULDER else GradingSystem.FRENCH
                    target_system = GradingSystem.V_SCALE if row['discipline'] == ClimbingDiscipline.BOULDER else GradingSystem.YDS
                    
                    # Get original grade from input data
                    original_grade = df.loc[idx, 'difficulty']
                    
                    # Convert grade system
                    converted = await self.grade_service.convert_grade_system(
                        original_grade,
                        source_system,
                        target_system
                    )
                    converted = converted if converted else original_grade
                    converted_grades.append(converted)

                    # Convert to code
                    code = await self.grade_service.convert_to_code(
                        converted,
                        target_system,
                        row['discipline']
                    )
                    binned_codes.append(code)

                    # Get binned grade
                    binned_grade = self.grade_service.get_grade_from_code(code)
                    binned_grades.append(binned_grade)

            standardized_df['route_grade'] = converted_grades
            standardized_df['binned_code'] = binned_codes
            standardized_df['binned_grade'] = binned_grades
            logger.info("Completed grade conversion", extra={
                "converted_grades_count": len(converted_grades),
                "binned_codes_count": len(binned_codes),
                "sample_conversions": list(zip(
                    df['difficulty'].head().tolist(),
                    converted_grades[:5],
                    binned_codes[:5],
                    binned_grades[:5]
                ))
            })


            # Clean the dataframe to handle NaN values for database insertion
            string_columns = ['route_name', 'route_grade', 'binned_grade', 'location', 
                            'location_raw', 'lead_style', 'route_type', 
                            'difficulty_category', 'length_category', 'season_category', 
                            'route_url', 'notes', 'tags']
            for col in string_columns:
                if col in standardized_df.columns:
                    standardized_df.loc[:, col] = standardized_df[col].astype(object).where(pd.notna(standardized_df[col]), None)

            numeric_columns = ['route_quality', 'user_quality', 'binned_code']
            for col in numeric_columns:
                if col in standardized_df.columns:
                    standardized_df.loc[:, col] = standardized_df[col].where(pd.notna(standardized_df[col]), None)
            logger.info("Cleaned DataFrame for database insertion", extra={
                "string_columns_cleaned": string_columns,
                "numeric_columns_cleaned": numeric_columns
            })

            logger.info("8a.nu data processing completed", extra={
                "user_id": str(self.user_id),
                "processed_rows": len(standardized_df),
                "disciplines": standardized_df['discipline'].value_counts().to_dict(),
                "difficulty_categories": standardized_df['difficulty_category'].value_counts().to_dict(),
                "send_types": standardized_df['lead_style'].value_counts().to_dict()
            })

            return standardized_df

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
        try:
            # Safely get notes
            notes = ""
            if 'notes' in row and pd.notna(row['notes']):
                notes = str(row['notes']).replace('|', '').strip()
            
            logger.debug("Processing notes", extra={
                "has_notes": 'notes' in row,
                "notes_value": row.get('notes')
            })

            characteristics = []

            # Map boolean fields to standardized tags
            tag_mapping = {
                # Route characteristics
                'recommended': '#recommended',
                'traditional': '#trad',
                'firstAscent': '#fa',
                'chipped': '#chipped',
                'withKneepad': '#kneebar',
                'isHard': '#sandbagged',
                'isSoft': '#soft',
                'isBoltedByMe': '#boltedbyme',
                
                # Angle characteristics
                'isRoof': '#roof',
                'isOverhang': '#overhang',
                'isVertical': '#vertical',
                'isSlab': '#slab',
                
                # Style characteristics
                'isAthletic': '#athletic',
                'isEndurance': '#endurance',
                'isCrimpy': '#crimpy',
                'isCruxy': '#cruxy',
                'isSloper': '#slopers',
                'isTechnical': '#technical',
                
                # Warning tags
                'looseRock': '#looserock',
                'highFirstBolt': '#highfirstbolt',
                'badAnchor': '#badanchor',
                'badBolts': '#badbolts',
                'isDanger': '#dangerous',
                'badClippingPosition': '#badclips'
            }

            # Add tags based on boolean fields
            for field, tag in tag_mapping.items():
                if field in row and row[field] is True:
                    characteristics.append(tag)

            hashtags = ' '.join(characteristics).strip()
            return f"{notes} | {hashtags}" if notes and hashtags else (notes or hashtags)

        except Exception as e:
            logger.error("Error generating notes", extra={
                "error": str(e),
                "row_keys": list(row.keys()),
                "row_values": {k: v for k, v in row.items() if pd.notna(v)}
            })
            return ""  # Return empty string on error

    def _generate_tags(self, row: pd.Series) -> Optional[list]:
        """Generate tags from boolean fields in the ascents data."""
        try:
            tags = []

            # Map boolean fields to standardized tags - these must match STANDARDIZED_TAG_MAPPING in orchestrator.py
            tag_mapping = {
                'firstAscent': 'firstAscent',
                'chipped': 'chipped',
                'withKneepad': 'withKneepad',
                'badAnchor': 'badAnchor',
                'badBolts': 'badBolts',
                'highFirstBolt': 'highFirstBolt',
                'looseRock': 'looseRock',
                'badClippingPosition': 'badClippingPosition',
                'isHard': 'isHard',
                'isSoft': 'isSoft',
                'isBoltedByMe': 'isBoltedByMe',
                'isOverhang': 'isOverhang',
                'isVertical': 'isVertical',
                'isSlab': 'isSlab',
                'isRoof': 'isRoof',
                'isAthletic': 'isAthletic',
                'isEndurance': 'isEndurance',
                'isCrimpy': 'isCrimpy',
                'isCruxy': 'isCruxy',
                'isSloper': 'isSloper',
                'isTechnical': 'isTechnical',
                'isDanger': 'isDanger'
            }


            # Add tags based on boolean fields
            for field, tag in tag_mapping.items():
                if field in row and row[field] is True:
                    tags.append(tag)
                    logger.debug(f"Added tag for {field}", extra={
                        "field": field,
                        "value": row[field],
                        "tag": tag
                    })

            if tags:
                logger.debug("Generated tags", extra={
                    "row_fields": {k: v for k, v in row.items() if pd.notna(v)},
                    "generated_tags": tags
                })

            return tags if tags else None

        except Exception as e:
            logger.error("Error generating tags", extra={
                "error": str(e),
                "row_keys": list(row.keys()),
                "row_values": {k: v for k, v in row.items() if pd.notna(v)}
            })
            return None  # Return None on error
