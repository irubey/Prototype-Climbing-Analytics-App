from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta, timezone
from app.models import (
    ClimberSummary,
    ClimbingDiscipline,
    CruxAngle,
    CruxEnergyType,
    HoldType,
    SessionLength,
    SleepScore,
    NutritionScore,
    UserTicks,
    PerformancePyramid,
    User
)
from app.services.grade_processor import GradeProcessor
from app.services.database_service import DatabaseService
from app import db
from uuid import UUID
from sqlalchemy import func, desc, and_

class UserInputData:
    """Data class for user input fields"""
    def __init__(
        self,
        # Core progression metrics
        highest_sport_grade_tried: Optional[str] = None,
        highest_trad_grade_tried: Optional[str] = None,
        highest_boulder_grade_tried: Optional[str] = None,
        total_climbs: Optional[int] = None,
        favorite_discipline: Optional[str] = None,
        years_climbing: Optional[int] = None,
        preferred_crag_last_year: Optional[str] = None,
        
        # Core Context
        climbing_goals: Optional[str] = None,
        current_training_description: Optional[str] = None,
        interests: Optional[List[str]] = None,
        injury_information: Optional[str] = None,
        additional_notes: Optional[str] = None,
        
        # Advanced Settings - Training Context
        current_training_frequency: Optional[str] = None,
        typical_session_length: Optional[str] = None,
        typical_session_intensity: Optional[str] = None,
        home_equipment: Optional[str] = None,
        access_to_commercial_gym: Optional[bool] = None,
        supplemental_training: Optional[str] = None,
        training_history: Optional[str] = None,
        
        # Performance metrics
        highest_grade_sport_sent_clean_on_lead: Optional[str] = None,
        highest_grade_tr_sent_clean: Optional[str] = None,
        highest_grade_trad_sent_clean_on_lead: Optional[str] = None,
        highest_grade_boulder_sent_clean: Optional[str] = None,
        onsight_grade_sport: Optional[str] = None,
        onsight_grade_trad: Optional[str] = None,
        flash_grade_boulder: Optional[str] = None,
        
        # Health and Limitations
        physical_limitations: Optional[str] = None,
        
        # Recent Activity
        activity_last_30_days: Optional[int] = None,
        
        # Style preferences
        favorite_angle: Optional[str] = None,
        favorite_hold_types: Optional[str] = None,
        weakest_angle: Optional[str] = None,
        strongest_angle: Optional[str] = None,
        favorite_energy_type: Optional[str] = None,
        strongest_energy_type: Optional[str] = None,
        weakest_energy_type: Optional[str] = None,
        strongest_hold_types: Optional[str] = None,
        weakest_hold_types: Optional[str] = None,
        
        # Lifestyle
        sleep_score: Optional[str] = None,
        nutrition_score: Optional[str] = None
    ):
        # Core progression metrics
        self.highest_sport_grade_tried = highest_sport_grade_tried
        self.highest_trad_grade_tried = highest_trad_grade_tried
        self.highest_boulder_grade_tried = highest_boulder_grade_tried
        self.total_climbs = total_climbs
        self.favorite_discipline = getattr(ClimbingDiscipline, favorite_discipline) if favorite_discipline else None
        self.years_climbing = years_climbing
        self.preferred_crag_last_year = preferred_crag_last_year
        
        # Core Context
        self.climbing_goals = climbing_goals
        self.current_training_description = current_training_description
        self.interests = interests
        self.injury_information = injury_information
        self.additional_notes = additional_notes
        
        # Advanced Settings - Training Context
        self.current_training_frequency = current_training_frequency
        self.typical_session_length = getattr(SessionLength, typical_session_length) if typical_session_length else None
        self.typical_session_intensity = typical_session_intensity
        self.home_equipment = home_equipment
        self.access_to_commercial_gym = access_to_commercial_gym
        self.supplemental_training = supplemental_training
        self.training_history = training_history
        
        # Performance metrics
        self.highest_grade_sport_sent_clean_on_lead = highest_grade_sport_sent_clean_on_lead
        self.highest_grade_tr_sent_clean = highest_grade_tr_sent_clean
        self.highest_grade_trad_sent_clean_on_lead = highest_grade_trad_sent_clean_on_lead
        self.highest_grade_boulder_sent_clean = highest_grade_boulder_sent_clean
        self.onsight_grade_sport = onsight_grade_sport
        self.onsight_grade_trad = onsight_grade_trad
        self.flash_grade_boulder = flash_grade_boulder
        
        # Health and Limitations
        self.physical_limitations = physical_limitations
        
        # Recent Activity
        self.activity_last_30_days = activity_last_30_days
        
        # Style preferences
        self.favorite_angle = getattr(CruxAngle, favorite_angle) if favorite_angle else None
        self.strongest_angle = getattr(CruxAngle, strongest_angle) if strongest_angle else None
        self.weakest_angle = getattr(CruxAngle, weakest_angle) if weakest_angle else None
        self.favorite_energy_type = getattr(CruxEnergyType, favorite_energy_type) if favorite_energy_type else None
        self.strongest_energy_type = getattr(CruxEnergyType, strongest_energy_type) if strongest_energy_type else None
        self.weakest_energy_type = getattr(CruxEnergyType, weakest_energy_type) if weakest_energy_type else None
        self.favorite_hold_types = getattr(HoldType, favorite_hold_types) if favorite_hold_types else None
        self.strongest_hold_types = getattr(HoldType, strongest_hold_types) if strongest_hold_types else None
        self.weakest_hold_types = getattr(HoldType, weakest_hold_types) if weakest_hold_types else None
        
        # Lifestyle
        self.sleep_score = getattr(SleepScore, sleep_score) if sleep_score else None
        self.nutrition_score = getattr(NutritionScore, nutrition_score) if nutrition_score else None

    def to_dict(self) -> Dict[str, Any]:
        """Convert user input to dictionary, excluding None values and converting enums to their values"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None:
                if hasattr(v, 'value'):
                    result[k] = v.value
                else:
                    result[k] = v
        return result

class ClimberSummaryService:
    def __init__(self, user_id: UUID):
        self.user_id = user_id
        self.grade_processor = GradeProcessor()
        self.user = User.query.get(user_id)
        self.username = self.user.username
        
    def get_grade_from_tick(self, tick: Union[UserTicks, Dict, None]) -> Optional[str]:
        """Get standardized grade from a tick using GradeProcessor.
        
        Args:
            tick: Can be either a UserTicks model instance or a dictionary containing tick data
        """
        if tick is None:
            return None
            
        # Handle both model instances and dictionaries
        binned_code = tick.binned_code if isinstance(tick, UserTicks) else tick.get('binned_code')
        return self.grade_processor.get_grade_from_code(binned_code) if binned_code is not None else None
        
    def get_core_progression_metrics(self) -> Dict[str, Any]:
        """Calculate core progression metrics using DatabaseService"""
        # Get the query object
        user_ticks_query = DatabaseService.get_user_ticks_by_id(self.user_id)
        
        return {
            "highest_sport_grade_tried": self.get_grade_from_tick(
                DatabaseService.get_highest_grade(self.user_id, 'sport')
            ),
            "highest_trad_grade_tried": self.get_grade_from_tick(
                DatabaseService.get_highest_grade(self.user_id, 'trad')
            ),
            "highest_boulder_grade_tried": self.get_grade_from_tick(
                DatabaseService.get_highest_grade(self.user_id, 'boulder')
            ),
            "total_climbs": user_ticks_query.count(),  # Using SQLAlchemy's count() on query object
            "favorite_discipline": (discipline_counts := DatabaseService.get_discipline_counts(self.user_id)) 
                and discipline_counts.discipline,
            "years_climbing": self._calculate_years_climbing(),
            "preferred_crag_last_year": (preferred_crag := DatabaseService.get_preferred_crag(self.user_id)) 
                and preferred_crag.location
        }

    def _calculate_years_climbing(self) -> int:
        earliest_tick = DatabaseService.get_earliest_tick_date(self.user_id)
        if earliest_tick and earliest_tick.tick_date:
            return (datetime.now().date() - earliest_tick.tick_date).days // 365
        return 0
        
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics using DatabaseService"""
        lead_styles = ['Redpoint', 'Onsight', 'Flash', 'Pinkpoint']
        
        sport_query = DatabaseService.get_clean_sends(
            self.user_id, 'sport', lead_styles
        )
        trad_query = DatabaseService.get_clean_sends(
            self.user_id, 'trad', lead_styles
        )
        boulder_query = DatabaseService.get_clean_sends(
            self.user_id, 'boulder'
        )

        return {
            "highest_grade_sport_sent_clean_on_lead": self.get_grade_from_tick(
                DatabaseService.get_max_clean_send(sport_query)
            ),
            "highest_grade_tr_sent_clean": self.get_grade_from_tick(
                DatabaseService.get_max_clean_send(
                    DatabaseService.get_clean_sends(self.user_id, 'trad')
                )
            ),
            "highest_grade_trad_sent_clean_on_lead": self.get_grade_from_tick(
                DatabaseService.get_max_clean_send(trad_query)
            ),
            "highest_grade_boulder_sent_clean": self.get_grade_from_tick(
                DatabaseService.get_max_clean_send(boulder_query)
            ),
            "onsight_grade_sport": self.get_grade_from_tick(
                DatabaseService.get_max_clean_send(
                    DatabaseService.get_clean_sends(self.user_id, 'sport', ['Onsight'])
                )
            ),
            "onsight_grade_trad": self.get_grade_from_tick(
                DatabaseService.get_max_clean_send(
                    DatabaseService.get_clean_sends(self.user_id, 'trad', ['Onsight'])
                )
            ),
            "flash_grade_boulder": self.get_grade_from_tick(
                DatabaseService.get_max_clean_send(
                    DatabaseService.get_clean_sends(self.user_id, 'boulder', ['Flash'])
                )
            )
        }
        
    def get_style_preferences(self) -> Dict[str, Any]:
        """Analyze climbing style preferences using pyramid data"""
        # Get pyramid data from DatabaseService
        pyramids = DatabaseService.get_pyramids_by_user_id(self.user_id)
        
        # Combine all entries for analysis
        all_entries = []
        for discipline, entries in pyramids.items():
            all_entries.extend(entries)
            
        # Analyze angles
        angle_counts = {}
        angle_grades = {}
        for entry in all_entries:
            if entry.get('crux_angle'):
                angle = entry['crux_angle']
                angle_counts[angle] = angle_counts.get(angle, 0) + 1
                current_grade = angle_grades.get(angle, 0)
                angle_grades[angle] = max(current_grade, entry.get('binned_code', 0))

        # Analyze energy systems
        energy_counts = {}
        energy_grades = {}
        for entry in all_entries:
            if entry.get('crux_energy'):
                energy = entry['crux_energy']
                energy_counts[energy] = energy_counts.get(energy, 0) + 1
                current_grade = energy_grades.get(energy, 0)
                energy_grades[energy] = max(current_grade, entry.get('binned_code', 0))

        # Get favorites and strengths
        favorite_angle = max(angle_counts.items(), key=lambda x: x[1])[0] if angle_counts else None
        strongest_angle = max(angle_grades.items(), key=lambda x: x[1])[0] if angle_grades else None
        weakest_angle = min(angle_grades.items(), key=lambda x: x[1])[0] if angle_grades else None

        favorite_energy = max(energy_counts.items(), key=lambda x: x[1])[0] if energy_counts else None
        strongest_energy = max(energy_grades.items(), key=lambda x: x[1])[0] if energy_grades else None
        weakest_energy = min(energy_grades.items(), key=lambda x: x[1])[0] if energy_grades else None

        # Hold type analysis
        hold_type_counts = self._analyze_hold_types(all_entries)
        favorite_hold = max(hold_type_counts.items(), key=lambda x: x[1])[0] if hold_type_counts else None
        strongest_hold = max(hold_type_counts.items(), key=lambda x: x[1])[0] if hold_type_counts else None
        weakest_hold = min(hold_type_counts.items(), key=lambda x: x[1])[0] if hold_type_counts else None

        # Convert string values to enums
        return {
            "favorite_angle": CruxAngle(favorite_angle) if favorite_angle else None,
            "strongest_angle": CruxAngle(strongest_angle) if strongest_angle else None,
            "weakest_angle": CruxAngle(weakest_angle) if weakest_angle else None,
            "favorite_energy_type": CruxEnergyType(favorite_energy) if favorite_energy else None,
            "strongest_energy_type": CruxEnergyType(strongest_energy) if strongest_energy else None,
            "weakest_energy_type": CruxEnergyType(weakest_energy) if weakest_energy else None,
            "favorite_hold_types": HoldType(favorite_hold) if favorite_hold else None,
            "strongest_hold_types": HoldType(strongest_hold) if strongest_hold else None,
            "weakest_hold_types": HoldType(weakest_hold) if weakest_hold else None
        }

    def _analyze_hold_types(self, entries: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze hold types from route names in pyramid entries"""
        hold_type_counts = {hold_type.value: 0 for hold_type in HoldType}
        
        for entry in entries:
            route_name = entry.get('route_name', '').lower()
            if "crimp" in route_name: hold_type_counts[HoldType.Crimps.value] += 1
            if "sloper" in route_name: hold_type_counts[HoldType.Slopers.value] += 1
            if "pocket" in route_name or "mono" in route_name: hold_type_counts[HoldType.Pockets.value] += 1
            if "pinch" in route_name: hold_type_counts[HoldType.Pinches.value] += 1
            if "crack" in route_name: hold_type_counts[HoldType.Cracks.value] += 1
            
        return hold_type_counts
        
    def get_grade_pyramids(self) -> Dict[str, Any]:
        """Calculate grade pyramids using PerformancePyramid and UserTicks"""
        def process_pyramid(discipline: str) -> List[Dict[str, Any]]:
            pyramid_data = db.session.query(
                UserTicks.binned_code,
                func.count().label('count'),
                func.max(UserTicks.tick_date).label('last_sent')
            ).join(
                PerformancePyramid,
                and_(
                    PerformancePyramid.tick_id == UserTicks.id,
                    PerformancePyramid.user_id == self.user_id
                )
            ).filter(
                UserTicks.discipline == discipline,
                UserTicks.send_bool == True
            ).group_by(
                UserTicks.binned_code
            ).order_by(
                desc(UserTicks.binned_code)
            ).all()

            return [{
                "grade": self.grade_processor.get_grade_from_code(entry.binned_code),
                "num_sends": entry.count,
                "last_sent": entry.last_sent.strftime('%Y-%m-%d') if entry.last_sent else None
            } for entry in pyramid_data]

        return {
            "sport": process_pyramid('sport'),
            "trad": process_pyramid('trad'),
            "boulder": process_pyramid('boulder')
        }
        
    def get_recent_activity(self) -> Dict[str, Any]:
        """Calculate recent activity metrics using DatabaseService"""
        projects = DatabaseService.get_current_projects(self.user_id)
        return {
            "activity_last_30_days": DatabaseService.get_recent_sends_count(self.user_id),
            "current_projects": [{
                "name": p.route_name,
                "grade": p.route_grade,
                "discipline": p.discipline.value if p.discipline else None,
                "location": p.location,
                "attempts": p.attempts,
                "days_tried": p.days_tried,
                "last_tried": p.last_tried.strftime('%Y-%m-%d') if p.last_tried else None
            } for p in projects]
        }
    
    def get_recent_favorite_routes(self) -> List[Dict[str, Any]]:
        """Calculate favorite routes using DatabaseService"""
        favorite_ticks = DatabaseService.get_user_ticks_by_id(self.user_id).filter_by(user_stars=5)\
            .order_by((UserTicks.notes != '').desc(), UserTicks.tick_date.desc()).limit(10).all()
            
        return [{
            "name": route.route_name,
            "grade": route.route_grade,
            "discipline": route.discipline.value,
            "location": route.location,
            "notes": route.notes
        } for route in favorite_ticks]

    def update_summary(self, user_input: Optional[UserInputData] = None):
        """
        Update or create climber summary with optional user input.
        
        Args:
            user_input: Optional UserInputData object containing user-provided information
        """
        # Get all metrics
        core_metrics = self.get_core_progression_metrics()
        performance_metrics = self.get_performance_metrics()
        style_preferences = self.get_style_preferences()
        grade_pyramids = self.get_grade_pyramids()
        recent_activity = self.get_recent_activity()
        recent_favorite_routes = self.get_recent_favorite_routes()
        
        # Combine all metrics
        summary_data = {
            "user_id": self.user_id,
            **core_metrics,
            **performance_metrics,
            **style_preferences,
            "grade_pyramid_sport": grade_pyramids["sport"],
            "grade_pyramid_trad": grade_pyramids["trad"],
            "grade_pyramid_boulder": grade_pyramids["boulder"],
            **recent_activity,
            "recent_favorite_routes": recent_favorite_routes,
            "current_info_as_of": datetime.now(timezone.utc)  # Update timestamp
        }
        
        # Get existing summary
        summary = ClimberSummary.query.get(self.user_id)
        
        if summary:
            # Preserve user input fields if not provided in update
            user_input_fields = [
                'current_training_frequency',
                'typical_session_length',
                'typical_session_intensity',
                'home_equipment',
                'access_to_commercial_gym',
                'supplemental_training',
                'training_history',
                'physical_limitations',
                'climbing_goals',
                'current_training_description',
                'interests',
                'injury_information',
                'sleep_score',
                'nutrition_score',
                'additional_notes'
            ]
            
            if not user_input:
                # Preserve existing user input data
                for field in user_input_fields:
                    existing_value = getattr(summary, field)
                    if existing_value is not None:
                        summary_data[field] = existing_value
            
            # Update fields
            for key, value in summary_data.items():
                if hasattr(summary, key):
                    setattr(summary, key, value)
        else:
            # Create new summary
            if not user_input:
                # Set default values for required fields
                summary_data.update({
                    'current_training_frequency': None,
                    'typical_session_length': None,
                    'typical_session_intensity': None,
                    'home_equipment': None,
                    'access_to_commercial_gym': False,
                    'supplemental_training': None,
                    'training_history': None,
                    'created_at': datetime.now(timezone.utc)
                })
            summary = ClimberSummary(**summary_data)
            db.session.add(summary)
            
        # Apply user input if provided
        if user_input:
            user_input_dict = user_input.to_dict()
            for key, value in user_input_dict.items():
                if hasattr(summary, key):
                    setattr(summary, key, value)
            
        db.session.commit()
        return summary

def update_all_summaries():
    """Update summaries for all users, preserving existing user input."""
    users = db.session.query(UserTicks.user_id, UserTicks.username).distinct().all()
    for user_id, username in users:
        service = ClimberSummaryService(user_id=user_id, username=username)
        service.update_summary()  # No user input, will preserve existing

# Example usage:
"""
# Update with user input
user_input = UserInputData(
    training_frequency=TrainingFrequency.TWICE_WEEK,
    typical_session_length=SessionLength.TWO_TO_THREE_HOURS,
    has_hangboard=True,
    has_home_wall=False,
    current_injuries="Slight finger strain",
    climbing_goals="Project 5.12a by end of year",
    willing_to_train_indoors=True
)

service = ClimberSummaryService(user_id=123, username="climber1")
service.update_summary(user_input=user_input)

# Update without user input (preserves existing)
service.update_summary()
"""
