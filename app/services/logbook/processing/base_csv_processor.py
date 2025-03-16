"""
Base CSV processor for climbing logbook data.

This module provides:
- Abstract base class for CSV processors
- Common data processing utilities
- Standardized data transformation methods
- Tag extraction functionality
"""

# Standard library imports
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List
from uuid import UUID
import traceback
import re

# Third-party imports
import pandas as pd

# Application imports
from app.core.exceptions import DataSourceError
from app.core.logging import logger

from app.models.enums import (
    ClimbingDiscipline,
    CruxAngle,
    CruxEnergyType,
)

class BaseCSVProcessor(ABC):
    """Base processor for climbing logbook CSV data"""
    
    def __init__(self, user_id: UUID):
        self.user_id = user_id
        
    @abstractmethod
    def process_raw_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process raw CSV data into standardized format"""
        pass
        
    def process_ticks(self, df: pd.DataFrame) -> List[Dict]:
        """
        Process DataFrame into UserTicks models
        
        Args:
            df: DataFrame with standardized column names
            
        Returns:
            List of dictionaries representing UserTicks records
        """
        try:
            logger.debug(
                "Processing user ticks",
                extra={
                    "user_id": str(self.user_id),
                    "row_count": len(df)
                }
            )
            
            # Ensure required columns exist
            required_columns = {
                'tick_date', 'route_name', 'route_grade', 'binned_grade',
                'binned_code', 'discipline', 'send_bool'
            }
            missing_columns = required_columns - set(df.columns)
            if missing_columns:
                raise DataSourceError(f"Missing required columns: {missing_columns}")
            
            # Convert dates
            df['tick_date'] = pd.to_datetime(df['tick_date']).dt.date
            df['created_at'] = datetime.now()
            
            # Process numeric columns
            numeric_columns = {
                'length': 0,
                'pitches': 1,
                'route_quality': 0.0,
                'user_quality': 0.0,
                'cur_max_rp_sport': 0,
                'cur_max_rp_trad': 0,
                'cur_max_boulder': 0
            }
            
            for col, default in numeric_columns.items():
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(default)
            
            # Convert to list of dicts
            ticks_data = df.to_dict('records')
            
            # Add user_id to each record
            for tick in ticks_data:
                tick['user_id'] = self.user_id
                
                # Ensure boolean fields are proper booleans
                if 'send_bool' in tick:
                    tick['send_bool'] = bool(tick['send_bool'])
            
            logger.info(
                "Successfully processed user ticks",
                extra={
                    "user_id": str(self.user_id),
                    "processed_count": len(ticks_data)
                }
            )
            
            return ticks_data
            
        except Exception as e:
            logger.error(
                "Error processing user ticks",
                extra={
                    "user_id": str(self.user_id),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
            )
            raise DataSourceError(f"Error processing user ticks: {str(e)}")
    
    def process_performance_pyramid(
        self,
        df: pd.DataFrame,
        tick_id_map: Dict[int, int]
    ) -> List[Dict]:
        """
        Process DataFrame into PerformancePyramid models
        
        Args:
            df: DataFrame with standardized column names
            tick_id_map: Mapping of temporary IDs to database IDs for UserTicks
            
        Returns:
            List of dictionaries representing PerformancePyramid records
        """
        try:
            logger.debug(
                "Processing performance pyramid",
                extra={
                    "user_id": str(self.user_id),
                    "tick_count": len(tick_id_map)
                }
            )
            
            pyramid_data = []
            
            # Group by location and grade for performance analysis
            grouped = df[df['send_bool']].groupby(['location', 'binned_code'])
            
            for (location, binned_code), group in grouped:
                # Basic metrics
                num_sends = len(group)
                num_attempts = len(df[
                    (df['location'] == location) &
                    (df['binned_code'] == binned_code)
                ])
                
                # Get the first send date for this grade at this location
                first_send = group['tick_date'].min()
                
                # Calculate days between first attempt and first send
                first_attempt = df[
                    (df['location'] == location) &
                    (df['binned_code'] == binned_code)
                ]['tick_date'].min()
                
                days_attempts = (first_send - first_attempt).days if first_attempt else 0
                
                # Create pyramid record
                for _, send in group.iterrows():
                    temp_tick_id = send.name  # DataFrame index
                    if temp_tick_id not in tick_id_map:
                        continue
                        
                    pyramid_record = {
                        'user_id': self.user_id,
                        'tick_id': tick_id_map[temp_tick_id],
                        'send_date': send['tick_date'],
                        'location': location,
                        'binned_code': binned_code,
                        'num_attempts': num_attempts,
                        'days_attempts': days_attempts,
                        'num_sends': num_sends
                    }
                    
                    # Add crux information if available
                    if 'crux_angle' in send:
                        pyramid_record['crux_angle'] = CruxAngle(send['crux_angle'])
                    if 'crux_energy' in send:
                        pyramid_record['crux_energy'] = CruxEnergyType(send['crux_energy'])
                    
                    pyramid_data.append(pyramid_record)
            
            logger.info(
                "Successfully processed performance pyramid",
                extra={
                    "user_id": str(self.user_id),
                    "pyramid_records": len(pyramid_data)
                }
            )
            
            return pyramid_data
            
        except Exception as e:
            logger.error(
                "Error processing performance pyramid",
                extra={
                    "user_id": str(self.user_id),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
            )
            raise DataSourceError(f"Error processing performance pyramid: {str(e)}")
    
    def extract_tags(self, df: pd.DataFrame) -> List[str]:
        """
        Extract tags from route names and notes
        
        Args:
            df: DataFrame with standardized column names
            
        Returns:
            List of unique tags
        """
        try:
            tags = set()
            
            # Extract tags from notes (hashtags)
            if 'notes' in df.columns:
                notes_tags = df['notes'].str.findall(r'#(\w+)').explode().unique()
                tags.update(tag.lower() for tag in notes_tags if pd.notna(tag))
            
            # Extract common climbing terms from route names
            if 'route_name' in df.columns:
                route_terms = df['route_name'].str.findall(
                    r'\b(crack|slab|arete|dihedral|roof|corner|face|chimney)\b',
                    flags=re.IGNORECASE
                ).explode().unique()
                tags.update(term.lower() for term in route_terms if pd.notna(term))
            
            logger.info(
                "Successfully extracted tags",
                extra={
                    "user_id": str(self.user_id),
                    "tag_count": len(tags)
                }
            )
            
            return list(tags)
            
        except Exception as e:
            logger.error(
                "Error extracting tags",
                extra={
                    "user_id": str(self.user_id),
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            )
            return []  # Return empty list on error rather than failing
