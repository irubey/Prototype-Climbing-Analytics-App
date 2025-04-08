"""
Service for recalculating derived fields and rebuilding performance pyramids.

This module provides functionality for:
- Recalculating derived fields (cur_max_*, categories)
- Rebuilding performance pyramids
- Preserving user-entered data
- Handling errors during recalculation
"""

from typing import Dict, List, Optional, Tuple
from uuid import UUID
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.models import UserTicks, PerformancePyramid, Tag
from app.models.enums import ClimbingDiscipline
from app.services.logbook.climb_classifier import ClimbClassifier
from app.services.logbook.pyramid_builder import PyramidBuilder

class RecalculationService:
    """Service for recalculating derived fields and rebuilding pyramids."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.classifier = ClimbClassifier()
        self.pyramid_builder = PyramidBuilder()

    async def _calculate_difficulty_category(self, df: pd.DataFrame) -> pd.Series:
        """Calculate difficulty category based on max grades"""
        def difficulty_bins(row):
            discipline = row['discipline']
            binned_code = row['binned_code']
            
            max_grade_cols = {
                'sport': 'cur_max_sport',
                'trad': 'cur_max_trad',
                'boulder': 'cur_max_boulder',
                'tr': 'cur_max_tr',
                'alpine': 'cur_max_alpine',
                'winter_ice': 'cur_max_winter_ice',
                'aid': 'cur_max_aid',
                'mixed': 'cur_max_mixed'
            }
            
            if discipline not in max_grade_cols:
                return 'Other'
                
            cur_max = row[max_grade_cols[discipline]]
            
            # Handle boulder vs route grade ranges
            if discipline == 'boulder':
                if binned_code < 101:  # If current tick is not a boulder grade
                    return 'Other'
                if cur_max < 101:  # If no previous boulder sends
                    return 'Project'
            else:  # Sport/Trad
                if binned_code >= 101 or cur_max >= 101:  # If either grade is a boulder grade
                    return 'Other'
            
            # Calculate relative difficulty and apply consistent categorization
            grade_diff = binned_code - cur_max
            
            if grade_diff > 0:
                return 'Project'
            elif grade_diff == 0:
                return 'Project'
            elif grade_diff == -1:
                return 'Tier 2'
            elif grade_diff == -2:
                return 'Tier 3'
            elif grade_diff == -3:
                return 'Tier 4'
            else:
                return 'Base Volume'
        
        return df.apply(difficulty_bins, axis=1)

    async def recalculate_fields_and_pyramids(
        self,
        user_id: UUID,
        created_ids: List[int] = None,
        updated_ids: List[int] = None,
        deleted_ids: List[int] = None
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Recalculate derived fields and rebuild pyramids for a user.
        
        Args:
            user_id: The user's UUID
            created_ids: List of newly created tick IDs
            updated_ids: List of updated tick IDs
            deleted_ids: List of deleted tick IDs
            
        Returns:
            Tuple of (success, errors)
        """
        try:
            # Fetch all ticks for the user
            result = await self.db.execute(
                select(UserTicks)
                .filter(UserTicks.user_id == user_id)
                .options(selectinload(UserTicks.performance_pyramid))
            )
            all_ticks = result.scalars().all()

            # Convert to DataFrame
            ticks_data = []
            for tick in all_ticks:
                tick_dict = {
                    "id": tick.id,
                    "route_name": tick.route_name,
                    "location": tick.location,
                    "discipline": tick.discipline,
                    "binned_code": tick.binned_code,
                    "tick_date": tick.tick_date,
                    "send_bool": tick.send_bool,
                    "notes": tick.notes,
                    "length_category": tick.length_category,
                    "pitches": tick.pitches,
                    "length": tick.length
                }
                ticks_data.append(tick_dict)
            
            df = pd.DataFrame(ticks_data)

            # Calculate max grades - sort by date first
            df = df.sort_values('tick_date')
            
            # Initialize max grade columns
            max_columns = {
                'cur_max_sport': 0,
                'cur_max_trad': 0,
                'cur_max_boulder': 0,
                'cur_max_tr': 0,
                'cur_max_alpine': 0,
                'cur_max_winter_ice': 0,
                'cur_max_aid': 0,
                'cur_max_mixed': 0
            }
            
            for col in max_columns:
                df[col] = 0
            
            # Initialize running max values
            max_values = {
                'sport': 0,
                'boulder': 0,
                'trad': 0,
                'tr': 0,
                'alpine': 0,
                'winter_ice': 0,
                'aid': 0,
                'mixed': 0
            }

            # Calculate running max values for each row
            for idx, row in df.iterrows():
                discipline = row['discipline']
                is_send = row['send_bool']
                grade_code = row['binned_code']
                
                # Update max values based on sends
                if is_send and discipline in max_values:
                    if discipline == 'boulder' and grade_code >= 101:
                        max_values['boulder'] = max(max_values['boulder'], grade_code)
                    elif discipline != 'boulder' and grade_code < 101:
                        max_values[discipline] = max(max_values[discipline], grade_code)
                
                # Set current max values for the row
                for disc, max_val in max_values.items():
                    df.at[idx, f'cur_max_{disc}'] = max_val

            # Calculate categories after cur_max values are set
            df['length_category'] = self.classifier.classify_length(df)
            df['season_category'] = self.classifier.classify_season(df)
            df['difficulty_category'] = await self._calculate_difficulty_category(df)

            # Update database with new calculated values
            for _, row in df.iterrows():
                await self.db.execute(
                    update(UserTicks)
                    .where(UserTicks.id == row['id'])
                    .values(
                        length_category=row['length_category'],
                        season_category=row['season_category'],
                        difficulty_category=row['difficulty_category'],
                        cur_max_sport=row['cur_max_sport'],
                        cur_max_trad=row['cur_max_trad'],
                        cur_max_boulder=row['cur_max_boulder'],
                        cur_max_tr=row['cur_max_tr'],
                        cur_max_alpine=row['cur_max_alpine'],
                        cur_max_winter_ice=row['cur_max_winter_ice'],
                        cur_max_aid=row['cur_max_aid'],
                        cur_max_mixed=row['cur_max_mixed']
                    )
                )

            # Build new pyramid entries only for sends
            sends_df = df[df['send_bool'] == True].copy()
            pyramid_entries = await self.pyramid_builder.build_performance_pyramid(sends_df, user_id)
            
            # Get existing pyramid entries
            existing_pyramid_entries = {
                pyramid.tick_id: pyramid
                for tick in all_ticks
                for pyramid in tick.performance_pyramid
            }
            to_keep_tick_ids = set()

            # Process each pyramid entry with explicit send verification
            for entry in pyramid_entries:
                tick_id = entry['tick_id']
                # Verify this tick is still a send
                tick_row = df[df['id'] == tick_id]
                if not tick_row.empty and tick_row['send_bool'].iloc[0]:
                    existing_entry = existing_pyramid_entries.get(tick_id)
                    if existing_entry:
                        # Preserve only if still a send
                        to_keep_tick_ids.add(tick_id)
                    else:
                        # Create new entry
                        new_entry = PerformancePyramid(
                            user_id=user_id,
                            tick_id=tick_id,
                            first_sent=entry['first_sent'],
                            crux_angle=entry['crux_angle'],
                            crux_energy=entry['crux_energy'],
                            num_attempts=entry['num_attempts'],
                            days_attempts=entry['days_attempts'],
                            num_sends=entry['num_sends'],
                            description=None,
                            agg_notes=entry['agg_notes']
                        )
                        self.db.add(new_entry)
                        to_keep_tick_ids.add(tick_id)

            # Delete entries not in new pyramid or no longer sends
            for tick_id, pyramid in existing_pyramid_entries.items():
                if tick_id not in to_keep_tick_ids:
                    await self.db.delete(pyramid)

            await self.db.commit()
            return True, None

        except Exception as e:
            logger.error(f"Error updating calculated fields and pyramids: {str(e)}")
            await self.db.rollback()
            return False, {"recalculation": str(e)} 