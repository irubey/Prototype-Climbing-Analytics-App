from app import db
from sqlalchemy import Enum
import enum

# Enums for climbing-related fields
class ClimbingDiscipline(enum.Enum):
    tr = 'tr'
    boulder = 'boulder'
    sport = 'sport'
    trad = 'trad'
    mixed = 'mixed'
    winter_ice = 'winter_ice'
    aid = 'aid'
    
class SleepScore(enum.Enum):
    Poor = "Poor"
    Fair = "Fair"
    Good = "Good"
    Excellent = "Excellent"

class NutritionScore(enum.Enum):
    Poor = "Poor"
    Fair = "Fair"
    Good = "Good"
    Excellent = "Excellent"

class SessionLength(enum.Enum):
    LESS_THAN_1_HOUR = "Less than 1 hour"
    ONE_TO_TWO_HOURS = "1-2 hours"
    TWO_TO_THREE_HOURS = "2-3 hours"
    THREE_TO_FOUR_HOURS = "3-4 hours"
    FOUR_PLUS_HOURS = "4+ hours"
    
class ClimbingStyle(enum.Enum):
    Slab = "Slab"
    Vertical = "Vertical"
    Overhang = "Overhang"
    Roof = "Roof"


class RouteCharacteristic(enum.Enum):
    Power = "Power"
    Power_Endurance = "Power Endurance"
    Endurance = "Endurance"
    Technique = "Technique"

class HoldType(enum.Enum):
    Crimps = "Crimps"
    Slopers = "Slopers"
    Pockets = "Pockets"
    Pinches = "Pinches"
    Cracks = "Cracks"


class BaseModel(db.Model):
    __abstract__ = True  

    def as_dict(self):
        result = {}
        for c in self.__table__.columns:
            value = getattr(self, c.name)
            # Handle enum values
            if hasattr(value, 'value'):  # Check if it's an enum
                result[c.name] = value.value
            else:
                result[c.name] = value
        return result

class BinnedCodeDict(BaseModel):
    __tablename__ = 'binned_code_dict'
    binned_code = db.Column(db.Integer, primary_key=True)
    binned_grade = db.Column(db.String(50), nullable=False)

class BoulderPyramid(BaseModel):
    __tablename__ = 'boulder_pyramid'
    __table_args__ = (
        db.Index('idx_boulder_pyramid_username', 'username'),
        db.Index('idx_boulder_pyramid_tick_date', 'tick_date'),
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tick_id = db.Column(db.Integer)
    route_name = db.Column(db.String(255))
    tick_date = db.Column(db.Date)
    route_grade = db.Column(db.String(255))
    binned_grade = db.Column(db.String(255))
    binned_code = db.Column(db.Integer)
    length = db.Column(db.Integer)
    pitches = db.Column(db.Integer)
    location = db.Column(db.String(255))
    lead_style = db.Column(db.String(255))
    discipline = db.Column(Enum(ClimbingDiscipline))
    length_category = db.Column(db.String(255))
    season_category = db.Column(db.String(255))
    route_url = db.Column(db.String(255))
    user_grade = db.Column(db.String(255))
    username = db.Column(db.String(255))
    userId = db.Column(db.BigInteger)
    route_characteristic = db.Column(Enum(RouteCharacteristic))
    num_attempts = db.Column(db.Integer)
    route_style = db.Column(Enum(ClimbingStyle))

class SportPyramid(BaseModel):
    __tablename__ = 'sport_pyramid'
    __table_args__ = (
        db.Index('idx_sport_pyramid_username', 'username'),
        db.Index('idx_sport_pyramid_tick_date', 'tick_date'),
        db.Index('idx_sport_pyramid_lookup', 'username', 'route_name', 'tick_date'),
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tick_id = db.Column(db.Integer)
    route_name = db.Column(db.String(255))
    tick_date = db.Column(db.Date)
    route_grade = db.Column(db.String(255))
    binned_grade = db.Column(db.String(255))
    binned_code = db.Column(db.Integer)
    length = db.Column(db.Integer)
    pitches = db.Column(db.Integer)
    location = db.Column(db.String(255))
    lead_style = db.Column(db.String(255))
    discipline = db.Column(Enum(ClimbingDiscipline))
    length_category = db.Column(db.String(255))
    season_category = db.Column(db.String(255))
    route_url = db.Column(db.String(255))
    user_grade = db.Column(db.String(255))
    username = db.Column(db.String(255))
    userId = db.Column(db.BigInteger)
    route_characteristic = db.Column(Enum(RouteCharacteristic))
    num_attempts = db.Column(db.Integer)
    route_style = db.Column(Enum(ClimbingStyle))

class TradPyramid(BaseModel):
    __tablename__ = 'trad_pyramid'
    __table_args__ = (
        db.Index('idx_trad_pyramid_username', 'username'),
        db.Index('idx_trad_pyramid_tick_date', 'tick_date'),
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tick_id = db.Column(db.Integer)
    route_name = db.Column(db.String(255))
    tick_date = db.Column(db.Date)
    route_grade = db.Column(db.String(255))
    binned_grade = db.Column(db.String(255))
    binned_code = db.Column(db.Integer)
    length = db.Column(db.Integer)
    pitches = db.Column(db.Integer)
    location = db.Column(db.String(255))
    lead_style = db.Column(db.String(255))
    discipline = db.Column(Enum(ClimbingDiscipline))
    length_category = db.Column(db.String(255))
    season_category = db.Column(db.String(255))
    route_url = db.Column(db.String(255))
    user_grade = db.Column(db.String(255))
    username = db.Column(db.String(255))
    userId = db.Column(db.BigInteger)
    route_characteristic = db.Column(Enum(RouteCharacteristic))
    num_attempts = db.Column(db.Integer)
    route_style = db.Column(Enum(ClimbingStyle))

class UserTicks(BaseModel):
    __tablename__ = 'user_ticks'
    __table_args__ = (
        db.Index('idx_user_ticks_username', 'username'),
        db.Index('idx_user_ticks_tick_date', 'tick_date'),
        db.Index('idx_user_ticks_lookup', 'username', 'route_name', 'tick_date'),
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    route_name = db.Column(db.String(255))
    tick_date = db.Column(db.Date)
    route_grade = db.Column(db.String(255))
    binned_grade = db.Column(db.String(255))
    binned_code = db.Column(db.Integer)
    length = db.Column(db.Integer)
    pitches = db.Column(db.Integer)
    location = db.Column(db.String(255))
    location_raw = db.Column(db.String(255))
    lead_style = db.Column(db.String(255))
    cur_max_rp_sport = db.Column(db.Integer)
    cur_max_rp_trad = db.Column(db.Integer)
    cur_max_boulder = db.Column(db.Integer)
    difficulty_category = db.Column(db.String(255))
    discipline = db.Column(Enum(ClimbingDiscipline))
    send_bool = db.Column(db.Boolean)
    length_category = db.Column(db.String(255))
    season_category = db.Column(db.String(255))
    username = db.Column(db.String(255))
    userId = db.Column(db.BigInteger)
    route_url = db.Column(db.String(255))
    user_profile_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    notes = db.Column(db.Text)
    route_stars = db.Column(db.Float)
    user_stars = db.Column(db.Float)


class ClimberSummary(BaseModel):
    __tablename__ = 'climber_summary'
    
    # Primary Key
    userId = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.String(255))
    
    # Core progression metrics
    highest_sport_grade_tried = db.Column(db.String(255))
    highest_trad_grade_tried = db.Column(db.String(255))
    highest_boulder_grade_tried = db.Column(db.String(255))
    total_climbs = db.Column(db.Integer)
    favorite_discipline = db.Column(Enum(ClimbingDiscipline))
    years_climbing_outside = db.Column(db.Integer)
    preferred_crag_last_year = db.Column(db.String(255))
    
    # Training context
    training_frequency = db.Column(db.String(255))
    typical_session_length = db.Column(Enum(SessionLength, values_callable=lambda x: [e.value for e in x]))
    has_hangboard = db.Column(db.Boolean)
    has_home_wall = db.Column(db.Boolean)
    goes_to_gym = db.Column(db.Boolean)
    
    # Performance metrics
    highest_grade_sport_sent_clean_on_lead = db.Column(db.String(255))
    highest_grade_tr_sent_clean = db.Column(db.String(255))
    highest_grade_trad_sent_clean_on_lead = db.Column(db.String(255))
    highest_grade_boulder_sent_clean = db.Column(db.String(255))
    onsight_grade_sport = db.Column(db.String(255))
    onsight_grade_trad = db.Column(db.String(255))
    flash_grade_boulder = db.Column(db.String(255))
    
    # Grade Pyramids (stored as JSON strings)
    grade_pyramid_sport = db.Column(db.JSON)
    grade_pyramid_trad = db.Column(db.JSON)
    grade_pyramid_boulder = db.Column(db.JSON)
    
    # Injury history and limitations
    current_injuries = db.Column(db.Text)
    injury_history = db.Column(db.Text)
    physical_limitations = db.Column(db.Text)
    
    # Goals and preferences
    climbing_goals = db.Column(db.Text)
    willing_to_train_indoors = db.Column(db.Boolean)
    
    # Recent activity
    sends_last_30_days = db.Column(db.Integer)
    current_projects = db.Column(db.JSON)  # List of current projects stored as JSON
    
    # Style preferences
    favorite_angle = db.Column(Enum(ClimbingStyle, values_callable=lambda x: [e.value for e in x]))
    favorite_hold_types = db.Column(Enum(HoldType, values_callable=lambda x: [e.value for e in x]))
    weakest_style = db.Column(Enum(ClimbingStyle, values_callable=lambda x: [e.value for e in x]))
    strongest_style = db.Column(Enum(ClimbingStyle, values_callable=lambda x: [e.value for e in x]))
    favorite_energy_type = db.Column(Enum(RouteCharacteristic, values_callable=lambda x: [e.value for e in x]))

    #Lifestyle
    sleep_score = db.Column(Enum(SleepScore, values_callable=lambda x: [e.value for e in x]))
    nutrition_score = db.Column(Enum(NutritionScore, values_callable=lambda x: [e.value for e in x]))

    #Favorite Routes
    recent_favorite_routes = db.Column(db.JSON) #List of latest 10 routes with 5 stars and notes

    #additional notes
    additional_notes = db.Column(db.Text)

    # Metadata
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    current_info_as_of = db.Column(db.DateTime, server_default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
