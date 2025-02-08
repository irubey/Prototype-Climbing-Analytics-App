import pandas as pd
from typing import Optional
from uuid import UUID
from app.models import UserTicks, ClimbingDiscipline
from app.services.grade_processor import GradeProcessor
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class PyramidBuilderError(Exception):
    """Custom exception for pyramid building errors"""
    def __init__(self, message):
        self.message = message
        logger.error(f"PyramidBuilderError: {message}")
        super().__init__(self.message)

class PyramidBuilder:
    """Builds performance pyramids from user ticks data"""
    
    def __init__(self):
        logger.info("Initializing PyramidBuilder")
        self._load_grade_lists()
        self._load_keywords()

    def _load_grade_lists(self):
        logger.debug("Loading grade lists")
        self.grade_processor = GradeProcessor()

    def _load_keywords(self):
        """Style and characteristic keyword mappings"""
        logger.debug("Loading style and characteristic keywords")
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
        }
        
        # Map string disciplines to enum values
        self.discipline_map = {
            'sport': ClimbingDiscipline.sport,
            'trad': ClimbingDiscipline.trad,
            'boulder': ClimbingDiscipline.boulder,
            'tr': ClimbingDiscipline.tr,
            'winter_ice': ClimbingDiscipline.winter_ice,
            'mixed': ClimbingDiscipline.mixed,
            'aid': ClimbingDiscipline.aid
        }

    def build_performance_pyramid(self, user_id: UUID, db_session) -> pd.DataFrame:
        """Build performance pyramid for a user directly from UserTicks"""
        logger.info(f"Building performance pyramid for user {user_id}")
        
        try:
            # Query all user ticks
            logger.debug("Querying user ticks")
            user_ticks_query = db_session.query(UserTicks).filter(
                UserTicks.user_id == user_id
            ).order_by(UserTicks.tick_date.desc())
            
            # Convert to DataFrame for processing
            df = pd.read_sql(user_ticks_query.statement, db_session.connection())
            
            if df.empty:
                logger.debug("No ticks found for user")
                return pd.DataFrame()
            
            # Debug send_bool distribution
            send_bool_counts = df['send_bool'].value_counts()
            logger.debug(f"Send bool distribution: {send_bool_counts.to_dict()}")
            
            # Get successful sends only
            sends_df = df[df['send_bool']].copy()
            if sends_df.empty:
                logger.debug("No successful sends found")
                return pd.DataFrame()
            
            # Debug discipline distribution
            discipline_counts = sends_df['discipline'].value_counts()
            logger.debug(f"Discipline distribution in sends: {discipline_counts.to_dict()}")
            
            # Debug unique disciplines
            unique_disciplines = sends_df['discipline'].unique()
            logger.debug(f"Unique disciplines found: {unique_disciplines}")
            
            # Rename tick_date to send_date for processing
            df = df.rename(columns={'tick_date': 'send_date'})
            sends_df = sends_df.rename(columns={'tick_date': 'send_date'})
            
            results = []
            # Process each discipline separately
            for discipline_str in ['sport', 'trad', 'boulder', 'tr', 'winter_ice', 'mixed', 'aid']:
                # Get enum value for comparison
                discipline_enum = self.discipline_map[discipline_str]
                discipline_sends = sends_df[sends_df['discipline'] == discipline_enum]
                
                if discipline_sends.empty:
                    logger.debug(f"No {discipline_str} sends found")
                    continue
                    
                # Get top 4 grades for this discipline
                top_grades = discipline_sends['binned_code'].sort_values(ascending=False).unique()[:4]
                top_sends = discipline_sends[discipline_sends['binned_code'].isin(top_grades)]
                
                logger.debug(f"Processing {len(top_sends)} top sends for {discipline_str}")
                
                # Process each send
                for _, send in top_sends.iterrows():
                    # Get all attempts for this route before the send date
                    route_attempts = df[
                        (df['route_name'] == send['route_name']) & 
                        (df['location_raw'] == send['location_raw']) &
                        (df['send_date'] <= send['send_date'])
                    ]
                    
                    # Calculate num_attempts
                    if send['lead_style'] == 'onsight' or send['lead_style'] == 'flash':
                        num_attempts = 1
                    elif send['length_category'] != 'multipitch':
                        num_attempts = route_attempts['pitches'].sum() or 1
                    else:
                        num_attempts = len(route_attempts)
                    
                    # Calculate days_attempts
                    days_attempts = route_attempts['send_date'].nunique()
                    
                    # Predict crux characteristics
                    crux_angle = self._predict_crux_angle(send['notes'])
                    crux_energy = self._predict_crux_energy(send['notes'])
                    
                    results.append({
                        'user_id': send['user_id'],
                        'tick_id': send['id'],
                        'send_date': send['send_date'],
                        'location': send['location'],
                        'crux_angle': crux_angle,
                        'crux_energy': crux_energy,
                        'binned_code': send['binned_code'],
                        'num_attempts': num_attempts,
                        'days_attempts': days_attempts,
                        'description': None,  # Will be filled by user
                        'discipline': discipline_enum  # Use enum value
                    })
            
            if not results:
                logger.debug("No performance pyramid entries generated")
                return pd.DataFrame()
            
            result_df = pd.DataFrame(results)
            logger.info(f"Successfully built performance pyramid with {len(result_df)} entries "
                       f"across {result_df['discipline'].nunique()} disciplines")
            return result_df
            
        except Exception as e:
            logger.error(f"Error building performance pyramid: {str(e)}", exc_info=True)
            raise PyramidBuilderError(f"Error building performance pyramid: {str(e)}")

    def _predict_crux_angle(self, notes: str) -> Optional[str]:
        """Predict crux angle from notes"""
        if pd.isna(notes):
            return None
        notes = notes.lower()
        for angle, keywords in self.crux_angle_keywords.items():
            if any(k in notes for k in keywords):
                return angle
        return None

    def _predict_crux_energy(self, notes: str) -> Optional[str]:
        """Predict crux energy type from notes"""
        if pd.isna(notes):
            return None
        notes = notes.lower()
        for energy, keywords in self.crux_energy_keywords.items():
            if any(k in notes for k in keywords):
                return energy
        return None