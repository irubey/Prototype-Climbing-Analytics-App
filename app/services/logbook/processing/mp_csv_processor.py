"""
Mountain Project CSV data processor.

This module provides functionality for:
- Processing Mountain Project CSV exports
- Normalizing data formats
- Standardizing field names and types
"""

# Standard library imports
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID
import traceback

# Third-party imports
import pandas as pd

# Application imports
from app.core.exceptions import DataSourceError
from app.core.logging import logger
from app.models.enums import LogbookType, ClimbingDiscipline
from app.services.logbook.processing.base_csv_processor import BaseCSVProcessor

class MountainProjectCSVProcessor(BaseCSVProcessor):
    """Processor for Mountain Project CSV data"""
    
    def __init__(self, user_id: UUID):
        super().__init__(user_id)
        logger.info("Initializing Mountain Project CSV processor", extra={
            "user_id": str(user_id)
        })
    
    def process_raw_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process raw Mountain Project CSV data into standardized format matching UserTicks model"""
        try:
            logger.info("Starting Mountain Project data normalization", extra={
                "user_id": str(self.user_id),
                "row_count": len(df),
                "columns": df.columns.tolist()
            })
            
            # Validate DataFrame is not empty
            if df.empty or len(df.columns) == 0:
                raise DataSourceError("No data found in Mountain Project CSV")
            
            # Check required columns before proceeding
            required_columns = ['route_name', 'route_grade', 'tick_date']
            missing_columns = [col for col in required_columns if col.lower() not in [c.lower() for c in df.columns]]
            if missing_columns:
                logger.warning(
                    "Mountain Project CSV missing required columns",
                    extra={
                        "user_id": str(self.user_id),
                        "missing_columns": missing_columns
                    }
                )
                raise DataSourceError("No data found in Mountain Project CSV")
            
            # Normalize column names to lowercase and replace spaces with underscores
            df.columns = df.columns.str.lower().str.replace(' ', '_')
            
            # Create DataFrame with exact UserTicks model fields
            standardized_df = pd.DataFrame(index=df.index)
            
            # Required fields from UserTicks model
            standardized_df['id'] = None  # Will be set by database
            standardized_df['user_id'] = self.user_id
            standardized_df['logbook_type'] = LogbookType.MOUNTAIN_PROJECT
            standardized_df['created_at'] = datetime.now(timezone.utc)
            
            # Route information (direct mappings)
            standardized_df['route_name'] = df['route_name']
            standardized_df['route_grade'] = df['route_grade']
            standardized_df['tick_date'] = pd.to_datetime(df['tick_date'], utc=True)
            standardized_df['length'] = pd.to_numeric(df['length'], errors='coerce').fillna(0).astype(int)
            standardized_df['pitches'] = pd.to_numeric(df['pitches'], errors='coerce').fillna(1).astype(int)
            standardized_df['route_url'] = df['route_url']
            standardized_df['notes'] = df['notes']
            
            # Location processing
            standardized_df['location'] = df['location'].astype(str)
            standardized_df['location_raw'] = None  # Default to None
            
            # Process hierarchical locations if '>' separator exists
            mask = df['location'].str.contains('>')
            if mask.any():
                standardized_df.loc[mask, 'location_raw'] = df.loc[mask, 'location']
                standardized_df.loc[mask, 'location'] = standardized_df.loc[mask, 'location'].apply(
                    lambda x: x.split('>')).apply(
                        lambda x: f"{x[-2].strip()}, {x[0].strip()}" if len(x) >= 2 else x[0].strip()
                )
            
            # Style and quality fields
            standardized_df['lead_style'] = df['lead_style'].fillna('')
            standardized_df['style'] = df['style'].fillna('')
            standardized_df['route_type'] = df['route_type'].fillna('')
            # Normalize Mountain Project ratings (0-4 scale) to 0-1 scale
            # Handle -1 (no data) as null, then normalize valid ratings by dividing by max score (4)
            standardized_df['route_quality'] = df['route_stars'].apply(
                lambda x: None if x == -1 else (float(x) / 4.0) if pd.notna(x) else None
            )
            standardized_df['user_quality'] = df['user_stars'].apply(
                lambda x: None if x == -1 else (float(x) / 4.0) if pd.notna(x) else None
            )
            
            # Initialize classification fields (will be set by orchestrator)
            standardized_df['discipline'] = None
            standardized_df['send_bool'] = None
            standardized_df['length_category'] = None
            standardized_df['season_category'] = None
            standardized_df['crux_angle'] = None
            standardized_df['crux_energy'] = None

            # Extract tags from notes
            standardized_df['tags'] = standardized_df['notes'].apply(self._extract_tags_from_notes)
            
            # Initialize grade processing fields (will be set by orchestrator)
            standardized_df['binned_grade'] = None
            standardized_df['binned_code'] = None
            standardized_df['cur_max_sport'] = 0
            standardized_df['cur_max_trad'] = 0
            standardized_df['cur_max_boulder'] = 0
            standardized_df['cur_max_tr'] = 0
            standardized_df['cur_max_alpine'] = 0
            standardized_df['cur_max_winter_ice'] = 0
            standardized_df['cur_max_aid'] = 0
            standardized_df['cur_max_mixed'] = 0
            
            # Clean the dataframe to handle NaN values for database insertion
            # Replace NaN with None in string columns to avoid PostgreSQL errors
            string_columns = ['route_name', 'route_grade', 'binned_grade', 'location', 
                             'location_raw', 'lead_style', 'style', 'route_type', 
                             'difficulty_category', 'length_category', 'season_category', 
                             'route_url', 'notes']
            for col in string_columns:
                if col in standardized_df.columns:
                    standardized_df.loc[:, col] = standardized_df[col].astype(object).where(pd.notna(standardized_df[col]), None)

            # Replace NaN with None in numeric columns that can be null
            numeric_columns = ['route_quality', 'user_quality', 'binned_code']
            for col in numeric_columns:
                if col in standardized_df.columns:
                    standardized_df.loc[:, col] = standardized_df[col].where(pd.notna(standardized_df[col]), None)

            logger.info("Mountain Project data normalization completed", extra={
                "user_id": str(self.user_id),
                "processed_rows": len(standardized_df)
            })
            
            return standardized_df
            
        except Exception as e:
            logger.error("Error normalizing Mountain Project data", extra={
                "user_id": str(self.user_id),
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise DataSourceError(f"Error normalizing Mountain Project data: {str(e)}")
        
    def _extract_tags_from_notes(self, notes: str) -> Optional[list]:
        """Extract tags from the notes field with improved matching."""
        if pd.isna(notes):
            return None
        
        notes = notes.lower().strip()
        if not notes:
            return None
            
        logger.debug(f"Processing notes for tags: {notes[:100]}")  # Log first 100 chars
        
        tags = set()  
        
        # Define tag keywords with more flexible matching
        tag_keywords = {
            # 8a tags
            'looseRock': ['choss', 'loose rock', 'breaking', 'broke', 'crumbling', 'sketchy rock'],
            'isDanger': ['deck', 'sketchy', 'danger', 'scary', 'runout', 'no fall zone', 'run out'],
            'isHard': ['hard', 'tough', 'difficult', 'sandbag', 'stout', 'old school'],
            'isSoft': ['easy', 'soft', 'casual', 'walked'],
            'isOverhang': ['overhang', 'overhanging'],
            'isSlab': ['slab', 'friction', 'slabby'],
            'isRoof': ['roof', 'ceiling'],
            'isEndurance': ['pump', 'enduro', 'sustained', 'long', 'consistent', 'endurance'],
            'isCrimpy': ['crimp', 'tiny', 'small', 'micro'],
            'isCruxy': ['cruxy', 'hard move', 'difficult move', 'boulder problem', 'boulder crux'],
            'isSloper': ['sloper', 'slopey', 'sloping'],
            'isTechnical': ['tech', 'balance', 'precise', 'delicate', 'technical', 'techy'],
            'badBolts': ['spinner', 'loose hardware', 'bad bolts', 'bad bolt', 'sketchy bolts', 'sketchy bolt', 'bad hardware'],
            'highFirstBolt': ['high first clip', 'stick clip', 'high first bolt', 'first bolt pretty high', 'first bolt high'],
            'badAnchor': ['bad anchor', 'sketchy anchor', 'loose anchor'],
            'firstAscent': ['first ascent'],
            'withKneepad': ['knee pad', 'kneepad', 'knee bar', 'kneebar'],
            'isAthletic': ['athletic', 'powerful', 'dynamic', 'jump', 'dyno', 'dino', 'deadpoint', 'dead point', 'burly'],

            # Feature Tags:
            'arete': ['arete'],
            'corner': ['corner', 'dihedral', 'dihedral'],
            
            #Hold Types:
            'pinch': ['pinch', 'pinchy'],
            'crimp': ['crimp', 'crimpy'],
            'sloper': ['sloper', 'slopey'],
            'jug': ['jug'],
            'pocket': ['pocket'],
            'crack': ['crack', 'fingercrack', 'fistjam', 'fingerjam', 'offwidth', 'off width', 'off-width', 'chicken wing', 'chickenwing', 'splitter'],

            #positions
            'gaston': ['shoulder', 'gaston'],
            'heelhook': ['heelhook', 'heel hook'],
            'sidepull': ['sidepull', 'side pull'],
            'undercling': ['undercling'],
            'dropknee': ['drop knee'],
            'flag': ['flag', 'flagging'],
            'crossthrough': ['crossthrough', 'crossover', 'rose move'],
            'batHang': ['bat hang', 'bathang'],


        }
        
        # Helper to check for negation within reasonable distance
        def is_negated(text: str, start_idx: int, max_distance: int = 5) -> bool:
            words = text[:start_idx].strip().split()
            # Check last few words for negations
            check_words = words[-max_distance:] if len(words) > max_distance else words
            return any(neg in check_words for neg in ['not', 'no', 'never', "isn't", "wasn't", "aren't", "when", "if", "sometimes"])
        
        # Process each keyword pattern
        for tag, patterns in tag_keywords.items():
            for pattern in patterns:
                idx = notes.find(pattern)
                while idx != -1:
                    # Check if it's a reasonable match (word boundaries or close enough)
                    if (idx == 0 or notes[idx-1] in ' ,.!?-') and not is_negated(notes, idx):
                        tags.add(tag)
                        break  # Found a match for this tag, move to next tag
                    idx = notes.find(pattern, idx + 1)
        
        # Convert set to list for return
        extracted_tags = list(tags)
        
        if extracted_tags:
            logger.debug(f"Extracted tags from notes: {extracted_tags}")
        
        return extracted_tags if extracted_tags else None