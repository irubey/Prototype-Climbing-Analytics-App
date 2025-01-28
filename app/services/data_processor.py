import pandas as pd
import requests
from io import StringIO
from typing import Tuple, Dict
from .grade_processor import GradeProcessor
from .climb_classifier import ClimbClassifier
from .pyramid_builder import PyramidBuilder
from .database_service import DatabaseService
from app.models import UserTicks
import logging

logger = logging.getLogger(__name__)

class DataProcessor:
    """Main class that orchestrates the processing of climbing data"""
    
    def __init__(self, db_session):
        self.grade_processor = GradeProcessor()
        self.classifier = ClimbClassifier()
        self.db_session = db_session
    
    def process_user_ticks(self, profile_url: str, user_id: int, username: str) -> pd.DataFrame:
        """Process and return UserTicks dataframe without pyramids"""
        df = self.download_and_parse_csv(profile_url)
        processed_df = self.process_raw_data(df, user_id)
        return processed_df

    
    def download_and_parse_csv(self, profile_url: str) -> pd.DataFrame:
        """Download and parse the CSV data"""
        # Construct CSV URL
        csv_url = f"{profile_url}/tick-export"
        
        # Download CSV
        response = requests.get(csv_url, stream=False)
        if response.status_code != 200:
            raise ValueError(f"Failed to download CSV from {csv_url}")
        
        # Parse CSV with proper encoding and error handling
        try:
            data = StringIO(response.content.decode('utf-8'))
            df = pd.read_csv(data, 
                            sep=',',  # Explicitly set separator
                            quotechar='"',  # Handle quoted fields
                            escapechar='\\',  # Handle escaped characters
                            on_bad_lines='skip'  # Skip problematic lines
                            )
            
            # Rename columns
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
            
            return df
            
        except Exception as e:
            raise ValueError(f"Error parsing CSV data: {str(e)}")
    
    def process_raw_data(self, df: pd.DataFrame, user_id: int) -> pd.DataFrame:
        """Process the raw climbing data"""
        # Add userId FIRST before any processing
        df = df.assign(user_id=user_id)  # Immutable assignment
        
        # Convert grades to codes
        df['binned_code'] = self.grade_processor.convert_grades_to_codes(df['route_grade'])
        
        # Add binned grades
        df['binned_grade'] = df['binned_code'].map(self.grade_processor.get_grade_from_code)
        
        # Classify climbs
        df['discipline'] = self.classifier.classify_discipline(df)
        df['send_bool'] = self.classifier.classify_sends(df)
        
        # Process dates
        df['tick_date'] = pd.to_datetime(df['tick_date'], errors='coerce').dt.date
        df = df.dropna(subset=['tick_date'])
        
        # Process lengths
        df['length'] = df['length'].replace(0, pd.NA)
        df['length_category'] = self.classifier.classify_length(df)
        
        # Process seasons
        df['season_category'] = self.classifier.classify_season(df)
        
        # Process locations
        df['location'] = df['location'].astype(str)
        df['location_raw'] = df['location']
        df['location'] = df['location'].apply(lambda x: x.split('>')).apply(lambda x: x[:3])
        df['location'] = df['location'].apply(lambda x: f"{x[-1]}, {x[0]}")
        
        # Add route_stars
        df['route_stars'] = df['route_stars'].fillna(0) + 1
        
        # Add user_stars
        df['user_stars'] = df['user_stars'].fillna(0) + 1
        
        # Calculate max grades
        df = self.calculate_max_grades(df)
        
        # Calculate difficulty categories
        df['difficulty_category'] = self.calculate_difficulty_category(df)
        
        # Set data types
        df = self.set_data_types(df)
        
        # Insert data directly without stripping 'id'
        records = df.to_dict('records')
        
        # Batch insert with proper transaction handling
        try:
            with self.db_session.begin_nested():
                self.db_session.bulk_insert_mappings(UserTicks, records)
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise
        
        return df
    
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
    
    def set_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Set appropriate data types for columns"""
        # String types
        df['route_name'] = df['route_name'].astype(str)
        df['route_grade'] = df['route_grade'].astype(str)
        df['notes'] = df['notes'].fillna('').astype(str).str.strip()
        
        # Integer types - using standard Python int
        if 'user_id' in df.columns:
            df['user_id'] = df['user_id'].astype('int64').astype(int)
        df['pitches'] = df['pitches'].astype('int64').astype(int)
        df['binned_code'] = df['binned_code'].astype('int64').astype(int)
        df['cur_max_rp_sport'] = df['cur_max_rp_sport'].astype('int64').astype(int)
        df['cur_max_rp_trad'] = df['cur_max_rp_trad'].astype('int64').astype(int)
        df['cur_max_boulder'] = df['cur_max_boulder'].astype('int64').astype(int)
        
        # Nullable integer
        df['length'] = df['length'].astype('Int64')
        
        # Enum types - ensure values match database enums
        df['discipline'] = df['discipline'].str.lower()  # Keep lowercase for enum names
        
        # Convert lead_style to match enum names
        df['lead_style'] = df['lead_style'].str.title()

        
        # Category types
        df['length_category'] = df['length_category'].astype('category')
        df['season_category'] = df['season_category'].astype('category')
        
        return df 

    def process_demo_data(self, user_id: int, username: str):
        """Process demo user data using a predefined Mountain Project profile"""
        demo_url = "https://www.mountainproject.com/user/200169262/isaac-rubey"
        
        # Process core data
        df = self.download_and_parse_csv(demo_url)
        processed_df = self.process_raw_data(df, user_id)

        # Build pyramids
        pyramid_builder = PyramidBuilder()
        user_ticks = UserTicks.query.filter_by(user_id=user_id).all()
        # Convert to DataFrame with required columns
        ticks_df = pd.DataFrame([{
            'id': t.id,
            'user_id': t.user_id,
            'route_name': t.route_name,
            'tick_date': t.tick_date,
            'route_grade': t.route_grade,
            'binned_code': t.binned_code,
            'discipline': t.discipline,
            'notes': t.notes,
            'send_bool': t.send_bool,
            'location': t.location
        } for t in user_ticks])
        
        sport_pyramid, trad_pyramid, boulder_pyramid = pyramid_builder.build_all_pyramids(
            ticks_df, 
            self.db_session
        )
        
        # After building pyramids
        DatabaseService.save_calculated_data({
            'sport_pyramid': sport_pyramid,
            'trad_pyramid': trad_pyramid,
            'boulder_pyramid': boulder_pyramid
        })

        return sport_pyramid, trad_pyramid, boulder_pyramid 