from app import db,  bcrypt
from sqlalchemy import Enum
from flask_login import UserMixin
import enum
from datetime import datetime, UTC, timezone
from werkzeug.security import generate_password_hash, check_password_hash



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
    
class CruxAngle(enum.Enum):
    Slab = "Slab"
    Vertical = "Vertical"
    Overhang = "Overhang"
    Roof = "Roof"

class CruxEnergyType(enum.Enum):
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

#----------------------------------

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

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        db.Index('idx_user_id', 'id'),
        db.Index('idx_user_username', 'username'),
    db.Index('ix_user_tier', 'tier'),
    db.Index('ix_user_mtn_project', 'mtn_project_profile_url'),
    )
    
    # Core Authentication
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    
    # Payment & Subscription
    stripe_customer_id = db.Column(db.String(255))
    stripe_subscription_id = db.Column(db.String(255))
    tier = db.Column(db.String(20), default='basic')  # 'basic' or 'premium'
    payment_status = db.Column(db.String(20), default='unpaid')  # 'unpaid | pending | active'
    last_payment_check = db.Column(db.DateTime)
    stripe_webhook_verified = db.Column(db.Boolean, default=False)
    
    # Usage Tracking
    daily_message_count = db.Column(db.Integer, default=0)
    last_message_date = db.Column(db.Date)
    
    # Mountain Project Integration
    mtn_project_profile_url = db.Column(db.String(255))
    mtn_project_last_sync = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)
    
    # Relationships
    climber_summary = db.relationship('ClimberSummary', backref='user', uselist=False)
    uploads = db.relationship('UserUpload', backref='user', lazy='dynamic')
    boulder_pyramids = db.relationship('BoulderPyramid', backref='user', lazy='dynamic', foreign_keys='BoulderPyramid.user_id')
    sport_pyramids = db.relationship('SportPyramid', backref='user', lazy='dynamic', foreign_keys='SportPyramid.user_id')
    trad_pyramids = db.relationship('TradPyramid', backref='user', lazy='dynamic', foreign_keys='TradPyramid.user_id')
    ticks = db.relationship('UserTicks', backref='user', lazy='dynamic', foreign_keys='UserTicks.user_id')
    
    def get_id(self):
        return str(self.id)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class UserUpload(db.Model):
    __tablename__ = 'user_uploads'
    __table_args__ = (
        db.Index('idx_user_uploads_user_id', 'user_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    filename = db.Column(db.String(255))
    file_size = db.Column(db.Integer)  # Track size for 1MB/10MB limits
    file_type = db.Column(db.String(10))  # 'txt' or 'csv'
    content = db.Column(db.Text)  # Raw text storage for MVP
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))    


class BoulderPyramid(BaseModel):
    __tablename__ = 'boulder_pyramid'
    __table_args__ = (
        db.Index('idx_boulder_pyramid_tick_date', 'tick_date'),
        db.Index('idx_boulder_pyramid_user_id', 'user_id'),
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.ForeignKey('users.id'))
    tick_id = db.Column(db.ForeignKey('user_ticks.id'))
    route_name = db.Column(db.String(255))
    first_send_date = db.Column(db.Date)
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
    crux_energy = db.Column(Enum(CruxEnergyType))
    num_attempts = db.Column(db.Integer)
    num_sends = db.Column(db.Integer)
    crux_angle = db.Column(Enum(CruxAngle))

class SportPyramid(BaseModel):
    __tablename__ = 'sport_pyramid'
    __table_args__ = (
        db.Index('idx_sport_pyramid_tick_date', 'tick_date'),
        db.Index('idx_sport_pyramid_user_id', 'user_id'),
        db.Index('idx_sport_pyramid_lookup', 'user_id', 'route_name', 'tick_date'),
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tick_id = db.Column(db.ForeignKey('user_ticks.id'))
    user_id = db.Column(db.ForeignKey('users.id'))
    route_name = db.Column(db.String(255))
    first_send_date = db.Column(db.Date)
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
    crux_energy = db.Column(Enum(CruxEnergyType))
    num_attempts = db.Column(db.Integer)
    num_sends = db.Column(db.Integer)
    crux_angle = db.Column(Enum(CruxAngle))

class TradPyramid(BaseModel):
    __tablename__ = 'trad_pyramid'
    __table_args__ = (
        db.Index('idx_trad_pyramid_tick_date', 'tick_date'),
        db.Index('idx_trad_pyramid_user_id', 'user_id'),
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tick_id = db.Column(db.ForeignKey('user_ticks.id'))
    user_id = db.Column(db.ForeignKey('users.id'))
    route_name = db.Column(db.String(255))
    first_send_date = db.Column(db.Date)
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
    crux_energy = db.Column(Enum(CruxEnergyType))
    num_attempts = db.Column(db.Integer)
    num_sends = db.Column(db.Integer)
    crux_angle = db.Column(Enum(CruxAngle))

class UserTicks(BaseModel):
    __tablename__ = 'user_ticks'
    __table_args__ = (
        db.Index('idx_user_ticks_tick_date', 'tick_date'),
        db.Index('idx_user_ticks_user_id', 'user_id'),
        db.Index('idx_user_ticks_lookup', 'user_id', 'route_name', 'tick_date'),
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False)
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
    route_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    notes = db.Column(db.Text)
    route_stars = db.Column(db.Float)
    user_stars = db.Column(db.Float)


class ClimberSummary(BaseModel):
    __tablename__ = 'climber_summary'
    __table_args__ = (
        db.Index('idx_climber_summary_user_id', 'user_id'),
    )
    
    # Primary Key
    user_id = db.Column(db.ForeignKey('users.id'), primary_key=True)
    
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
    favorite_angle = db.Column(Enum(CruxAngle, values_callable=lambda x: [e.value for e in x]))
    weakest_angle = db.Column(Enum(CruxAngle, values_callable=lambda x: [e.value for e in x]))
    strongest_angle = db.Column(Enum(CruxAngle, values_callable=lambda x: [e.value for e in x]))
    favorite_energy_type = db.Column(Enum(CruxEnergyType, values_callable=lambda x: [e.value for e in x]))
    weakest_energy_type = db.Column(Enum(CruxEnergyType, values_callable=lambda x: [e.value for e in x]))
    strongest_energy_type = db.Column(Enum(CruxEnergyType, values_callable=lambda x: [e.value for e in x]))
    favorite_hold_types = db.Column(Enum(HoldType, values_callable=lambda x: [e.value for e in x]))
    weakest_hold_types = db.Column(Enum(HoldType, values_callable=lambda x: [e.value for e in x]))
    strongest_hold_types = db.Column(Enum(HoldType, values_callable=lambda x: [e.value for e in x]))

    #Lifestyle
    sleep_score = db.Column(Enum(SleepScore, values_callable=lambda x: [e.value for e in x]))
    nutrition_score = db.Column(Enum(NutritionScore, values_callable=lambda x: [e.value for e in x]))

    #Favorite Routes
    recent_favorite_routes = db.Column(db.JSON) #List of latest 10 routes with 5 stars and notes

    #additional notes
    additional_notes = db.Column(db.Text)

    # Metadata
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    current_info_as_of = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
