import pandas as pd
from typing import Tuple, Dict
from .grade_processor import GradeProcessor
import time
from sqlalchemy import func, or_, text
from sqlalchemy.orm import aliased
from sqlalchemy.sql import or_
from app.models import SportPyramid, TradPyramid, BoulderPyramid

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
        
        # Add style and characteristic keywords
        self.style_keywords = {
            'Slab': ['slab', 'low angle'],
            'Vertical': ['vertical', 'vertical face','vert'],
            'Overhang': ['overhang', 'steep' 'overhanging'],
            'Roof': ['roof', 'horizontal', 'ceiling']
        }
        
        self.characteristic_keywords = {
            'Power': ['powerful', 'dynamic', 'boulder', 'bouldery', 'power'],
            'Power Endurance': ['resistance', 'sustained', 'power endurance'],
            'Endurance': ['endurance', 'continuous', 'no rest']
        }

    def predict_style_characteristic(self, row, db_session):
        """Predict route style and characteristic based on evidence with optimized DB queries."""
        route_name = row['route_name']
        location = row['location']
        notes = row.get('notes', '').lower() if pd.notna(row.get('notes')) else ''
        
        style = None
        characteristic = None
        
        # Query existing pyramid data
        for table in [SportPyramid, TradPyramid, BoulderPyramid]:
            if style and characteristic:
                break
            
            existing_data = (db_session.query(
                table.route_style,
                table.route_characteristic,
                func.count(table.route_style).label('style_count'),
                func.count(table.route_characteristic).label('char_count')
            )
            .filter(
                table.route_name == route_name,
                table.location == location,
                or_(
                    table.route_style.isnot(None),
                    table.route_characteristic.isnot(None)
                )
            )
            .group_by(table.route_style, table.route_characteristic)
            .order_by(text('style_count DESC, char_count DESC'))
            .limit(1)
            .first())
            
            if existing_data:
                style = style or existing_data.route_style
                characteristic = characteristic or existing_data.route_characteristic
        
        # Check notes for keywords if still not found
        if not style and notes:
            for s, keywords in self.style_keywords.items():
                if any(keyword in notes for keyword in keywords):
                    style = s
                    break
        
        if not characteristic and notes:
            for c, keywords in self.characteristic_keywords.items():
                if any(keyword in notes for keyword in keywords):
                    characteristic = c
                    break
        
        # Return None if we couldn't determine style/characteristic
        return style, characteristic

    def build_pyramid(self, df, discipline, db_session):
        """Build a pyramid with optimized style/characteristic prediction."""
        # Store the full dataset before filtering for sends, but filter by discipline
        all_attempts_df = df[df['discipline'] == discipline].copy()
        
        # Continue with send filtering for the pyramid
        df = df.dropna(how='all')
        df = df[df['send_bool'] == True]
        df = df[df['discipline'] == discipline]
        
        if df.empty:
            return df
        
        # Initialize route_style and route_characteristic as None
        df['route_style'] = None
        df['route_characteristic'] = None
        
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

        # New attempt calculation that uses the full dataset
        def calculate_num_attempts(row):
            route_entries = all_attempts_df[
                (all_attempts_df['route_name'] == row['route_name']) & 
                (all_attempts_df['location'] == row['location'])
            ]
            
            if row['length_category'] == 'multipitch':
                # For multipitch: count unique entries since each entry represents a full attempt
                return len(route_entries)
            else:
                # For single pitch: sum the pitches across all entries since each pitch represents an attempt
                return route_entries['pitches'].sum()
        
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

        # Predict styles and characteristics
        if db_session is not None:
            predictions = df.apply(
                lambda row: self.predict_style_characteristic(row, db_session), 
                axis=1
            )
            df['route_style'] = df['route_style'].fillna(
                pd.Series([p[0] for p in predictions], index=df.index)
            )
            df['route_characteristic'] = df['route_characteristic'].fillna(
                pd.Series([p[1] for p in predictions], index=df.index)
            )

        return df

    def build_all_pyramids(self, df, db_session=None):
        """Build pyramids for all disciplines."""
        sport_pyramid = self.build_pyramid(df, 'sport', db_session)
        trad_pyramid = self.build_pyramid(df, 'trad', db_session)
        boulder_pyramid = self.build_pyramid(df, 'boulder', db_session)
        
        return sport_pyramid, trad_pyramid, boulder_pyramid