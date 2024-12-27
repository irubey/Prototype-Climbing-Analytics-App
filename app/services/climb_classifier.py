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
    
    def classify_discipline(self, df: pd.DataFrame) -> pd.Series:
        """Classify climbs into disciplines (sport, trad, boulder, etc.)"""
        conditions = [
            ((df['binned_code'] >= 0) & (df['binned_code'] < 100) & 
             (df['route_type'] == 'Trad') | (df['route_type'] == 'Trad, Alpine')),
            ((df['binned_code'] >= 0) & (df['binned_code'] < 100) & 
             (df['route_type'] == 'Sport') | (df['route_type'] == 'Sport, Alpine')),
            ((df['binned_code'] >= 100) & (df['binned_code'] < 200)),
            ((df['binned_code'] >= 200) & (df['binned_code'] < 300)),
            ((df['binned_code'] >= 300) & (df['binned_code'] < 400)),
            ((df['binned_code'] >= 400) & (df['binned_code'] < 500))
        ]
        choices = ['trad', 'sport', 'boulder', 'winter/ice', 'mixed', 'aid']
        return pd.Series(np.select(conditions, choices, default=None))
    
    def classify_sends(self, df: pd.DataFrame) -> pd.Series:
        """Determine if climbs were successfully sent"""
        return ((df['lead_style'].isin(self.lead_sends)) | 
                (df['style'].isin(self.boulder_sends))).fillna(False)
    
    def classify_length(self, df: pd.DataFrame) -> pd.Series:
        """Classify routes by length"""
        return pd.cut(df['length'], 
                     bins=self.length_bins, 
                     labels=self.length_labels, 
                     right=False)
    
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