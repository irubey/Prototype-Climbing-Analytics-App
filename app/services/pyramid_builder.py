import pandas as pd
from typing import Tuple
from sqlalchemy import text

from app.models import SportPyramid, TradPyramid, BoulderPyramid, UserTicks
from app.services.grade_processor import GradeProcessor
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Explicitly set level

class PyramidBuilderError(Exception):
    """Custom exception for pyramid building errors"""
    pass

class PyramidBuilder:
    """Optimized pyramid builder with database optimizations and proper tick ID handling"""
    
    def __init__(self):
        self.crux_angle_cache = {}
        self.crux_energy_cache = {}
        self._load_grade_lists()
        self._load_keywords()

    def _load_grade_lists(self):
        self.grade_processor = GradeProcessor() 
        self.grade_lists = {
            'routes': self.grade_processor.get_grade_sorting_list('sport'),
            'boulders': self.grade_processor.get_grade_sorting_list('boulder')
        }

    def _load_keywords(self):
        """Style and characteristic keyword mappings"""
        self.crux_angle_keywords = {
            'Slab': ['slab', 'low angle'],
            'Vertical': ['vertical', 'vert'],
            'Overhang': ['overhang', 'steep'],
            'Roof': ['roof', 'ceiling']
        }
        self.crux_energy_keywords = {
            'Power': ['powerful', 'dynamic'],
            'Power Endurance': ['sustained', 'power endurance'],
            'Endurance': ['endurance', 'continuous'],
            'Technique': ['technical', 'beta']
        }

    def build_all_pyramids(self, df: pd.DataFrame, db_session=None) -> Tuple[pd.DataFrame]:
        """Build pyramids for all disciplines with transaction support"""
        try:
            # Pre-cache existing crux angles and crux energies
            if db_session:
                self._precache_existing_data(df, db_session)

            return (
                self._build_discipline_pyramid(df, 'sport', db_session),
                self._build_discipline_pyramid(df, 'trad', db_session),
                self._build_discipline_pyramid(df, 'boulder', db_session)
            )
        except Exception as e:
            logger.error(f"Pyramid build failed: {str(e)}")
            raise PyramidBuilderError from e

    def _precache_existing_data(self, df: pd.DataFrame, db_session):
        """Batch load existing crux angle and crux energy data for all routes"""
        routes = df[['route_name', 'location']].drop_duplicates()
        
        # Single query for all existing pyramid data
        existing_data = db_session.query(
            SportPyramid.route_name,
            SportPyramid.location,
            SportPyramid.crux_angle,
            SportPyramid.crux_energy,
            text("'sport' as discipline") 
        ).union_all(
            db_session.query(
                TradPyramid.route_name,
                TradPyramid.location,
                TradPyramid.crux_angle,
                TradPyramid.crux_energy,
                text("'trad' as discipline")
            )
        ).union_all(
            db_session.query(
                BoulderPyramid.route_name,
                BoulderPyramid.location,
                BoulderPyramid.crux_angle,
                BoulderPyramid.crux_energy,
                text("'boulder' as discipline")
            )
        ).all()

        # Cache results
        for route_name, location, crux_angle, crux_energy, discipline in existing_data:
            key = (route_name, location, discipline)
            self.crux_angle_cache.setdefault(key, crux_angle)
            self.crux_energy_cache.setdefault(key, crux_energy)

    def _build_discipline_pyramid(self, df: pd.DataFrame, discipline: str, db_session):
        """Core pyramid building logic for a single discipline"""
        # Filter and validate
        discipline_df = df[df['discipline'] == discipline].copy()
        if discipline_df.empty:
            return pd.DataFrame()

        # Process sends and attempts
        sends_df = self._process_sends(discipline_df, discipline)

        # Add metadata and predict crux attributes
        sends_df = self._add_pyramid_metadata(sends_df, discipline)
        sends_df = self._predict_crux_angle_crux_energy(sends_df)

        # Filter to top 4 binned codes (pyramid tiers)
        if not sends_df.empty:
            # Get top 4 unique binned codes (highest grades first)
            top_codes = sends_df['binned_code'].sort_values(
                ascending=False
            ).unique()[:4]
            sends_df = sends_df[sends_df['binned_code'].isin(top_codes)]

        # Validate after filtering
        self._validate_pyramid(sends_df)

        # Final cleanup
        logger.debug(f"Final pyramid columns before save: {sends_df.columns.tolist()}")
        logger.debug(f"Sample user_ids: {sends_df['user_id'].head(3).tolist()}")
        return self._finalize_pyramid(sends_df, discipline)

    REQUIRED_COLUMNS = [
        'id', 'user_id', 'route_name', 'location',
        'tick_date', 'route_grade', 'binned_code',
        'discipline', 'notes', 'send_bool'
    ]

    def _process_sends(self, df: pd.DataFrame, discipline: str) -> pd.DataFrame:
        """Process all sends and calculate num_sends/num_attempts"""
        missing = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise PyramidBuilderError(f"Missing required columns: {missing}")

        # Filter to successful sends only
        sends_df = df[df['send_bool']].copy()
        
        # Group by user_id + route/location
        grouped = sends_df.groupby(['user_id', 'route_name', 'location']).agg({
            'tick_date': ['min', 'count'],
            'route_grade': 'first',
            'binned_code': 'first',
            'discipline': 'first',
            'notes': 'first',
            'id': 'first'
        }).reset_index()

        # Flatten multi-index columns
        grouped.columns = [
            'user_id', 'route_name', 'location',
            'first_send_date', 'num_sends',
            'route_grade', 'binned_code', 
            'discipline', 'notes', 'tick_id'
        ]

        # Calculate attempts using pitches and lead style
        if 'pitches' not in df.columns:
            df['pitches'] = 1  # Default to 1 pitch if missing
        
        df['attempt_contribution'] = df.apply(
            lambda row: 1 if row['lead_style'] in ['Flash', 'Onsight'] 
            else row['pitches'] if row['length_category'] != 'multipitch' 
            else 1,
            axis=1
        )
        
        attempts = df.groupby(['user_id', 'route_name', 'location'])['attempt_contribution'].sum().reset_index(name='num_attempts')
        
        attempts['user_id'] = attempts['user_id'].astype(int)
        grouped['user_id'] = grouped['user_id'].astype(int)
        
        sends_df = pd.merge(
            grouped,
            attempts,
            on=['user_id', 'route_name', 'location'],
            how='left'
        )

        # Explicitly ensure user_id exists and is integer type
        if 'user_id' not in sends_df.columns:
            raise PyramidBuilderError("user_id missing after merge in _process_sends")
        sends_df['user_id'] = sends_df['user_id'].astype(int)

        # After grouping, check columns
        logger.debug(f"Grouped columns: {grouped.columns}")

        # After merge
        logger.debug(f"Merged columns: {sends_df.columns}")

        if 'id' not in sends_df.columns:
            raise PyramidBuilderError("Missing 'id' column in UserTicks data")

        return sends_df

    def _add_pyramid_metadata(self, df: pd.DataFrame, discipline: str):
        """Use GradeProcessor's sorting logic"""
        grade_type = 'routes' if discipline in ['sport', 'trad'] else 'boulders'
        sorted_grades = self.grade_processor.get_grade_sorting_list(discipline)
        
        df['sort_grade'] = pd.Categorical(
            df['route_grade'].str.split(' ').str[0],
            categories=sorted_grades,
            ordered=True
        )
        return df.sort_values(['binned_code', 'sort_grade'], ascending=[False, False])

    def _predict_crux_angle_crux_energy(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict missing crux angles and crux energies using cache and keywords"""
        df['crux_angle'] = df.apply(
            lambda r: self.crux_angle_cache.get((r['route_name'], r['location'], r['discipline'])) or
                      self._keyword_match(r['notes'], self.crux_angle_keywords),
            axis=1
        )
        
        df['crux_energy'] = df.apply(
            lambda r: self.crux_energy_cache.get((r['route_name'], r['location'], r['discipline'])) or
                      self._keyword_match(r['notes'], self.crux_energy_keywords),
            axis=1
        )
        
        return df

    def _keyword_match(self, notes: str, keyword_map: dict) -> str:
        """Match keywords in notes"""
        if pd.isna(notes):
            return None
        notes = notes.lower()
        for key, keywords in keyword_map.items():
            if any(k in notes for k in keywords):
                return key
        return None

    def _finalize_pyramid(self, df: pd.DataFrame, discipline: str) -> pd.DataFrame:
        """Final cleanup and validation"""
        # Should already have user_id from raw data processing
        if 'user_id' not in df.columns:
            raise PyramidBuilderError("Missing user_id in pyramid data")
        
        # Verify tick IDs exist before finalization
        missing_ticks = df[~df['tick_id'].isin(UserTicks.query.with_entities(UserTicks.id))]
        if not missing_ticks.empty:
            logger.error(f"Missing tick IDs: {missing_ticks['tick_id'].tolist()}")
            df = df[df['tick_id'].isin(UserTicks.query.with_entities(UserTicks.id))]
        
        logger.debug(f"First 3 tick IDs: {df['tick_id'].head(3).tolist()}")
        existing = UserTicks.query.filter(UserTicks.id.in_(df['tick_id'])).count()
        logger.info(f"Found {existing}/{len(df)} valid tick IDs")
        
        return df

    def _validate_pyramid(self, df: pd.DataFrame):
        """Data integrity checks for pyramid structure"""
        if not df.empty:
            if df['tick_id'].isnull().any():
                raise PyramidBuilderError("Missing tick IDs in pyramid data")
                
            # Check for max 4 tiers (binned codes)
            if df['binned_code'].nunique() > 4:
                raise PyramidBuilderError("Pyramid exceeds 4-tier limit")