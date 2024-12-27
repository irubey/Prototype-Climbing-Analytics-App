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

    @staticmethod
    def process_changes(username: str, changes_data: Dict[str, Any]) -> bool:
        """
        Process changes to pyramid data.
        
        Args:
            username: The username of the user making changes
            changes_data: Dictionary containing changes for each discipline
        """
        try:
            print(f"Processing changes for user {username}")
            print(f"Changes data: {changes_data}")

            for discipline, changes in changes_data.items():
                model_class = {
                    'sport': SportPyramid,
                    'trad': TradPyramid,
                    'boulder': BoulderPyramid
                }.get(discipline)

                if not model_class:
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
                        
                    if str(route_id).startswith('8'):  # Check for 8-prefixed IDs (new routes)
                        # Handle new route
                        updates['username'] = username  # Ensure username is set
                        updates['discipline'] = discipline  # Ensure discipline is set
                        updates['tick_date'] = updates.get('tick_date', datetime.now().date())  # Ensure date is set
                        
                        # Use the ID as is since it's already in the correct format
                        updates['tick_id'] = int(route_id)  # Convert string ID to integer
                        
                        PyramidUpdateService._add_new_route(
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
                                print(f"Updating route {route_id} with data: {updates}")
                                # Update basic fields
                                for field, value in updates.items():
                                    if hasattr(pyramid_entry, field):
                                        setattr(pyramid_entry, field, value)
                                
                                # Update binned grade and code if grade is changed
                                if 'route_grade' in updates:
                                    grade_processor = GradeProcessor()
                                    grade = updates['route_grade']
                                    # Get binned code
                                    binned_code = grade_processor.convert_grades_to_codes([grade])[0]
                                    pyramid_entry.binned_grade = grade
                                    pyramid_entry.binned_code = binned_code
                                    print(f"Updated binned grade to {grade} and code to {binned_code}")
                                
                                # Ensure critical fields are set
                                if not pyramid_entry.username:
                                    pyramid_entry.username = username
                                if not pyramid_entry.discipline:
                                    pyramid_entry.discipline = discipline
                                if not pyramid_entry.tick_date:
                                    pyramid_entry.tick_date = datetime.now().date()
                                
                                print(f"Updated pyramid entry: {pyramid_entry.route_name} with tick_id {pyramid_entry.tick_id}")
                            else:
                                print(f"No pyramid entry found for tick_id {route_id}")

                        except (ValueError, TypeError) as e:
                            print(f"Error updating route {route_id}: {str(e)}")
                            continue

            db.session.commit()
            print("Changes committed successfully")
            return True

        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"Error processing changes: {str(e)}")
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

    @staticmethod
    def _add_new_route(username: str, model_class: Any, route_data: Dict[str, Any], new_id: str) -> None:
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
                # If it's already a date object, use it as is
            else:
                route_data['tick_date'] = datetime.now().date()

            # Ensure tick_id is set
            if 'tick_id' not in route_data:
                route_data['tick_id'] = int(datetime.now().timestamp())
            print(f"Using tick_id: {route_data['tick_id']}")

            # Validate and bin the grade
            try:
                grade_processor = GradeProcessor()
                route_grade = route_data.get('route_grade', '')
                binned_code = grade_processor.convert_grades_to_codes([route_grade])[0]
                binned_grade = grade_processor.get_grade_from_code(binned_code)
            except ValueError as e:
                raise ValueError(f"Invalid route data: {str(e)}")

            # Set lead_style based on discipline and attempts
            num_attempts = int(route_data.get('num_attempts', 1))
            discipline = route_data.get('discipline', '')
            if discipline in ['sport', 'trad']:
                lead_style = 'Redpoint' if num_attempts > 1 else 'Flash'
            else:  # boulder
                lead_style = 'Send' if num_attempts > 1 else 'Flash'

            # Get season category from date
            classifier = ClimbClassifier()
            date_df = pd.DataFrame({
                'tick_date': [route_data['tick_date']]
            })
            season_category = classifier.classify_season(date_df).iloc[0]

            # Create new pyramid entry with all required fields
            new_entry = model_class(
                username=username,
                route_name=route_data.get('route_name', 'Unknown Route'),
                route_grade=route_data.get('route_grade', 'Unknown Grade'),
                tick_date=route_data['tick_date'],
                num_attempts=num_attempts,
                route_characteristic=route_data.get('route_characteristic', 'Unknown'),
                route_style=route_data.get('route_style', 'Unknown'),
                tick_id=route_data['tick_id'],
                binned_grade=binned_grade,
                binned_code=binned_code,
                length=None,  # Default to NA
                pitches=num_attempts,  # Set to attempts
                location='User Added',
                lead_style=lead_style,
                discipline=discipline,
                length_category=None,  # Default to NA
                season_category=season_category,
                route_url=None,  # Default to NA
                user_grade=route_data.get('route_grade', 'Unknown Grade')  # Same as route_grade
            )

            print(f"Adding new route: {new_entry.route_name} with grade {new_entry.route_grade} and tick_id {new_entry.tick_id}")
            db.session.add(new_entry)
        except Exception as e:
            print(f"Error adding new route: {str(e)}")
            raise 