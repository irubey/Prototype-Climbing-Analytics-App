from typing import Dict, Any, List, Optional
from app.models import (
    db, 
    UserTicks,
    PerformancePyramid,
    CruxEnergyType,
    CruxAngle,
    ClimbingDiscipline
)
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone
from app.services.grade_processor import GradeProcessor
from app.services.climb_classifier import ClimbClassifier
from uuid import UUID
import pandas as pd
import logging

class PyramidUpdateService:
    def __init__(self, db_session=None):
        self.grade_processor = GradeProcessor()
        self.classifier = ClimbClassifier()
        self.logger = logging.getLogger(__name__)
        self.db_session = db_session or db.session

    def process_changes(self, user_id: UUID, changes_data: Dict[str, Any]) -> bool:
        """Process changes to performance pyramid data."""
        self.logger.info(f"Starting to process changes for user {user_id}")
        self.logger.debug(f"Received changes_data: {changes_data}")

        if not changes_data or not user_id:
            self.logger.warning("No changes_data or user_id provided")
            return False

        try:
            # Process removals
            if removals := changes_data.get('removed'):
                self.logger.info(f"Processing {len(removals)} removals")
                self._remove_entries(user_id, removals)

            # Process updates
            for discipline in ['sport', 'trad', 'boulder']:
                if discipline_data := changes_data.get(discipline, {}):
                    if updates := discipline_data.get('updated', []):
                        self.logger.info(f"Processing {len(updates)} updates for {discipline}")
                        for update in updates:
                            self.logger.debug(f"Processing update for tick_id: {update.get('tick_id')}")
                            self._process_update(user_id, update)

            self.db_session.commit()
            self.logger.info("Successfully committed all changes to database")
            return True

        except SQLAlchemyError as e:
            self.logger.error(f"Database error while processing changes: {str(e)}", exc_info=True)
            self.db_session.rollback()
            raise e
        except Exception as e:
            self.logger.error(f"Unexpected error while processing changes: {str(e)}", exc_info=True)
            self.db_session.rollback()
            raise e

    def _process_update(self, user_id: UUID, update_data: Dict):
        """Process a single update entry."""
        try:
            tick_id = update_data.get('tick_id')
            self.logger.debug(f"Processing update for tick_id {tick_id}")

            # Update UserTicks
            user_tick = UserTicks.query.filter_by(
                user_id=user_id,
                id=tick_id
            ).first()

            if user_tick:
                self.logger.debug(f"Found existing UserTicks entry for tick_id {tick_id}")
                self._update_user_tick(user_tick, update_data)
                self.logger.debug(f"Successfully updated UserTicks for tick_id {tick_id}")
            else:
                self.logger.warning(f"No UserTicks entry found for tick_id {tick_id}")

            # Update PerformancePyramid
            perf_entry = PerformancePyramid.query.filter_by(
                user_id=user_id,
                tick_id=tick_id
            ).first()

            if perf_entry:
                self.logger.debug(f"Found existing PerformancePyramid entry for tick_id {tick_id}")
                self._update_entry(perf_entry, update_data)
                self.logger.debug(f"Successfully updated PerformancePyramid for tick_id {tick_id}")
            else:
                self.logger.warning(f"No PerformancePyramid entry found for tick_id {tick_id}")

        except Exception as e:
            self.logger.error(f"Error processing update for tick_id {tick_id}: {str(e)}", exc_info=True)
            raise

    def _remove_entries(self, user_id: UUID, tick_ids: List[int]):
        """Remove entries from performance pyramid and user ticks."""
        try:
            self.logger.info(f"Removing entries for tick_ids: {tick_ids}")
            
            # Remove from PerformancePyramid
            pyramid_result = PerformancePyramid.query.filter(
                PerformancePyramid.user_id == user_id,
                PerformancePyramid.tick_id.in_(tick_ids)
            ).delete(synchronize_session=False)
            
            self.logger.debug(f"Removed {pyramid_result} entries from PerformancePyramid")
            
            # Remove from UserTicks
            ticks_result = UserTicks.query.filter(
                UserTicks.user_id == user_id,
                UserTicks.id.in_(tick_ids)
            ).delete(synchronize_session=False)
            
            self.logger.debug(f"Removed {ticks_result} entries from UserTicks")

        except Exception as e:
            self.logger.error(f"Error removing entries: {str(e)}", exc_info=True)
            raise

    def _update_user_tick(self, user_tick: UserTicks, data: Dict):
        """Update an existing UserTicks entry."""
        try:
            self.logger.debug(f"Updating UserTicks entry {user_tick.id} with data: {data}")
            
            # Update grade-related fields
            if route_grade := data.get('route_grade'):
                user_tick.route_grade = route_grade
                discipline = user_tick.discipline.value if hasattr(user_tick.discipline, 'value') else user_tick.discipline
                binned_code = self.grade_processor.convert_grades_to_codes([route_grade], discipline=discipline)[0]
                user_tick.binned_code = binned_code
                user_tick.binned_grade = self.grade_processor.get_grade_from_code(binned_code)
                self.logger.debug(f"Updated grade fields: {route_grade} -> {user_tick.binned_grade}")

            # Update attempts and days
            if num_attempts := data.get('num_attempts'):
                user_tick.num_attempts = int(num_attempts)
            if days_tried := data.get('days_tried'):
                user_tick.days_tried = int(days_tried)

            # Update other fields
            if description := data.get('description'):
                user_tick.notes = description
            if location := data.get('location'):
                user_tick.location = location
                user_tick.location_raw = location

            self.logger.debug(f"Successfully updated UserTicks entry {user_tick.id}")

        except Exception as e:
            self.logger.error(f"Error updating UserTicks entry {user_tick.id}: {str(e)}", exc_info=True)
            raise

    def _update_entry(self, entry: PerformancePyramid, data: Dict):
        """Update an existing performance pyramid entry."""
        try:
            self.logger.debug(f"Updating PerformancePyramid entry {entry.tick_id} with data: {data}")
            
            # Update grade-related fields if provided
            if route_grade := data.get('route_grade'):
                discipline = data.get('discipline', 'sport')  # Default to sport if not specified
                binned_code = self.grade_processor.convert_grades_to_codes([route_grade], discipline=discipline)[0]
                entry.binned_code = binned_code
                entry.route_grade = route_grade
                self.logger.debug(f"Updated grade fields: {route_grade} -> {binned_code}")

            # Update attempts and days
            if num_attempts := data.get('num_attempts'):
                entry.num_attempts = int(num_attempts)
            if days_tried := data.get('days_tried'):
                entry.days_tried = int(days_tried)

            # Update other fields
            if description := data.get('description'):
                entry.description = description

            self.logger.debug(f"Successfully updated PerformancePyramid entry {entry.tick_id}")

        except Exception as e:
            self.logger.error(f"Error updating PerformancePyramid entry {entry.tick_id}: {str(e)}", exc_info=True)
            raise

    def _create_user_tick(self, user_id: UUID, data: Dict) -> UserTicks:
        """Create a new UserTicks entry."""
        # Grade processing
        route_grade = data.get('route_grade', '')
        discipline = data.get('discipline', 'sport')  # Default to sport if not specified
        binned_code = self.grade_processor.convert_grades_to_codes([route_grade], discipline=discipline)[0]
        binned_grade = self.grade_processor.get_grade_from_code(binned_code)
        
        # Get discipline from user input
        if not data.get('discipline'):
            raise ValueError("Discipline is required")
            
        try:
            discipline = ClimbingDiscipline(data['discipline'])
        except ValueError:
            raise ValueError(f"Invalid discipline value: {data.get('discipline')}")
        
        # Process date and get season
        try:
            send_date = datetime.strptime(data.get('send_date', ''), '%Y-%m-%d').date() if data.get('send_date') else datetime.now().date()
        except ValueError:
            send_date = datetime.now().date()

        # Use classifier for length categorization
        length = data.get('length')
        pitches = data.get('pitches', 1)
        df = pd.DataFrame([{
            'length': length,
            'pitches': pitches,
            'notes': data.get('description', '')
        }])
        length_category = self.classifier.classify_length(df).iloc[0]

        # Use classifier for season categorization
        df['tick_date'] = send_date
        season_category = self.classifier.classify_season(df).iloc[0].split(',')[0].lower()

        return UserTicks(
            user_id=user_id,
            route_name=data.get('route_name', 'Unknown Route'),
            route_grade=route_grade,
            binned_grade=binned_grade,
            binned_code=binned_code,
            length=length,
            pitches=pitches,
            location=data.get('location'),
            location_raw=data.get('location'),
            lead_style=data.get('lead_style'),
            discipline=discipline,
            send_bool=True,  # Performance pyramid entries are sends
            length_category=length_category,
            season_category=season_category,
            route_url=data.get('route_url'),
            route_stars=data.get('route_stars'),
            user_stars=data.get('user_stars'),
            tick_date=send_date,
            notes=data.get('description'),
            created_at=datetime.now(timezone.utc)
        )

    def _create_entry(self, user_id: UUID, data: Dict) -> PerformancePyramid:
        """Create a new performance pyramid entry."""
        # Convert grade to binned code
        route_grade = data.get('route_grade', '')
        discipline = data.get('discipline', 'sport')  # Default to sport if not specified
        binned_code = self.grade_processor.convert_grades_to_codes([route_grade], discipline=discipline)[0]

        # Convert enums
        try:
            crux_angle = CruxAngle(data.get('crux_angle')) if data.get('crux_angle') else None
        except ValueError:
            crux_angle = None

        try:
            crux_energy = CruxEnergyType(data.get('crux_energy')) if data.get('crux_energy') else None
        except ValueError:
            crux_energy = None

        # Parse date
        try:
            send_date = datetime.strptime(data.get('send_date', ''), '%Y-%m-%d').date() if data.get('send_date') else datetime.now().date()
        except ValueError:
            send_date = datetime.now().date()

        # Handle numeric fields with proper validation
        try:
            length = int(data.get('length')) if data.get('length') is not None else None
        except (ValueError, TypeError):
            length = None

        try:
            num_attempts = max(1, int(data.get('num_attempts', 1)))
        except (ValueError, TypeError):
            num_attempts = 1

        try:
            days_tried = max(1, int(data.get('days_tried', 1)))
        except (ValueError, TypeError):
            days_tried = 1

        # Create new entry using the tick_id from UserTicks
        return PerformancePyramid(
            user_id=user_id,
            tick_id=data['tick_id'],  # This will be set from the UserTicks id
            route_name=data.get('route_name', 'Unknown Route'),
            route_grade=route_grade,
            binned_code=binned_code,
            send_date=send_date,
            location=data.get('location'),
            crux_angle=crux_angle,
            crux_energy=crux_energy,
            num_attempts=num_attempts,
            days_tried=days_tried,
            length=length,
            description=data.get('description')
        )