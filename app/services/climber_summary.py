from typing import Dict, Any, List, Optional
from sqlalchemy import func, desc, case, and_, exists
from datetime import datetime, timedelta
from app.models import (
    UserTicks, 
    SportPyramid, 
    TradPyramid, 
    BoulderPyramid,
    ClimberSummary,
    ClimbingDiscipline,
    ClimbingStyle,
    RouteCharacteristic,
    HoldType,
    SessionLength,
    db,
    SleepScore,
    NutritionScore
)
from app.services.grade_processor import GradeProcessor

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
        years_climbing_outside: Optional[int] = None,
        preferred_crag_last_year: Optional[str] = None,
        
        # Training context
        training_frequency: Optional[str] = None,
        typical_session_length: Optional[str] = None,
        has_hangboard: Optional[bool] = None,
        has_home_wall: Optional[bool] = None,
        goes_to_gym: Optional[bool] = None,
        
        # Performance metrics
        highest_grade_sport_sent_clean_on_lead: Optional[str] = None,
        highest_grade_tr_sent_clean: Optional[str] = None,
        highest_grade_trad_sent_clean_on_lead: Optional[str] = None,
        highest_grade_boulder_sent_clean: Optional[str] = None,
        onsight_grade_sport: Optional[str] = None,
        onsight_grade_trad: Optional[str] = None,
        flash_grade_boulder: Optional[str] = None,
        
        # Injury history and limitations
        current_injuries: Optional[str] = None,
        injury_history: Optional[str] = None,
        physical_limitations: Optional[str] = None,
        
        # Goals and preferences
        climbing_goals: Optional[str] = None,
        willing_to_train_indoors: Optional[bool] = None,
        
        # Recent activity
        sends_last_30_days: Optional[int] = None,
        
        # Style preferences
        favorite_angle: Optional[str] = None,
        favorite_hold_types: Optional[str] = None,
        weakest_style: Optional[str] = None,
        strongest_style: Optional[str] = None,
        favorite_energy_type: Optional[str] = None,
        
        # Lifestyle
        sleep_score: Optional[str] = None,
        nutrition_score: Optional[str] = None,

        # Additional notes
        additional_notes: Optional[str] = None
    ):
        # Core progression metrics
        self.highest_sport_grade_tried = highest_sport_grade_tried
        self.highest_trad_grade_tried = highest_trad_grade_tried
        self.highest_boulder_grade_tried = highest_boulder_grade_tried
        self.total_climbs = total_climbs
        self.favorite_discipline = getattr(ClimbingDiscipline, favorite_discipline) if favorite_discipline else None
        self.years_climbing_outside = years_climbing_outside
        self.preferred_crag_last_year = preferred_crag_last_year
        
        # Training context
        self.training_frequency = training_frequency
        self.typical_session_length = getattr(SessionLength, typical_session_length) if typical_session_length else None
        self.has_hangboard = has_hangboard
        self.has_home_wall = has_home_wall
        self.goes_to_gym = goes_to_gym
        
        # Performance metrics
        self.highest_grade_sport_sent_clean_on_lead = highest_grade_sport_sent_clean_on_lead
        self.highest_grade_tr_sent_clean = highest_grade_tr_sent_clean
        self.highest_grade_trad_sent_clean_on_lead = highest_grade_trad_sent_clean_on_lead
        self.highest_grade_boulder_sent_clean = highest_grade_boulder_sent_clean
        self.onsight_grade_sport = onsight_grade_sport
        self.onsight_grade_trad = onsight_grade_trad
        self.flash_grade_boulder = flash_grade_boulder
        
        # Injury history and limitations
        self.current_injuries = current_injuries
        self.injury_history = injury_history
        self.physical_limitations = physical_limitations
        
        # Goals and preferences
        self.climbing_goals = climbing_goals
        self.willing_to_train_indoors = willing_to_train_indoors
        
        # Recent activity
        self.sends_last_30_days = sends_last_30_days
        
        # Style preferences
        self.favorite_angle = getattr(ClimbingStyle, favorite_angle) if favorite_angle else None
        self.favorite_hold_types = getattr(HoldType, favorite_hold_types) if favorite_hold_types else None
        self.weakest_style = getattr(ClimbingStyle, weakest_style) if weakest_style else None
        self.strongest_style = getattr(ClimbingStyle, strongest_style) if strongest_style else None
        self.favorite_energy_type = getattr(RouteCharacteristic, favorite_energy_type) if favorite_energy_type else None
        
        # Lifestyle
        self.sleep_score = getattr(SleepScore, sleep_score) if sleep_score else None
        self.nutrition_score = getattr(NutritionScore, nutrition_score) if nutrition_score else None

        # Additional notes
        self.additional_notes = additional_notes

    def to_dict(self) -> Dict[str, Any]:
        """Convert user input to dictionary, excluding None values and converting enums to their values"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None:
                # Convert enum to its value if it's an enum
                if hasattr(v, 'value'):
                    result[k] = v.value
                else:
                    result[k] = v
        return result

class ClimberSummaryService:
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.grade_processor = GradeProcessor()
        self.username = username

    
        
    def get_grade_from_tick(self, tick: UserTicks) -> str:
        """Get standardized grade from a tick using GradeProcessor."""
        if not tick:
            return None
        return self.grade_processor.get_grade_from_code(tick.binned_code)
        
    def get_core_progression_metrics(self) -> Dict[str, Any]:
        """Calculate core progression metrics from UserTicks."""
        # Get base query for user's ticks
        user_ticks = UserTicks.query.filter_by(userId=self.user_id)
        
        # Calculate highest grades tried
        highest_sport = user_ticks.filter_by(discipline='sport').order_by(desc(UserTicks.binned_code)).first()
        highest_trad = user_ticks.filter_by(discipline='trad').order_by(desc(UserTicks.binned_code)).first()
        highest_boulder = user_ticks.filter_by(discipline='boulder').order_by(desc(UserTicks.binned_code)).first()
        
        # Calculate total climbs
        total_climbs = user_ticks.count()
        
        # Calculate favorite style based on most frequent discipline
        discipline_counts = db.session.query(
            UserTicks.discipline,
            func.count(UserTicks.discipline).label('count')
        ).filter_by(userId=self.user_id).group_by(UserTicks.discipline).order_by(desc('count')).first()
        
        # Calculate years climbing (from earliest tick)
        earliest_tick = user_ticks.order_by(UserTicks.tick_date).first()
        years_climbing = 0
        if earliest_tick:
            years_climbing = (datetime.now().date() - earliest_tick.tick_date).days // 365
            
        # Get most frequent crag in the last year
        year_ago = datetime.now().date() - timedelta(days=365)
        preferred_crag = db.session.query(
            UserTicks.location,
            func.count(UserTicks.location).label('count')
        ).filter(
            UserTicks.userId == self.user_id,
            UserTicks.tick_date >= year_ago
        ).group_by(UserTicks.location).order_by(desc('count')).first()
        
        return {
            "highest_sport_grade_tried": self.get_grade_from_tick(highest_sport),
            "highest_trad_grade_tried": self.get_grade_from_tick(highest_trad),
            "highest_boulder_grade_tried": self.get_grade_from_tick(highest_boulder),
            "total_climbs": total_climbs,
            "favorite_discipline": discipline_counts.discipline if discipline_counts else None,
            "years_climbing_outside": years_climbing,
            "preferred_crag_last_year": preferred_crag.location if preferred_crag else None
        }
        
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics from UserTicks."""
        # Base query for clean sends
        clean_sends = UserTicks.query.filter_by(
            userId=self.user_id,
            send_bool=True
        )
        
        # Sport clean sends
        sport_sends = clean_sends.filter_by(discipline='sport')
        highest_sport_lead = sport_sends.filter(UserTicks.lead_style.in_([
            'Redpoint',
            'Onsight',
            'Flash',
            'Pinkpoint'
        ])).order_by(desc(UserTicks.binned_code)).first()
        
        tr_sends = clean_sends.filter_by(discipline='trad')
        highest_tr = tr_sends.order_by(desc(UserTicks.binned_code)).first()
        
        # Trad clean sends
        trad_sends = clean_sends.filter_by(discipline='trad')
        highest_trad_lead = trad_sends.filter(UserTicks.lead_style.in_([
            'Redpoint',
            'Onsight',
            'Flash',
            'Pinkpoint'
        ])).order_by(desc(UserTicks.binned_code)).first()
        
        highest_trad_top = trad_sends.filter_by(discipline='trad').order_by(desc(UserTicks.binned_code)).first()
        
        # Boulder clean sends
        highest_boulder = clean_sends.filter_by(discipline='boulder').order_by(desc(UserTicks.binned_code)).first()
        
        # Onsight grades
        sport_onsight = sport_sends.filter_by(lead_style='Onsight').order_by(desc(UserTicks.binned_code)).first()
        trad_onsight = trad_sends.filter_by(lead_style='Onsight').order_by(desc(UserTicks.binned_code)).first()
        
        # Flash grades for boulder
        boulder_flash = clean_sends.filter_by(
            discipline='boulder',
            lead_style='Flash'
        ).order_by(desc(UserTicks.binned_code)).first()
        
        return {
            "highest_grade_sport_sent_clean_on_lead": self.get_grade_from_tick(highest_sport_lead),
            "highest_grade_tr_sent_clean": self.get_grade_from_tick(highest_tr),
            "highest_grade_trad_sent_clean_on_lead": self.get_grade_from_tick(highest_trad_lead),
            "highest_grade_boulder_sent_clean": self.get_grade_from_tick(highest_boulder),
            "onsight_grade_sport": self.get_grade_from_tick(sport_onsight),
            "onsight_grade_trad": self.get_grade_from_tick(trad_onsight),
            "flash_grade_boulder": self.get_grade_from_tick(boulder_flash)
        }
        
    def get_style_preferences(self) -> Dict[str, Any]:
        """Analyze climbing style preferences from Pyramid tables."""
        # Get all pyramid sends for analysis
        sport_sends = SportPyramid.query.filter_by(userId=self.user_id)
        trad_sends = TradPyramid.query.filter_by(userId=self.user_id)
        boulder_sends = BoulderPyramid.query.filter_by(userId=self.user_id)
        
        # Analyze favorite angle/style by summing counts across all disciplines
        style_counts_sport = db.session.query(
            SportPyramid.route_style,
            func.count().label('count')
        ).filter_by(userId=self.user_id).group_by(SportPyramid.route_style)
        
        style_counts_trad = db.session.query(
            TradPyramid.route_style,
            func.count().label('count')
        ).filter_by(userId=self.user_id).group_by(TradPyramid.route_style)
        
        style_counts_boulder = db.session.query(
            BoulderPyramid.route_style,
            func.count().label('count')
        ).filter_by(userId=self.user_id).group_by(BoulderPyramid.route_style)
        
        # Calculate completeness ratio for each discipline
        def calculate_style_completeness(style_counts_query):
            style_counts = style_counts_query.all()
            routes_with_style = sum(count.count for count in style_counts if count.route_style is not None)
            total_routes = sum(count.count for count in style_counts)
            return routes_with_style / total_routes if total_routes > 0 else 0
            
        sport_completeness = calculate_style_completeness(style_counts_sport)
        trad_completeness = calculate_style_completeness(style_counts_trad)
        boulder_completeness = calculate_style_completeness(style_counts_boulder)
        
        # Only include disciplines with >80% completeness
        combined_style_counts = {}
        for style_count in style_counts_sport.all():
            if style_count.route_style and sport_completeness > 0.8:
                combined_style_counts[style_count.route_style] = style_count.count
                
        for style_count in style_counts_trad.all():
            if style_count.route_style and trad_completeness > 0.8:
                combined_style_counts[style_count.route_style] = combined_style_counts.get(style_count.route_style, 0) + style_count.count
                
        for style_count in style_counts_boulder.all():
            if style_count.route_style and boulder_completeness > 0.8:
                combined_style_counts[style_count.route_style] = combined_style_counts.get(style_count.route_style, 0) + style_count.count
        
        # Get the most frequent style if we have enough data
        favorite_style = max(combined_style_counts.items(), key=lambda x: x[1])[0] if combined_style_counts else None
        
        # Analyze strongest style (highest grade by style)
        style_grades = {}
        for style in ClimbingStyle:
            # Check each discipline for the highest grade in this style
            highest_sport = sport_sends.filter_by(route_style=style).order_by(desc(SportPyramid.binned_code)).first() if sport_completeness > 0.8 else None
            highest_trad = trad_sends.filter_by(route_style=style).order_by(desc(TradPyramid.binned_code)).first() if trad_completeness > 0.8 else None
            highest_boulder = boulder_sends.filter_by(route_style=style).order_by(desc(BoulderPyramid.binned_code)).first() if boulder_completeness > 0.8 else None
            
            # Get the highest grade across all disciplines
            highest_codes = [
                highest_sport.binned_code if highest_sport else None,
                highest_trad.binned_code if highest_trad else None,
                highest_boulder.binned_code if highest_boulder else None
            ]
            highest_code = max([code for code in highest_codes if code is not None], default=None)
            
            if highest_code is not None:
                style_grades[style] = highest_code
                
        strongest_style = max(style_grades.items(), key=lambda x: x[1])[0] if style_grades else None
        weakest_style = min(style_grades.items(), key=lambda x: x[1])[0] if style_grades else None
        
        # Analyze favorite energy system using a simpler query
        energy_counts = db.session.query(
            SportPyramid.route_characteristic,
            func.count().label('count')
        ).filter_by(userId=self.user_id).group_by(SportPyramid.route_characteristic).order_by(desc('count')).first()
        
        # Initialize hold type counts using enum values
        hold_type_counts = {hold_type: 0 for hold_type in HoldType}
        
        # Combine all pyramid sends
        all_sends = []
        all_sends.extend(sport_sends.all())
        all_sends.extend(trad_sends.all())
        all_sends.extend(boulder_sends.all())
        
        # Count occurrences of each hold type in route names
        for send in all_sends:
            route_name_lower = send.route_name.lower() if send.route_name else ""
            
            # Check route name for hold type keywords using enum values
            if "crimp" in route_name_lower:
                hold_type_counts[HoldType.Crimps] += 1
            if "sloper" in route_name_lower:
                hold_type_counts[HoldType.Slopers] += 1
            if "pocket" in route_name_lower or "mono" in route_name_lower:
                hold_type_counts[HoldType.Pockets] += 1
            if "pinch" in route_name_lower:
                hold_type_counts[HoldType.Pinches] += 1
            if "crack" in route_name_lower or "splitter" in route_name_lower:
                hold_type_counts[HoldType.Cracks] += 1
                    
        # Calculate hold type completeness ratio
        filled_hold_types = sum(1 for count in hold_type_counts.values() if count > 0)
        total_hold_types = len(HoldType)
        ratio = filled_hold_types / total_hold_types if total_hold_types > 0 else 0

        if ratio > 0.5:
            favorite_hold_type = max(hold_type_counts.items(), key=lambda x: x[1])[0].value
        else:
            favorite_hold_type = None

        return {
            "favorite_angle": favorite_style.value if favorite_style else None,
            "strongest_style": strongest_style.value if strongest_style else None,
            "weakest_style": weakest_style.value if weakest_style else None,
            "favorite_energy_type": energy_counts.route_characteristic.value if energy_counts and energy_counts.route_characteristic else None,
            "favorite_hold_types": favorite_hold_type
        }
        
    def get_grade_pyramids(self) -> Dict[str, Any]:
        """Calculate grade pyramids for each discipline."""
        def get_pyramid_data(pyramid_table) -> List[Dict[str, Any]]:
            """Helper to process pyramid data for a discipline."""
            pyramid_data = db.session.query(
                pyramid_table.binned_code,
                func.count(pyramid_table.id).label('count'),
                func.max(pyramid_table.tick_date).label('last_sent')
            ).filter_by(
                userId=self.user_id
            ).group_by(
                pyramid_table.binned_code
            ).order_by(
                desc(pyramid_table.binned_code)
            ).all()
            
            return [{
                "grade": self.grade_processor.get_grade_from_code(entry.binned_code),
                "num_sends": entry.count,
                "last_sent": entry.last_sent.strftime('%Y-%m-%d') if entry.last_sent else None
            } for entry in pyramid_data]
        
        return {
            "sport": get_pyramid_data(SportPyramid),
            "trad": get_pyramid_data(TradPyramid),
            "boulder": get_pyramid_data(BoulderPyramid)
        }
        
    def get_recent_activity(self) -> Dict[str, Any]:
        """Calculate recent activity metrics."""
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        # Count sends in last 30 days
        recent_sends = UserTicks.query.filter(
            UserTicks.userId == self.user_id,
            UserTicks.tick_date >= thirty_days_ago,
            UserTicks.send_bool == True
        ).count()
        
        # Get current projects using subquery for routes with sends
        sent_routes = db.session.query(
            UserTicks.route_name,
            UserTicks.location
        ).filter(
            UserTicks.userId == self.user_id,
            UserTicks.send_bool == True
        ).subquery()

        # Main query for current projects
        projects = db.session.query(
            UserTicks.route_name,
            UserTicks.location,
            UserTicks.discipline,
            UserTicks.route_grade,
            func.count(func.distinct(UserTicks.tick_date)).label('days_tried'),
            func.sum(
                case(
                    (UserTicks.length_category != 'multipitch', UserTicks.pitches),
                    else_=1
                )
            ).label('attempts'),
            func.max(UserTicks.tick_date).label('last_tried')
        ).filter(
            UserTicks.userId == self.user_id,
            ~exists().where(and_(
                sent_routes.c.route_name == UserTicks.route_name,
                sent_routes.c.location == UserTicks.location
            ))
        ).group_by(
            UserTicks.route_name,
            UserTicks.location,
            UserTicks.discipline,
            UserTicks.route_grade
        ).having(
            func.count(func.distinct(UserTicks.tick_date)) >= 2
        ).order_by(
            desc(func.max(UserTicks.tick_date))
        ).limit(5).all()
        
        project_list = [{
            "name": p.route_name,
            "grade": p.route_grade,
            "discipline": p.discipline.value if p.discipline else None,
            "location": p.location,
            "attempts": p.attempts,
            "days_tried": p.days_tried,
            "last_tried": p.last_tried.strftime('%Y-%m-%d') if p.last_tried else None
        } for p in projects]

        return {
            "sends_last_30_days": recent_sends,
            "current_projects": project_list
        }
    
    def get_recent_favorite_routes(self) -> Dict[str, Any]:
        """Calculate favorite routes."""
        favorite_routes = UserTicks.query.filter_by(userId=self.user_id, user_stars=5)\
            .order_by(
                (UserTicks.notes != '').desc(),
                UserTicks.tick_date.desc()
            )\
            .limit(10)\
            .all()
        return [
            {
                "name": route.route_name,
                "grade": route.route_grade,
                "discipline": route.discipline.value,
                "location": route.location,
                "notes": route.notes
            }
            for route in favorite_routes
        ]

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
            "userId": self.user_id,
            "username": self.username,
            **core_metrics,
            **performance_metrics,
            **style_preferences,
            "grade_pyramid_sport": grade_pyramids["sport"],
            "grade_pyramid_trad": grade_pyramids["trad"],
            "grade_pyramid_boulder": grade_pyramids["boulder"],
            **recent_activity,
            "recent_favorite_routes": recent_favorite_routes
        }
        
        # Add user input if provided
        if user_input:
            summary_data.update(user_input.to_dict())
        
        # Update or create summary
        summary = ClimberSummary.query.get(self.user_id)
        if summary:
            # Preserve existing user input if not provided in update
            if not user_input:
                existing_user_data = {
                    'training_frequency': summary.training_frequency,
                    'typical_session_length': summary.typical_session_length,
                    'has_hangboard': summary.has_hangboard,
                    'has_home_wall': summary.has_home_wall,
                    'current_injuries': summary.current_injuries,
                    'injury_history': summary.injury_history,
                    'physical_limitations': summary.physical_limitations,
                    'climbing_goals': summary.climbing_goals,
                    'willing_to_train_indoors': summary.willing_to_train_indoors,
                    'sleep_score': summary.sleep_score,
                    'nutrition_score': summary.nutrition_score,
                    'additional_notes': summary.additional_notes
                }
                summary_data.update({k: v for k, v in existing_user_data.items() if v is not None})
            
            # Update fields
            for key, value in summary_data.items():
                setattr(summary, key, value)
        else:
            summary = ClimberSummary(**summary_data)
            db.session.add(summary)
            
        db.session.commit()
        return summary

def update_all_summaries():
    """Update summaries for all users, preserving existing user input."""
    users = db.session.query(UserTicks.userId, UserTicks.username).distinct().all()
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
