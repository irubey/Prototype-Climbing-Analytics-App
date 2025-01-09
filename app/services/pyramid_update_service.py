from typing import Dict, Any, List
from app.models import db, SportPyramid, TradPyramid, BoulderPyramid, UserTicks
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from app.services.grade_processor import GradeProcessor

import time
import pandas as pd
from app.services.climb_classifier import ClimbClassifier

class PyramidUpdateService:
    def __init__(self):
        self.grade_processor = GradeProcessor()
        self.classifier = ClimbClassifier()

    def process_changes(self, username: str, changes_data: Dict[str, Any]) -> bool:
        """Process changes to pyramid data."""
        try:
            for discipline, changes in changes_data.items():
                model_class = {
                    'sport': SportPyramid,
                    'trad': TradPyramid,
                    'boulder': BoulderPyramid
                }.get(discipline)

                if not model_class:
                    continue

                # Get the valid grade range for this discipline's pyramid
                existing_entries = model_class.query.filter_by(username=username).all()
                if existing_entries:
                    valid_codes = [entry.binned_code for entry in existing_entries]
                    min_valid_code = min(valid_codes)
                    max_valid_code = max(valid_codes)
                else:
                    continue

                # Process removals
                if changes.get('removed'):
                    valid_ids = []
                    for tid in changes['removed']:
                        try:
                            if tid and tid != 'None':
                                valid_ids.append(tid)
                        except (ValueError, TypeError):
                            continue
                    
                    if valid_ids:
                        PyramidUpdateService._remove_routes(discipline, username, valid_ids)

                # Process updates and additions
                for route_id, updates in changes.get('updated', {}).items():
                    # Skip any route_id that's not a valid identifier
                    if not route_id or route_id in ['attempts', 'characteristic', 'style']:
                        continue

                    # Check if the route's grade is within the valid range
                    if 'route_grade' in updates:
                        binned_code = self.grade_processor.convert_grades_to_codes([updates['route_grade']])[0]
                        if binned_code < min_valid_code or binned_code > max_valid_code:
                            continue
                        
                    if str(route_id).startswith('8'):  # New routes
                        updates['username'] = username
                        updates['discipline'] = discipline
                        updates['tick_date'] = updates.get('tick_date', datetime.now().date())
                        updates['tick_id'] = int(route_id)
                        
                        self._add_new_route(
                            username=username,
                            model_class=model_class,
                            route_data=updates,
                            new_id=route_id
                        )
                    else:
                        try:
                            # Update existing route
                            pyramid_entry = model_class.query.filter_by(
                                username=username,
                                tick_id=route_id
                            ).first()
                            
                            if pyramid_entry:
                                # Debug logging for num_attempts updates
                                if 'num_attempts' in updates:
                                    print(f"Updating num_attempts for {route_id}: {updates['num_attempts']} (type: {type(updates['num_attempts'])})")
                                
                                # Update basic fields
                                for field, value in updates.items():
                                    if hasattr(pyramid_entry, field) and field not in ['binned_grade', 'binned_code']:
                                        if field == 'num_attempts':
                                            value = int(value)  # Ensure num_attempts is an integer
                                        setattr(pyramid_entry, field, value)
                                        print(f"Updated {field} to {value} for route {route_id}")
                                
                                # Update binned grade and code if grade is changed
                                if 'route_grade' in updates:
                                    grade_processor = GradeProcessor()
                                    grade = updates['route_grade']
                                    new_binned_code = grade_processor.convert_grades_to_codes([grade])[0]
                                    
                                    # Check for suspicious grade changes (more than 3 grades different)
                                    if abs(new_binned_code - pyramid_entry.binned_code) > 3:
                                        continue
                                        
                                    binned_grade = grade_processor.get_grade_from_code(new_binned_code)
                                    pyramid_entry.binned_grade = binned_grade
                                    pyramid_entry.binned_code = new_binned_code
                                
                                # Ensure critical fields are set
                                if not pyramid_entry.username:
                                    pyramid_entry.username = username
                                if not pyramid_entry.discipline:
                                    pyramid_entry.discipline = discipline
                                if not pyramid_entry.tick_date:
                                    pyramid_entry.tick_date = datetime.now().date()

                        except (ValueError, TypeError):
                            continue

            db.session.commit()
            db.session.expire_all()  # Ensure fresh data on subsequent queries
            return True

        except SQLAlchemyError as e:
            db.session.rollback()
            raise e

    @staticmethod
    def _remove_routes(discipline, username, tick_ids):
        if not tick_ids:  # Don't attempt deletion if no valid IDs
            return
            
        model = PyramidUpdateService._get_model(discipline)
        model.query.filter(
            model.username == username,
            model.tick_id.in_(tick_ids)
        ).delete(synchronize_session=False)

    @staticmethod
    def _update_routes(discipline, username, updates):
        model = PyramidUpdateService._get_model(discipline)
        for route_id, data in updates.items():
            if not route_id.startswith('new_'):  # Only update existing routes
                try:
                    route = model.query.filter_by(
                        username=username,
                        id=int(route_id)
                    ).first()
                    
                    if route:
                        for field, value in data.items():
                            if hasattr(route, field):
                                setattr(route, field, value)
                except (ValueError, TypeError):
                    continue

    @staticmethod
    def _add_routes(discipline, username, added_ids, updates):
        model = PyramidUpdateService._get_model(discipline)
        for route_id in added_ids:
            if route_id.startswith('new_'):
                data = updates.get(route_id, {})
                if data:
                    try:
                        new_route = model(
                            username=username,
                            route_name=data.get('route_name'),
                            route_grade=data.get('route_grade'),
                            num_attempts=int(data.get('num_attempts', 1)),
                            route_characteristic=data.get('route_characteristic'),
                            route_style=data.get('route_style'),
                            tick_id=None  # New routes don't have a tick_id
                        )
                        db.session.add(new_route)
                    except (ValueError, TypeError):
                        continue

    @staticmethod
    def _get_model(discipline):
        if discipline == 'sport':
            return SportPyramid
        elif discipline == 'trad':
            return TradPyramid
        elif discipline == 'boulder':
            return BoulderPyramid
        else:
            raise ValueError(f"Unknown discipline: {discipline}")

    def _validate_and_bin_grade(self, grade: str, discipline: str) -> tuple[str, int]:
        """Validate grade and return binned grade and code"""
        # Get valid grades for discipline
        valid_grades = set()
        for grades in self.grade_processor.binned_code_dict.values():
            valid_grades.update(grades)

        # Clean grade input
        grade = grade.split(' ')[0] if grade else ''
        
        if grade not in valid_grades:
            raise ValueError(f"Invalid grade: {grade}")
            
        # Get binned code
        binned_code = self.grade_processor.convert_grades_to_codes([grade])[0]
        
        return grade, binned_code

    def _add_new_route(self, username: str, model_class: Any, route_data: Dict[str, Any], new_id: str) -> None:
        """Add a new route to the pyramid"""
        try:
            # Handle tick_date - if it's a string, parse it, otherwise use it as is
            if 'tick_date' in route_data:
                if isinstance(route_data['tick_date'], str):
                    try:
                        route_data['tick_date'] = datetime.strptime(
                            route_data['tick_date'], 
                            '%Y-%m-%d'
                        ).date()
                    except ValueError:
                        route_data['tick_date'] = datetime.now().date()
            else:
                route_data['tick_date'] = datetime.now().date()

            # Use user-provided values directly - no prediction
            num_attempts = int(route_data.get('num_attempts', 1))
            discipline = route_data.get('discipline', '')
            
            # Set lead_style based on discipline and attempts
            if discipline in ['sport', 'trad']:
                lead_style = 'Redpoint' if num_attempts > 1 else 'Flash'
            else:  # boulder
                lead_style = 'Send' if num_attempts > 1 else 'Flash'

            # Calculate binned_code from route_grade
            route_grade = route_data.get('route_grade', 'Unknown Grade')
            binned_code = self.grade_processor.get_code_from_grade(route_grade)

            # Get season category
            date_df = pd.DataFrame({
                'tick_date': [route_data['tick_date']]
            })
            season_category = self.classifier.classify_season(date_df).iloc[0]

            # Create new pyramid entry with user-provided data
            new_entry = model_class(
                username=username,
                route_name=route_data.get('route_name', 'Unknown Route'),
                route_grade=route_grade,
                tick_date=route_data['tick_date'],
                num_attempts=num_attempts,
                route_characteristic=route_data.get('route_characteristic'),  # Use as provided
                route_style=route_data.get('route_style'),  # Use as provided
                tick_id=route_data.get('tick_id', int(datetime.now().timestamp())),
                binned_grade=self.grade_processor.get_grade_from_code(binned_code),
                binned_code=binned_code,
                length=None,
                pitches=num_attempts,
                location=route_data.get('location', 'User Added'),
                lead_style=lead_style,
                discipline=discipline,
                length_category=None,
                season_category=season_category,
                route_url=None,
                user_grade=route_data.get('route_grade', 'Unknown Grade')
            )

            db.session.add(new_entry)
        except Exception as e:
            raise e