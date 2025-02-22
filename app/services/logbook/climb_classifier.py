"""
Climb classification service.

This module provides functionality for:
- Classifying climbs by discipline
- Determining send status
- Analyzing route characteristics
- Categorizing climbs by length and season
"""

from typing import Optional
import pandas as pd

from app.core.logging import logger
from app.models.enums import (
    ClimbingDiscipline,
    CruxAngle,
    CruxEnergyType
)

class ClimbClassifier:
    """Handles classification of climbs into different types and categories"""
    
    def __init__(self):
        """Initialize classifier with style and characteristic mappings"""
        logger.info("Initializing ClimbClassifier")
        
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
        
        # Load crux characteristic keywords
        self.crux_angle_keywords = {
            CruxAngle.SLAB: ['slab', 'low angle', 'friction'],
            CruxAngle.VERTICAL: ['vertical', 'face', 'straight up'],
            CruxAngle.OVERHANG: ['overhang', 'steep', 'overhanging'],
            CruxAngle.ROOF: ['roof', 'horizontal', 'ceiling']
        }
        
        self.crux_energy_keywords = {
            CruxEnergyType.POWER: ['power', 'powerful', 'dynamic', 'explosive'],
            CruxEnergyType.POWER_ENDURANCE: ['power endurance', 'sustained', 'pumpy'],
            CruxEnergyType.ENDURANCE: ['endurance', 'stamina', 'continuous']
        }
        
        logger.debug("ClimbClassifier initialized with keyword mappings", extra={
            "lead_sends": self.lead_sends,
            "boulder_sends": self.boulder_sends,
            "length_bins": self.length_bins,
            "crux_types": {
                "angles": list(self.crux_angle_keywords.keys()),
                "energy_types": list(self.crux_energy_keywords.keys())
            }
        })
    
    def classify_discipline(self, df: pd.DataFrame) -> pd.Series:
        """Classify climbs into disciplines (sport, trad, boulder, etc.)"""
        logger.info("Starting discipline classification", extra={
            "total_rows": len(df),
            "null_route_types": df['route_type'].isna().sum()
        })
        
        def determine_discipline(row):
            # Handle missing route type
            if pd.isna(row['route_type']):
                logger.warning("Missing route type", extra={
                    "route_name": row.get('route_name', 'Unknown'),
                    "location": row.get('location', 'Unknown')
                })
                return None
                
            # Extract types
            types = [t.strip() for t in str(row['route_type']).split(',')]
            lead_style = str(row['lead_style']) if pd.notna(row['lead_style']) else ''
            notes = str(row['notes']) if pd.notna(row['notes']) else ''
            
            logger.debug("Processing route classification", extra={
                "route_name": row.get('route_name', 'Unknown'),
                "types": types,
                "lead_style": lead_style
            })
            
            # Check for explicit TR/Follow style first
            if any(fi in lead_style for fi in self.follow_indicators):
                return ClimbingDiscipline.TR
            
            # Check if it's a boulder based on grade range
            if (row['binned_code'] >= 100) and (row['binned_code'] < 200):
                return ClimbingDiscipline.BOULDER
            
            # Handle simple cases
            type_map = {
                'Sport': ClimbingDiscipline.SPORT,
                'Trad': ClimbingDiscipline.TRAD,
                'Boulder': ClimbingDiscipline.BOULDER,
                'TR': ClimbingDiscipline.TR,
                'Ice': ClimbingDiscipline.WINTER_ICE,
                'Mixed': ClimbingDiscipline.MIXED,
                'Aid': ClimbingDiscipline.AID
            }
            
            if len(types) == 1:
                return type_map.get(types[0], None)
            
            # Sport/TR combinations
            if ('Sport' in types and 'TR' in types):
                if any(ls in lead_style for ls in self.lead_indicators):
                    return ClimbingDiscipline.SPORT
                return ClimbingDiscipline.TR  # Default to TR if no lead indicators
            
            # Trad/TR combinations
            if ('Trad' in types and 'TR' in types):
                if any(ls in lead_style for ls in self.lead_indicators):
                    return ClimbingDiscipline.TRAD
                return ClimbingDiscipline.TR  # Default to TR if no lead indicators
            
            # Trad/Sport combinations
            if ('Trad' in types and 'Sport' in types) or ('Sport' in types and 'Trad' in types):
                # Look for explicit gear indicators
                if any(gi in notes.lower() for gi in self.gear_indicators):
                    return ClimbingDiscipline.TRAD
                    
                # Look for explicit sport indicators
                if any(si in notes.lower() for si in self.sport_indicators):
                    return ClimbingDiscipline.SPORT
                    
                # If no clear indicators, return None
                return None
            
            # Handle Alpine/Trad
            if 'Alpine' in types and 'Trad' in types:
                return ClimbingDiscipline.TRAD
            
            # Handle Ice/Mixed combinations
            if 'Ice' in types:
                return ClimbingDiscipline.WINTER_ICE
            if 'Mixed' in types:
                return ClimbingDiscipline.MIXED
            if 'Aid' in types:
                return ClimbingDiscipline.AID
            
            # Default cases based on primary type
            if 'Sport' in types:
                return ClimbingDiscipline.SPORT
            if 'Trad' in types:
                return ClimbingDiscipline.TRAD
            if 'Boulder' in types:
                return ClimbingDiscipline.BOULDER
            
            return None
        
        # Apply discipline classification
        disciplines = df.apply(determine_discipline, axis=1)
        
        # Log classification results
        discipline_counts = disciplines.value_counts()
        logger.info("Completed discipline classification", extra={
            "discipline_counts": discipline_counts.to_dict(),
            "null_disciplines": disciplines.isna().sum()
        })
        
        return disciplines
    
    def classify_sends(self, df: pd.DataFrame) -> pd.Series:
        """Determine if climbs were successfully sent"""
        logger.info("Starting send classification", extra={
            "total_rows": len(df),
            "disciplines_present": df['discipline'].unique().tolist()
        })
        
        # If send_bool already exists and is not None, respect it
        if 'send_bool' in df.columns and not df['send_bool'].isna().all():
            sends = df['send_bool']
        else:
            # For boulders:
            # - Style is Send/Flash -> True
            # - Style is Attempt -> False
            # - Style is None/empty -> check notes for send indicators
            is_boulder = df['discipline'] == ClimbingDiscipline.BOULDER
            is_roped = df['discipline'].isin([ClimbingDiscipline.SPORT, ClimbingDiscipline.TRAD])
            is_tr = df['discipline'] == ClimbingDiscipline.TR
            
            # Handle boulder sends/attempts - be more strict
            boulder_sends = is_boulder & (
                df['lead_style'].fillna('').str.lower().isin([s.lower() for s in self.boulder_sends]) |
                (df['lead_style'].isna() & df['notes'].fillna('').str.lower().str.contains('sent|topped|flash', na=False))
            )
            boulder_attempts = is_boulder & (
                df['lead_style'].fillna('').str.lower().isin(['attempt', 'working']) |
                df['notes'].fillna('').str.lower().str.contains('attempt|working|project', na=False)
            )
            
            # Handle roped climbs with stricter send classification
            roped_sends = is_roped & (
                # Direct match for lead sends (e.g. "Onsight")
                df['lead_style'].fillna('').str.lower().isin([s.lower() for s in self.lead_sends]) |
                # Lead style with no negative indicators
                (df['style'].fillna('').str.lower().str.contains('lead', na=False) & 
                 ~df['lead_style'].fillna('').str.lower().str.contains('fell|hung|attempt|working|project', na=False)) |
                # Empty lead style but positive notes
                (df['lead_style'].isna() & df['style'].fillna('').str.lower().str.contains('lead', na=False) &
                 df['notes'].fillna('').str.lower().str.contains('sent|redpoint|flash|onsight|clean', na=False) &
                 ~df['notes'].fillna('').str.lower().str.contains('fell|fall|hang|attempt|working|project|check|tried', na=False))
            )
            
            # Handle TR sends with stricter criteria
            send_keywords = {
                'sent', 'redpoint', 'flash', 'onsight'
            }
            attempt_keywords = {
                'attempt', 'working', 'project', 'fell', 'fall', 'hang'
            }
            tr_sends = is_tr & (
                (df['lead_style'].fillna('').str.lower().isin([s.lower() for s in ['Flash', 'Onsight', 'Clean']]) |
                 df['notes'].fillna('').str.lower().apply(
                    lambda x: any(keyword in x.split() for keyword in send_keywords)
                 )) &
                ~df['notes'].fillna('').str.lower().apply(
                    lambda x: any(keyword in x.split() for keyword in attempt_keywords)
                )
            )
            
            # Combine all conditions
            sends = (boulder_sends | roped_sends | tr_sends) & ~boulder_attempts
        
        # Enhanced logging for results
        send_stats = {
            str(disc): sends[df['discipline'] == disc].sum()
            for disc in df['discipline'].unique()
        }
        
        logger.info("Completed send classification", extra={
            "total_sends": sends.sum(),
            "sends_by_discipline": send_stats,
            "send_rate": f"{(sends.sum() / len(df)) * 100:.1f}%"
        })
        
        return sends.fillna(False)
    
    def classify_length(self, df: pd.DataFrame) -> pd.Series:
        """Classify routes by length"""
        logger.info("Starting length classification", extra={
            "total_rows": len(df),
            "missing_lengths": df['length'].isna().sum()
        })
        
        # First try to identify multipitch from notes
        is_multipitch = df['notes'].apply(self._is_multipitch_from_notes)
        multipitch_count = is_multipitch.sum()
        
        logger.debug("Identified multipitch routes", extra={
            "multipitch_count": multipitch_count,
            "multipitch_percentage": f"{(multipitch_count / len(df)) * 100:.1f}%"
        })
        
        # Create a mask for routes that should be marked as Unknown
        is_unknown = (df['length'] == 0) | df['length'].isna()
        
        # Then do standard length classification for routes with valid lengths
        length_categories = pd.Series('Unknown', index=df.index)  # Default to Unknown
        valid_lengths = ~is_unknown & ~is_multipitch
        if valid_lengths.any():
            length_categories[valid_lengths] = pd.cut(
                df.loc[valid_lengths, 'length'],
                bins=self.length_bins,
                labels=self.length_labels,
                right=False
            )
        
        # Override with multipitch if identified from notes
        length_categories = length_categories.mask(is_multipitch, 'multipitch')
        
        # Log length distribution
        length_dist = length_categories.value_counts()
        logger.info("Completed length classification", extra={
            "length_distribution": length_dist.to_dict(),
            "null_lengths": length_categories.isna().sum(),
            "unknown_count": (length_categories == 'Unknown').sum()
        })
        
        return length_categories
    
    def classify_season(self, df: pd.DataFrame) -> pd.Series:
        """Classify climbs by season"""
        logger.info("Starting season classification", extra={
            "total_rows": len(df),
            "date_range": {
                "start": df['tick_date'].min().strftime('%Y-%m-%d') if not df['tick_date'].empty else 'N/A',
                "end": df['tick_date'].max().strftime('%Y-%m-%d') if not df['tick_date'].empty else 'N/A'
            }
        })
        
        # Extract month and year first
        df = df.copy()
        
        # Validate tick_date column
        if 'tick_date' not in df.columns:
            logger.error("tick_date column missing from DataFrame")
            return pd.Series(index=df.index)
            
        # Convert tick_date to datetime safely
        try:
            dates = pd.to_datetime(df['tick_date'])
            df['tick_month'] = dates.dt.month
            df['tick_year'] = dates.dt.year
        except Exception as e:
            logger.error(f"Error converting tick_date to datetime: {str(e)}")
            return pd.Series(index=df.index)
        
        def season_mapping(row: pd.Series) -> str:
            try:
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
            except Exception as e:
                logger.error(f"Error in season_mapping: {str(e)}")
                return 'Unknown'
        
        # Apply season mapping
        seasons = df[['tick_month', 'tick_year']].apply(season_mapping, axis=1)
        
        # Log season distribution and years covered
        season_dist = seasons.value_counts()
        years_covered = df['tick_year'].nunique()
        
        logger.info("Completed season classification", extra={
            "season_distribution": season_dist.to_dict(),
            "years_covered": years_covered
        })
        
        return seasons
    
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
    
    def predict_crux_angle(self, notes: str) -> Optional[CruxAngle]:
        """Predict crux angle based on notes"""
        if pd.isna(notes):
            return None
            
        notes = notes.lower()
        for angle, keywords in self.crux_angle_keywords.items():
            if any(keyword in notes for keyword in keywords):
                logger.debug("Crux angle prediction", extra={
                    "predicted_angle": str(angle),
                    "matching_keywords": [k for k in keywords if k in notes]
                })
                return angle
        return None
    
    def predict_crux_energy(self, notes: str) -> Optional[CruxEnergyType]:
        """Predict crux energy type based on notes"""
        if pd.isna(notes):
            return None
            
        notes = notes.lower()
        for energy, keywords in self.crux_energy_keywords.items():
            if any(keyword in notes for keyword in keywords):
                logger.debug("Crux energy prediction", extra={
                    "predicted_energy": str(energy),
                    "matching_keywords": [k for k in keywords if k in notes]
                })
                return energy
        return None
