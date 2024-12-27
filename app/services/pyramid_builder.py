import pandas as pd
from typing import Tuple, Dict
from .grade_processor import GradeProcessor
import time

class PyramidBuilder:
    """Handles the creation of climbing pyramids for different disciplines"""
    
    def __init__(self):
        self.custom_routes_grade_list = [
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
        self.custom_boulders_grade_list = [
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

    def build_pyramid(self, df, discipline):
        """Build a pyramid for a specific discipline."""
        # Clean data
        df = df.dropna(how='all')
        df = df[df['send_bool'] == True]  # Filter for sends only
        df = df[df['discipline'] == discipline]

        if df.empty:
            return df

        # Remove duplicates based on route_name and location, keep oldest tick_date
        df = df.sort_values('tick_date')
        df = df.drop_duplicates(subset=['route_name', 'location'], keep='first')

        # Get top 4 binned codes
        top_binned_code = df['binned_code'].max()
        top4_binned_codes = list(range(top_binned_code, top_binned_code - 4, -1))
        df = df[df['binned_code'].isin(top4_binned_codes)]

        # Add custom sorting grade
        df['custom_sorting_grade'] = df['route_grade'].str.split(' ').str[0]
        
        # Apply custom grade sorting
        if discipline in ['sport', 'trad']:
            df['custom_sorting_grade'] = pd.Categorical(
                df['custom_sorting_grade'], 
                categories=self.custom_routes_grade_list, 
                ordered=True
            )
        else:  # boulder
            df['custom_sorting_grade'] = pd.Categorical(
                df['custom_sorting_grade'], 
                categories=self.custom_boulders_grade_list, 
                ordered=True
            )

        # Sort by binned_code and grade
        df = df.sort_values(['binned_code', 'custom_sorting_grade'], ascending=[False, False])

        # Calculate attempts
        def calculate_num_attempts(row):
            if row['length_category'] == 'multipitch':
                return df.loc[df['route_name'] == row['route_name']].shape[0]
            else:
                return df.loc[df['route_name'] == row['route_name'], 'pitches'].sum()

        df['num_attempts'] = df.apply(calculate_num_attempts, axis=1)

        # Handle tick_id assignment - preserve UserTicks id
        if 'id' in df.columns:
            df['tick_id'] = df['id']  # Set tick_id from UserTicks id
        else:
            # For any rows without a tick_id, generate new ones with a prefix
            df['tick_id'] = None
            null_mask = df['tick_id'].isnull()
            if null_mask.any():
                # Generate smaller tick_ids that fit in PostgreSQL integer range (-2147483648 to +2147483647)
                # Use timestamp modulo 10000 to keep numbers very small
                timestamp = int(time.time()) % 10000
                df.loc[null_mask, 'tick_id'] = [
                    int(f"9{timestamp:04d}{i:03d}")  # Format: 9TTTTNNN where T=timestamp, N=counter
                    for i in range(len(df[null_mask]))
                ]

        # Drop unnecessary columns
        columns_to_drop = [
            'cur_max_rp_sport', 'cur_max_rp_trad', 'cur_max_boulder',
            'send_bool', 'difficulty_category', 'custom_sorting_grade',
            'id'  # Drop id after preserving it as tick_id
        ]
        df = df.drop(columns=columns_to_drop, errors='ignore')

        return df

    def build_all_pyramids(self, df):
        """Build pyramids for all disciplines."""
        sport_pyramid = self.build_pyramid(df, 'sport')
        trad_pyramid = self.build_pyramid(df, 'trad')
        boulder_pyramid = self.build_pyramid(df, 'boulder')
        
        return sport_pyramid, trad_pyramid, boulder_pyramid