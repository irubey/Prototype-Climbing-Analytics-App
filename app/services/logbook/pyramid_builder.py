"""
Performance pyramid analysis service.

This module provides functionality for:
- Building performance pyramids from tick data
- Analyzing climbing progression
- Predicting crux characteristics
- Calculating attempt metrics
"""

from typing import Dict, List, Optional, Tuple
from uuid import UUID
import traceback
import pandas as pd

from app.core.logging import logger
from app.core.exceptions import DataSourceError
from app.models.enums import (
    ClimbingDiscipline,
    CruxAngle,
    CruxEnergyType,
)

from app.services.utils.grade_service import GradeService

class PyramidBuilder:
    """Builds performance pyramids from user ticks data"""
    
    def __init__(self):
        logger.info("Initializing PyramidBuilder")
        self.grade_service = GradeService.get_instance()
        self._load_keywords()

    def _load_keywords(self):
        """Load style and characteristic keyword mappings"""
        logger.debug("Loading style and characteristic keywords")
        
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

    async def build_performance_pyramid(
        self,
        df: pd.DataFrame,
        user_id: UUID
    ) -> List[Dict]:
        """
        Build performance pyramid from processed tick data
        
        Args:
            df: DataFrame containing processed tick data
            user_id: UUID of the user
            
        Returns:
            List of dictionaries containing pyramid data
        """
        logger.info(f"Building performance pyramid for user {user_id}")
        
        try:
            if df.empty:
                logger.debug("No ticks found for user")
                return []
            
            # Get successful sends only
            sends_df = df[df['send_bool']].copy()
            if sends_df.empty:
                logger.debug("No successful sends found")
                return []
            
            # Debug discipline distribution
            discipline_counts = sends_df['discipline'].value_counts()
            logger.debug(
                "Discipline distribution in sends",
                extra={"counts": discipline_counts.to_dict()}
            )
            
            results = []
            # Process each discipline separately
            for discipline in ClimbingDiscipline:
                discipline_sends = sends_df[sends_df['discipline'] == discipline]
                
                if discipline_sends.empty:
                    logger.debug(f"No {discipline.value} sends found")
                    continue
                
                # Get top 4 grades for this discipline
                top_grades = discipline_sends['binned_code'].sort_values(ascending=False).unique()[:4]
                top_sends = discipline_sends[discipline_sends['binned_code'].isin(top_grades)]
                
                logger.debug(
                    f"Processing top sends for {discipline.value}",
                    extra={"count": len(top_sends)}
                )
                
                # Process each send
                for _, send in top_sends.iterrows():
                    # Get all attempts for this route before the send date
                    route_attempts = df[
                        (df['route_name'] == send['route_name']) & 
                        (df['location_raw'] == send['location_raw']) &
                        (df['tick_date'] <= send['tick_date'])
                    ]
                    
                    # Calculate attempts based on style and route type
                    num_attempts = await self._calculate_attempts(
                        route_attempts,
                        send['lead_style'],
                        send['length_category']
                    )
                    
                    # Calculate days spent attempting
                    days_attempts = route_attempts['tick_date'].nunique()
                    
                    # Predict crux characteristics
                    crux_angle = await self._predict_crux_angle(send['notes'])
                    crux_energy = await self._predict_crux_energy(send['notes'])
                    
                    pyramid_entry = {
                        'user_id': user_id,
                        'tick_id': send.name,  # DataFrame index as tick_id
                        'send_date': send['tick_date'],
                        'location': send['location'],
                        'crux_angle': crux_angle,
                        'crux_energy': crux_energy,
                        'binned_code': send['binned_code'],
                        'num_attempts': num_attempts,
                        'days_attempts': days_attempts,
                        'num_sends': len(route_attempts[route_attempts['send_bool']]),
                    }
                    
                    results.append(pyramid_entry)
            
            if not results:
                logger.debug("No performance pyramid entries generated")
                return []
            
            logger.info(
                "Successfully built performance pyramid",
                extra={"entry_count": len(results)}
            )
            return results
            
        except Exception as e:
            logger.error(f"Error building performance pyramid: {str(e)}")
            raise DataSourceError(f"Error building performance pyramid: {str(e)}")

    async def _calculate_attempts(
        self,
        attempts_df: pd.DataFrame,
        lead_style: str,
        length_category: str
    ) -> int:
        """Calculate number of attempts based on style and route type"""
        try:
            logger.debug("Calculating attempts", extra={
                "lead_style": lead_style,
                "length_category": length_category,
                "total_entries": len(attempts_df)
            })
            
            if lead_style and lead_style.lower() in ['onsight', 'flash']:
                logger.debug("Single attempt style detected", extra={
                    "style": lead_style
                })
                return 1
                
            if length_category == 'multipitch':
                attempts = len(attempts_df)
                logger.debug("Multipitch attempts calculated", extra={
                    "attempts": attempts
                })
                return attempts
                
            attempts = attempts_df['pitches'].sum() or 1
            logger.debug("Standard attempts calculated", extra={
                "attempts": attempts,
                "total_pitches": attempts_df['pitches'].sum()
            })
            return attempts
            
        except Exception as e:
            logger.error("Error calculating attempts", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            return 1

    async def _predict_crux_angle(self, notes: str) -> Optional[CruxAngle]:
        """Predict crux angle from notes"""
        if pd.isna(notes):
            return None
            
        notes = notes.lower()
        for angle, keywords in self.crux_angle_keywords.items():
            if any(k in notes for k in keywords):
                logger.debug("Crux angle predicted", extra={
                    "angle": str(angle),
                    "matching_keywords": [k for k in keywords if k in notes]
                })
                return angle
                
        logger.debug("No crux angle found in notes")
        return None

    async def _predict_crux_energy(self, notes: str) -> Optional[CruxEnergyType]:
        """Predict crux energy type from notes"""
        if pd.isna(notes):
            return None
            
        notes = notes.lower()
        for energy, keywords in self.crux_energy_keywords.items():
            if any(k in notes for k in keywords):
                logger.debug("Crux energy type predicted", extra={
                    "energy_type": str(energy),
                    "matching_keywords": [k for k in keywords if k in notes]
                })
                return energy
                
        logger.debug("No crux energy type found in notes")
        return None
