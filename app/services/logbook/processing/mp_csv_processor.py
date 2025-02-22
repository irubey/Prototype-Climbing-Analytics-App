"""
Mountain Project CSV data processor.

This module provides functionality for:
- Processing Mountain Project CSV exports
- Normalizing data formats
- Standardizing field names and types
"""

# Standard library imports
from datetime import datetime, timezone
from typing import Dict
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
            standardized_df['route_name'] = df['route']
            standardized_df['route_grade'] = df['rating']
            standardized_df['tick_date'] = pd.to_datetime(df['date'])
            standardized_df['length'] = pd.to_numeric(df['length'], errors='coerce').fillna(0).astype(int)
            standardized_df['pitches'] = pd.to_numeric(df['pitches'], errors='coerce').fillna(1).astype(int)
            standardized_df['route_url'] = df['url']
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
                        lambda x: f"{x[-1].strip()}, {x[0].strip()}" if len(x) >= 2 else x[0].strip()
                )
            
            # Style and quality fields
            standardized_df['lead_style'] = df['lead_style'].fillna('')
            standardized_df['style'] = df['style'].fillna('')
            standardized_df['route_type'] = df['route_type'].fillna('')
            # Normalize Mountain Project ratings (0-4 scale) to 0-1 scale
            # Handle -1 (no data) as null, then normalize valid ratings by dividing by max score (4)
            standardized_df['route_quality'] = df['avg_stars'].apply(
                lambda x: None if x == -1 else (float(x) / 4.0) if pd.notna(x) else None
            )
            standardized_df['user_quality'] = df['your_stars'].apply(
                lambda x: None if x == -1 else (float(x) / 4.0) if pd.notna(x) else None
            )
            
            # Initialize classification fields (will be set by orchestrator)
            standardized_df['discipline'] = None
            standardized_df['send_bool'] = None
            standardized_df['length_category'] = None
            standardized_df['season_category'] = None
            standardized_df['crux_angle'] = None
            standardized_df['crux_energy'] = None
            
            # Initialize grade processing fields (will be set by orchestrator)
            standardized_df['binned_grade'] = None
            standardized_df['binned_code'] = None
            standardized_df['cur_max_rp_sport'] = 0
            standardized_df['cur_max_rp_trad'] = 0
            standardized_df['cur_max_boulder'] = 0
            
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
