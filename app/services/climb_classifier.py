import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime

class ClimbClassifier:
    """Handles classification of climbs into different types and categories"""
    
    def __init__(self):
        self.lead_sends = ['Redpoint', 'Flash', 'Onsight', 'Pinkpoint']
        self.boulder_sends = ['Send', 'Flash']
        self.length_bins = [0, 60, 85, 130, 50000]
        self.length_labels = ['short', 'medium', 'long', 'multipitch']
        self.season_categories = {
            (3, 4, 5): 'Spring',
            (6, 7, 8): 'Summer',
            (9, 10, 11): 'Fall',
            (12, 1, 2): 'Winter'
        }
        # Add lead style indicators
        self.lead_indicators = ['Lead', 'Onsight', 'Flash', 'Redpoint', 'Pinkpoint']
        self.gear_indicators = ['Gear', 'Trad', 'Placed Gear', 'Traditional']
        self.sport_indicators = ['Bolts', 'Sport', 'Quickdraws']
        self.follow_indicators = ['Follow', 'TR', 'Second', 'Top Rope', 'Following']
    
    def classify_discipline(self, df: pd.DataFrame) -> pd.Series:
        """Classify climbs into disciplines (sport, trad, boulder, etc.)"""
        
        def determine_discipline(row):
            # Handle missing route type
            if pd.isna(row['route_type']):
                return None
                
            # Extract types
            types = [t.strip() for t in str(row['route_type']).split(',')]
            lead_style = str(row['lead_style']) if pd.notna(row['lead_style']) else ''
            style = str(row['style']) if pd.notna(row['style']) else ''
            notes = str(row['notes']) if pd.notna(row['notes']) else ''
            
            # Check for explicit TR/Follow style first
            if any(fi in style for fi in self.follow_indicators) or any(fi in lead_style for fi in self.follow_indicators):
                return 'tr'
            
            # Check if it's a boulder based on grade range
            if (row['binned_code'] >= 100) and (row['binned_code'] < 200):
                return 'boulder'
            
            # Handle simple cases
            if len(types) == 1:
                type_map = {
                    'Sport': 'sport',
                    'Trad': 'trad',
                    'Boulder': 'boulder',
                    'TR': 'tr'
                }
                return type_map.get(types[0])
            
            # Sport/TR combinations
            if ('Sport' in types and 'TR' in types):
                if any(ls in lead_style for ls in self.lead_indicators):
                    return 'sport'
                if 'Lead' in style:
                    return 'sport'
                return 'tr'  # Default to TR if no lead indicators
            
            # Trad/TR combinations
            if ('Trad' in types and 'TR' in types):
                if any(ls in lead_style for ls in self.lead_indicators):
                    return 'trad'
                if 'Lead' in style:
                    return 'trad'
                return 'tr'  # Default to TR if no lead indicators
            
            # Trad/Sport combinations
            if ('Trad' in types and 'Sport' in types) or ('Sport' in types and 'Trad' in types):
                # Look for explicit gear indicators
                if (any(gi in style.lower() for gi in self.gear_indicators) or 
                    any(gi in notes.lower() for gi in self.gear_indicators)):
                    return 'trad'
                    
                # Look for explicit sport indicators
                if (any(si in style.lower() for si in self.sport_indicators) or 
                    any(si in notes.lower() for si in self.sport_indicators)):
                    return 'sport'
                    
                # If no clear indicators, return None
                return None
            
            # Handle Alpine/Trad
            if 'Alpine' in types and 'Trad' in types:
                return 'trad'
            
            # Default cases based on primary type
            if 'Sport' in types:
                return 'sport'
            if 'Trad' in types:
                return 'trad'
            if 'Boulder' in types:
                return 'boulder'
            
            return None
        
        return df.apply(determine_discipline, axis=1)
    
    def classify_sends(self, df: pd.DataFrame) -> pd.Series:
        """Determine if climbs were successfully sent"""
        # For boulders:
        # - Style is Send/Flash -> True
        # - Style is Attempt -> False
        # - Style is None/empty -> pass (handled by fillna(False))
        is_boulder = df['discipline'] == 'boulder'
        is_roped = df['discipline'] != 'boulder'
        
        # Handle boulder sends/attempts
        boulder_sends = is_boulder & df['style'].isin(self.boulder_sends)
        boulder_attempts = is_boulder & (df['style'] == 'Attempt')
        
        # Handle roped climbs with standard lead_sends classification
        roped_sends = is_roped & (df['lead_style'].isin(self.lead_sends))
        
        # Combine all conditions
        return (boulder_sends | roped_sends & ~boulder_attempts).fillna(False)
    
    def _is_multipitch_from_notes(self, notes: str) -> bool:
        """Check if route is multipitch based on note content"""
        if pd.isna(notes):
            return False
            
        notes = notes.lower()
        multipitch_indicators = [
            'p1', 'p2', 'p3', 'p4', 'p5',
            'swapped leads', 'swung leads', 'simul', 
            'simulclimb', 'simul climb', 'simul-climb',
            'linked pitches', 'multi-pitch', 'multipitch', 
            'pitches'
        ]
        return any(indicator in notes for indicator in multipitch_indicators)
    
    def classify_length(self, df: pd.DataFrame) -> pd.Series:
        """Classify routes by length"""
        # First try to identify multipitch from notes
        is_multipitch = df['notes'].apply(self._is_multipitch_from_notes)
        
        # Then do standard length classification
        length_categories = pd.cut(df['length'], 
                     bins=self.length_bins, 
                     labels=self.length_labels, 
                     right=False)
        
        # Override with multipitch if identified from notes
        length_categories = length_categories.mask(is_multipitch, 'multipitch')
        
        return length_categories
    
    def classify_season(self, df: pd.DataFrame) -> pd.Series:
        """Classify climbs by season"""
        def season_mapping(row: pd.Series) -> str:
            month, year = row['tick_month'], row['tick_year']
            for months, season in self.season_categories.items():
                if month in months:
                    if season == "Winter":
                        # Handle December differently for winter
                        if month == 12:
                            return f"{season}, {year}-{year+1}"
                        # Handle Jan & Feb differently for winter
                        elif month in [1, 2]:
                            return f"{season}, {year-1}-{year}"
                    return f"{season}, {year}"
            return f'Unknown, {year}'
        
        # Extract month and year
        df = df.copy()
        df['tick_month'] = pd.to_datetime(df['tick_date']).dt.month
        df['tick_year'] = pd.to_datetime(df['tick_date']).dt.year
        
        # Apply season mapping
        seasons = df[['tick_month', 'tick_year']].apply(season_mapping, axis=1)
        
        # Clean up temporary columns
        df.drop(['tick_month', 'tick_year'], axis=1, inplace=True)
        
        return seasons