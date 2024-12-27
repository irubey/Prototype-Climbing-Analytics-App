import pandas as pd
import requests
from io import StringIO
from typing import Tuple, Dict
from .grade_processor import GradeProcessor
from .climb_classifier import ClimbClassifier
from .pyramid_builder import PyramidBuilder

class DataProcessor:
    """Main class that orchestrates the processing of climbing data"""
    
    def __init__(self):
        self.grade_processor = GradeProcessor()
        self.classifier = ClimbClassifier()
    
    def process_profile(self, profile_url: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
        """Process a Mountain Project profile URL and return the processed data."""
        # Extract username from URL
        username = profile_url.split('/')[-1]
        
        # Download and parse CSV data
        df = self.download_and_parse_csv(profile_url)
        
        # Process raw climbing data
        processed_df = self.process_raw_data(df, username)
        
        # Calculate max grades
        self.calculate_max_grades(processed_df)
        
        # Build pyramids
        pyramid_builder = PyramidBuilder()
        sport_pyramid, trad_pyramid, boulder_pyramid = pyramid_builder.build_all_pyramids(processed_df)
        
        return sport_pyramid, trad_pyramid, boulder_pyramid, processed_df, username
    
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
    
    def process_raw_data(self, df: pd.DataFrame, username: str) -> pd.DataFrame:
        """Process the raw climbing data"""
        # Convert grades to codes
        df['binned_code'] = self.grade_processor.convert_grades_to_codes(df['route_grade'])
        
        # Add binned grades
        df['binned_grade'] = df['binned_code'].map(self.grade_processor.get_grade_from_code)
        
        # Classify climbs
        df['discipline'] = self.classifier.classify_discipline(df)
        df['send_bool'] = self.classifier.classify_sends(df)
        
        # Process dates
        df['tick_date'] = pd.to_datetime(df['tick_date'], errors='coerce')
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
        
        # Add username
        df['username'] = username
        
        # Calculate max grades
        df = self.calculate_max_grades(df)
        
        # Calculate difficulty categories
        df['difficulty_category'] = self.calculate_difficulty_category(df)
        
        # Set data types
        df = self.set_data_types(df)
        
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
        df['route_name'] = df['route_name'].astype(str)
        df['route_grade'] = df['route_grade'].astype(str)
        df['pitches'] = df['pitches'].astype(int)
        df['lead_style'] = df['lead_style'].astype('category')
        df['length'] = df['length'].astype('Int64')
        df['binned_code'] = df['binned_code'].astype(int)
        df['cur_max_rp_sport'] = df['cur_max_rp_sport'].astype(int)
        df['cur_max_rp_trad'] = df['cur_max_rp_trad'].astype(int)
        df['cur_max_boulder'] = df['cur_max_boulder'].astype(int)
        df['length_category'] = df['length_category'].astype('category')
        df['season_category'] = df['season_category'].astype('category')
        df['discipline'] = df['discipline'].astype('category')
        
        return df 