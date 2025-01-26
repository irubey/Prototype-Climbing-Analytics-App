from typing import Dict, Any, List
from app.models import (
    db, 
    SportPyramid, 
    TradPyramid, 
    BoulderPyramid, 
    UserTicks,
    CruxEnergyType,
    CruxAngle
)
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from app.services.grade_processor import GradeProcessor
from app.services.climb_classifier import ClimbClassifier
import pandas as pd
import time

class PyramidUpdateService:
    def __init__(self):
        self.grade_processor = GradeProcessor()
        self.classifier = ClimbClassifier()

    def process_changes(self, userId: int = None, changes_data: Dict[str, Any] = None) -> bool:
        """Process changes to pyramid data including new fields."""
        if not changes_data or not userId:
            return False

        try:
            for discipline, changes in changes_data.items():
                model_class = self._get_model(discipline)
                if not model_class:
                    continue

                # Get valid grade range for this discipline
                existing_entries = model_class.query.filter_by(userId=userId).all()
                valid_codes = [e.binned_code for e in existing_entries] if existing_entries else []
                min_code = min(valid_codes) if valid_codes else 0
                max_code = max(valid_codes) if valid_codes else 0

                # Process removals
                if changes.get('removed'):
                    valid_ids = [tid for tid in changes['removed'] if tid and tid != 'None']
                    if valid_ids:
                        self._remove_routes(discipline, userId, valid_ids)

                # Process updates and additions
                for route_id, updates in changes.get('updated', {}).items():
                    if not route_id or route_id in ['attempts', 'characteristic', 'style']:
                        continue

                    if str(route_id).startswith('8'):  # New route
                        self._handle_new_route(userId, model_class, discipline, route_id, updates)
                    else:  # Existing route
                        self._handle_existing_route(userId, model_class, discipline, route_id, updates, min_code, max_code)

            db.session.commit()
            db.session.expire_all()
            return True

        except SQLAlchemyError as e:
            db.session.rollback()
            raise e

    def _handle_new_route(self, userId: int, model_class, discipline: str, route_id: str, updates: Dict):
        """Handle creation of new pyramid entries."""
        try:
            updates.update({
                'userId': userId,
                'discipline': discipline,
                'tick_date': updates.get('tick_date', datetime.now().date()),
                'tick_id': int(route_id)
            })
            
            # Get username from existing ticks if missing
            if 'username' not in updates:
                user_tick = UserTicks.query.filter_by(userId=userId).first()
                updates['username'] = user_tick.username if user_tick else "Unknown"

            new_entry = self._create_pyramid_entry(model_class, updates)
            db.session.add(new_entry)

        except Exception as e:
            raise ValueError(f"Error creating new route: {str(e)}")

    def _handle_existing_route(self, userId: int, model_class, discipline: str, 
                             route_id: str, updates: Dict, min_code: int, max_code: int):
        """Handle updates to existing pyramid entries."""
        entry = model_class.query.filter_by(userId=userId, tick_id=route_id).first()
        if not entry:
            return

        # Update grade-related fields
        if 'route_grade' in updates:
            new_grade = updates['route_grade']
            new_code = self.grade_processor.convert_grades_to_codes([new_grade])[0]
            
            # Validate grade range
            if min_code <= new_code <= max_code and abs(new_code - entry.binned_code) <= 3:
                entry.binned_code = new_code
                entry.binned_grade = self.grade_processor.get_grade_from_code(new_code)
                entry.route_grade = new_grade

        # Update other fields
        for field, value in updates.items():
            if not hasattr(entry, field) or field in ['binned_code', 'binned_grade']:
                continue

            # Handle Enum conversions
            if field == 'crux_energy':
                try: value = CruxEnergyType(value)
                except ValueError: continue
            elif field == 'crux_angle':
                try: value = CruxAngle(value)
                except ValueError: continue

            # Convert numeric fields
            if field in ['num_attempts', 'num_sends']:
                try: value = int(value)
                except ValueError: continue

            setattr(entry, field, value)

        # Ensure required fields
        entry.discipline = discipline
        entry.tick_date = entry.tick_date or datetime.now().date()

    def _create_pyramid_entry(self, model_class, data: Dict) -> Any:
        """Create a new pyramid entry with full field support."""
        # Convert Enums
        crux_energy = self._safe_enum_conversion(data.get('crux_energy'), CruxEnergyType)
        crux_angle = self._safe_enum_conversion(data.get('crux_angle'), CruxAngle)

        # Convert dates
        tick_date = self._parse_date(data.get('tick_date'))

        # Calculate derived fields
        binned_code = self.grade_processor.get_code_from_grade(data.get('route_grade', ''))
        season_category = self._get_season_category(tick_date)
        lead_style = self._determine_lead_style(data.get('discipline'), data.get('num_attempts', 1))

        return model_class(
            userId=data['userId'],
            username=data.get('username', 'Unknown'),
            route_name=data.get('route_name', 'Unknown Route'),
            route_grade=data.get('route_grade', 'Unknown Grade'),
            binned_code=binned_code,
            binned_grade=self.grade_processor.get_grade_from_code(binned_code),
            tick_date=tick_date,
            crux_energy=crux_energy,
            crux_angle=crux_angle,
            num_attempts=int(data.get('num_attempts', 1)),
            num_sends=int(data.get('num_sends', 1)),
            discipline=data.get('discipline', ''),
            tick_id=data.get('tick_id', int(time.time())),
            location=data.get('location', 'User Added'),
            lead_style=lead_style,
            season_category=season_category,
            length_category=self._get_length_category(data.get('length')),
            pitches=int(data.get('pitches', 1)),
            route_url=data.get('route_url'),
            user_grade=data.get('user_grade')
        )

    def _safe_enum_conversion(self, value, enum_type):
        """Safely convert string values to Enum instances."""
        try:
            return enum_type(value) if value else None
        except ValueError:
            return None

    def _parse_date(self, date_input):
        """Parse date from various input formats."""
        if isinstance(date_input, datetime):
            return date_input.date()
        if isinstance(date_input, str):
            try:
                return datetime.strptime(date_input, '%Y-%m-%d').date()
            except ValueError:
                pass
        return datetime.now().date()

    def _get_season_category(self, date_obj):
        """Classify the season based on date."""
        date_df = pd.DataFrame({'tick_date': [date_obj]})
        return self.classifier.classify_season(date_df).iloc[0]

    def _determine_lead_style(self, discipline: str, attempts: int) -> str:
        """Determine lead style based on discipline and attempt count."""
        if discipline in ['sport', 'trad']:
            return 'Redpoint' if attempts > 1 else 'Flash'
        return 'Send' if attempts > 1 else 'Flash'

    @staticmethod
    def _remove_routes(discipline: str, userId: int, tick_ids: List):
        """Remove routes from specified discipline."""
        model_class = PyramidUpdateService._get_model(discipline)
        if not model_class:
            return

        model_class.query.filter(
            model_class.userId == userId,
            model_class.tick_id.in_(tick_ids)
        ).delete(synchronize_session=False)

    @staticmethod
    def _get_model(discipline: str):
        """Get model class for specified discipline."""
        return {
            'sport': SportPyramid,
            'trad': TradPyramid,
            'boulder': BoulderPyramid
        }.get(discipline)

    def _get_length_category(self, length: int) -> str:
        """Classify route length (example implementation)."""
        if not length:
            return None
        if length <= 15:
            return 'Short'
        if length <= 30:
            return 'Medium'
        return 'Long'
    
    @staticmethod
    def _remove_routes(discipline: str, userId: int, tick_ids: List):
        model_class = PyramidUpdateService._get_model(discipline)
        if model_class:
            model_class.query.filter(
                model_class.userId == userId,
                model_class.tick_id.in_(tick_ids)
            ).delete(synchronize_session=False)

    @staticmethod
    def _get_model(discipline: str):
        return {
            'sport': SportPyramid,
            'trad': TradPyramid,
            'boulder': BoulderPyramid
        }.get(discipline)