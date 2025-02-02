import pandas as pd
import requests
from io import StringIO
from typing import Tuple, Dict, Union
from uuid import UUID
from .grade_processor import GradeProcessor
from .climb_classifier import ClimbClassifier
from .pyramid_builder import PyramidBuilder
from .database_service import DatabaseService
from .exceptions import DataProcessingError
from app.models import UserTicks, PerformancePyramid, User
import logging
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class DataProcessor:
    """Main class that orchestrates the processing of climbing data"""
    
    def __init__(self, db_session):
        logger.info("Initializing DataProcessor")
        self.grade_processor = GradeProcessor()
        self.classifier = ClimbClassifier()
        self.pyramid_builder = PyramidBuilder()
        self.db_session = db_session
    
    def process_profile(self, user_id: str, profile_url: str) -> Tuple[Dict, pd.DataFrame]:
        """Process a user's Mountain Project profile"""
        logger.info(f"Processing user ticks for user_id: {user_id}")
        
        try:
            # Validate and convert UUID
            validated_uuid = self._validate_and_convert_uuid(user_id)
            logger.debug(f"Validated UUID: {validated_uuid}")
            
            # Download and process ticks
            logger.debug(f"Downloading CSV from: {profile_url}")
            raw_ticks_df = self.download_and_parse_csv(profile_url)
            
            # Process the raw data
            logger.debug("Processing raw tick data")
            processed_ticks = self.process_raw_data(raw_ticks_df, validated_uuid)
            
            # Save ticks to database
            logger.debug("Saving user ticks to database")
            DatabaseService.save_calculated_data({'user_ticks': processed_ticks})
            
            # Build performance pyramid
            logger.debug("Building performance pyramid")
            performance_pyramid = self.pyramid_builder.build_performance_pyramid(validated_uuid, self.db_session)
            
            # Save performance pyramid
            logger.debug("Saving performance pyramid")
            DatabaseService.save_calculated_data({'performance_pyramid': performance_pyramid})
            
            # Update user's Mountain Project sync timestamp
            self._update_user_sync_timestamp(validated_uuid)
            
            logger.info("Successfully processed profile and built performance pyramid")
            
            return performance_pyramid, processed_ticks
            
        except Exception as e:
            logger.error(f"Error processing profile: {str(e)}", exc_info=True)
            raise DataProcessingError(f"Error processing profile: {str(e)}")
            
    def process_user_ticks(self, profile_url: str, user_id: Union[UUID, str]) -> pd.DataFrame:
        """Process and return UserTicks dataframe without pyramids"""
        logger.info(f"Processing user ticks for user_id: {user_id}")
        try:
            # Download and parse CSV
            logger.debug(f"Downloading CSV from: {profile_url}")
            df = self.download_and_parse_csv(profile_url)
            
            # Process the raw data
            logger.debug("Processing raw tick data")
            processed_df = self.process_raw_data(df, user_id)
            
            logger.info(f"Successfully processed {len(processed_df)} ticks")
            return processed_df
            
        except Exception as e:
            logger.error(f"Error processing user ticks: {str(e)}", exc_info=True)
            raise DataProcessingError(f"Error processing user ticks: {str(e)}")
            
    def _validate_and_convert_uuid(self, user_id: Union[UUID, str]) -> UUID:
        """Validate and convert user_id to UUID"""
        logger.debug(f"Validating UUID: {user_id}")
        try:
            if isinstance(user_id, str):
                return UUID(user_id)
            elif isinstance(user_id, UUID):
                return user_id
            else:
                raise ValueError(f"Invalid user_id type: {type(user_id)}")
        except ValueError as e:
            logger.error(f"Invalid UUID format: {user_id}", exc_info=True)
            raise DataProcessingError(f"Invalid UUID format: {user_id}") from e
    
    def download_and_parse_csv(self, profile_url: str) -> pd.DataFrame:
        """Download and parse the CSV data"""
        logger.info(f"Downloading CSV from profile: {profile_url}")
        # Construct CSV URL
        csv_url = f"{profile_url}/tick-export"
            
        try:
            # Download CSV
            logger.debug(f"Making request to: {csv_url}")
            response = requests.get(csv_url, stream=False)
            if response.status_code != 200:
                logger.error(f"Failed to download CSV. Status code: {response.status_code}")
                raise DataProcessingError(f"Failed to download CSV from {csv_url}")
            
            # Parse CSV with proper encoding and error handling
            logger.debug("Parsing CSV data")
            data = StringIO(response.content.decode('utf-8'))
            df = pd.read_csv(data, 
                            sep=',',
                            quotechar='"',
                            escapechar='\\',
                            on_bad_lines='skip'
            )
            
            # Rename columns
            logger.debug("Renaming columns")
            df = df.rename(columns={
                'Date': 'tick_date',
                'Route': 'route_name',
                'Rating': 'route_grade',
                'Your Rating': 'user_grade',
                'Notes': 'notes',
                'URL': 'route_url',
                'Pitches': 'pitches',
                'Location': 'location',
                'Style': 'style',
                'Lead Style': 'lead_style',
                'Route Type': 'route_type',
                'Length': 'length',
                'Rating Code': 'binned_code',
                'Avg Stars': 'route_stars',
                'Your Stars': 'user_stars'
            })
            
            logger.info(f"Successfully parsed CSV with {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Error parsing CSV data: {str(e)}", exc_info=True)
            raise DataProcessingError(f"Error parsing CSV data: {str(e)}")
    
    def process_raw_data(self, df: pd.DataFrame, user_id: Union[UUID, str]) -> pd.DataFrame:
        """Process the raw climbing data"""
        logger.info("Starting raw data processing")
        try:
            # Validate and convert UUID first
            validated_uuid = self._validate_and_convert_uuid(user_id)
            logger.debug(f"Processing data for user_id: {validated_uuid}")
            
            # Create a UUID series for assignment
            uuid_series = pd.Series([validated_uuid] * len(df))
            
            # Add userId using validated UUID - ensure it's properly formatted
            df['user_id'] = uuid_series.astype(str)
            
            # Verify user_id is not null
            if df['user_id'].isnull().any():
                raise DataProcessingError("user_id cannot be null")
                
            logger.debug(f"Verified user_id is set for all {len(df)} rows")
            
            # Process data transformations
            logger.debug("Converting grades to codes")
            df['binned_code'] = self.grade_processor.convert_grades_to_codes(df['route_grade'])
            
            logger.debug("Adding binned grades")
            df['binned_grade'] = df['binned_code'].map(self.grade_processor.get_grade_from_code)
            
            logger.debug("Classifying climbs")
            df['discipline'] = self.classifier.classify_discipline(df)
            df['send_bool'] = self.classifier.classify_sends(df)
            
            logger.debug("Processing dates")
            df['tick_date'] = pd.to_datetime(df['tick_date'], errors='coerce').dt.date
            df = df.dropna(subset=['tick_date'])
            
            logger.debug("Processing lengths")
            df['length'] = df['length'].replace(0, pd.NA)
            df['length_category'] = self.classifier.classify_length(df)
            
            logger.debug("Processing seasons")
            df['season_category'] = self.classifier.classify_season(df)
            
            logger.debug("Processing locations")
            df['location'] = df['location'].astype(str)
            df['location_raw'] = df['location']
            df['location'] = df['location'].apply(lambda x: x.split('>')).apply(lambda x: x[:3])
            df['location'] = df['location'].apply(lambda x: f"{x[-1]}, {x[0]}")
            
            logger.debug("Processing route stars")
            df['route_stars'] = df['route_stars'].fillna(0) + 1
            df['user_stars'] = df['user_stars'].fillna(0) + 1
            
            logger.debug("Calculating max grades")
            df = self.calculate_max_grades(df)
            
            logger.debug("Calculating difficulty categories")
            df['difficulty_category'] = self.calculate_difficulty_category(df)
            
            logger.debug("Processing crux information")
            df = self.process_crux_info(df)
            
            logger.debug("Setting data types")
            df = self.set_data_types(df)
            
            logger.info(f"Successfully processed {len(df)} rows of raw data")
            return df
            
        except Exception as e:
            logger.error(f"Error processing raw data: {str(e)}", exc_info=True)
            raise DataProcessingError(f"Error processing raw data: {str(e)}")
    
    def calculate_max_grades(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate maximum grades for each discipline over time"""
        df = df.sort_values('tick_date')
        
        # Sport
        sport_mask = (df['discipline'] == 'sport') & (df['send_bool'])
        df.loc[sport_mask, 'cur_max_rp_sport'] = df.loc[sport_mask, 'binned_code'].cummax()
        df['cur_max_rp_sport'] = df['cur_max_rp_sport'].ffill().fillna(0)
        
        # Trad
        trad_mask = (df['discipline'] == 'trad') & (df['send_bool'])
        df.loc[trad_mask, 'cur_max_rp_trad'] = df.loc[trad_mask, 'binned_code'].cummax()
        df['cur_max_rp_trad'] = df['cur_max_rp_trad'].ffill().fillna(0)
        
        # Boulder
        boulder_mask = (df['discipline'] == 'boulder') & (df['send_bool'])
        df.loc[boulder_mask, 'cur_max_boulder'] = df.loc[boulder_mask, 'binned_code'].cummax()
        df['cur_max_boulder'] = df['cur_max_boulder'].ffill().fillna(0)
        
        return df
    
    def calculate_difficulty_category(self, df: pd.DataFrame) -> pd.Series:
        """Calculate difficulty category based on max grades"""
        def difficulty_bins(row):
            discipline = row['discipline']
            binned_code = row['binned_code']
            
            if discipline == 'sport':
                cur_max = row['cur_max_rp_sport']
                conditions = [
                    (binned_code >= cur_max),
                    (binned_code == cur_max - 1),
                    (binned_code == cur_max - 2),
                    (binned_code == cur_max - 3)
                ]
            elif discipline == 'trad':
                cur_max = row['cur_max_rp_trad']
                conditions = [
                    (binned_code >= cur_max),
                    (binned_code == cur_max - 1),
                    (binned_code == cur_max - 2),
                    (binned_code == cur_max - 3)
                ]
            elif discipline == 'boulder':
                cur_max = row['cur_max_boulder']
                conditions = [
                    (binned_code >= cur_max),
                    (binned_code == cur_max - 1),
                    (binned_code == cur_max - 2),
                    (binned_code == cur_max - 3)
                ]
            else:
                return 'Other'
                
            choices = ['Project', 'Tier 2', 'Tier 3', 'Tier 4']
            for condition, choice in zip(conditions, choices):
                if condition:
                    return choice
            return 'Base Volume'
        
        return df.apply(difficulty_bins, axis=1)
    
    def process_crux_info(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process crux information from notes and route descriptions"""
        try:
            # Extract crux angle information
            angle_keywords = {
                'Slab': ['slab', 'low angle', 'friction'],
                'Vertical': ['vertical', 'face', 'straight up'],
                'Overhang': ['overhang', 'steep', 'overhanging'],
                'Roof': ['roof', 'horizontal']
            }
            
            # Extract energy type information
            energy_keywords = {
                'Power': ['power', 'powerful', 'dynamic', 'explosive'],
                'Power_Endurance': ['power endurance', 'sustained', 'pumpy'],
                'Endurance': ['endurance', 'stamina', 'long'],
                'Technique': ['technical', 'balance', 'precise']
            }
            
            # Extract hold type information
            hold_keywords = {
                'Crimps': ['crimp', 'crimpy', 'small holds'],
                'Slopers': ['sloper', 'slopey', 'rounded'],
                'Pockets': ['pocket', 'mono', 'two finger'],
                'Pinches': ['pinch', 'pinchy'],
                'Cracks': ['crack', 'splitter', 'finger crack', 'hand crack']
            }
            
            # Combine notes and route description for analysis
            df['analysis_text'] = df['notes'].fillna('') + ' ' + df['route_name'].fillna('')
            df['analysis_text'] = df['analysis_text'].str.lower()
            
            # Classify crux angle
            for angle, keywords in angle_keywords.items():
                mask = df['analysis_text'].str.contains('|'.join(keywords), na=False)
                df.loc[mask, 'crux_angle'] = angle
                
            # Classify energy type
            for energy, keywords in energy_keywords.items():
                mask = df['analysis_text'].str.contains('|'.join(keywords), na=False)
                df.loc[mask, 'crux_energy'] = energy
                
            # Drop temporary analysis column
            df = df.drop('analysis_text', axis=1)
            
            return df
            
        except Exception as e:
            logger.error(f"Error processing crux information: {str(e)}")
            return df
    
    def set_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Set appropriate data types for columns"""
        try:
            logger.debug("Starting data type conversion")
            
            # Handle UUID first to ensure it's valid throughout the process
            if 'user_id' not in df.columns:
                raise DataProcessingError("user_id column is missing")
            
            if df['user_id'].isnull().any():
                raise DataProcessingError("user_id contains null values")
            
            # Convert user_id to proper UUID format
            try:
                df['user_id'] = df['user_id'].apply(lambda x: str(UUID(str(x).strip())))
                logger.debug("Successfully converted user_id to UUID format")
            except ValueError as e:
                logger.error(f"Invalid UUID format in user_id column: {e}")
                raise DataProcessingError(f"Invalid UUID format in user_id column: {e}")
            
            # String types
            df['route_name'] = df['route_name'].astype(str)
            df['route_grade'] = df['route_grade'].astype(str)
            df['notes'] = df['notes'].fillna('').astype(str).str.strip()
            df['location'] = df['location'].astype(str)
            df['location_raw'] = df['location_raw'].astype(str)
            
            # Integer types with null handling
            integer_columns = {
                'pitches': 0,
                'binned_code': 0,
                'cur_max_rp_sport': 0,
                'cur_max_rp_trad': 0,
                'cur_max_boulder': 0
            }
            
            for col, default in integer_columns.items():
                df[col] = df[col].fillna(default).astype('int64')
            
            # Nullable integer
            df['length'] = pd.to_numeric(df['length'], errors='coerce').astype('Int64')
            
            # Enum types with proper casing
            df['discipline'] = df['discipline'].str.lower()
            df['lead_style'] = df['lead_style'].str.title()
            
            # Boolean types with explicit conversion
            df['send_bool'] = df['send_bool'].fillna(False).astype(bool)
            
            # Float types with null handling
            float_columns = ['route_stars', 'user_stars']
            for col in float_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
            logger.debug("Successfully set data types for all columns")
            return df
            
        except Exception as e:
            logger.error(f"Error setting data types: {str(e)}", exc_info=True)
            raise DataProcessingError(f"Error setting data types: {str(e)}")
    
    def _update_user_sync_timestamp(self, user_id: UUID) -> None:
        """Update the user's Mountain Project sync timestamp"""
        try:
            user = self.db_session.query(User).filter_by(id=user_id).first()
            if user:
                user.mtn_project_last_sync = datetime.now(timezone.utc)
                self.db_session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error updating user sync timestamp: {str(e)}")
            self.db_session.rollback()
