from app import db,  bcrypt
from sqlalchemy import Enum
from flask_login import UserMixin
import enum
from datetime import datetime, UTC, timezone
from sqlalchemy.sql import text
from sqlalchemy.dialects.postgresql import UUID
import uuid



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
        db.Index('ix_user_mtn_project', 'mtn_project_profile_url')
    )
    
    # Core Authentication
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    mtn_project_profile_url = db.Column(db.String(255), unique=True)
    mtn_project_last_sync = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)
    
    # Relationships
    climber_summary = db.relationship('ClimberSummary', backref='user', uselist=False)
    uploads = db.relationship('UserUpload', backref='user', lazy='dynamic')
    ticks = db.relationship('UserTicks', backref='user', lazy='dynamic', foreign_keys='UserTicks.user_id')
    performance_pyramids = db.relationship('PerformancePyramid', backref='user', lazy='dynamic', foreign_keys='PerformancePyramid.user_id')
    
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
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255))
    file_size = db.Column(db.Integer)  # Track size for 1MB/10MB limits
    file_type = db.Column(db.String(10))  # 'txt' or 'csv'
    content = db.Column(db.Text)  # Raw text storage for MVP
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))    

class PerformancePyramid(BaseModel):
    __tablename__ = 'performance_pyramid'
    __table_args__ = (
        db.Index('idx_performance_pyramid_send_date', 'send_date'),
        db.Index('idx_performance_pyramid_user_id', 'user_id'),
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    tick_id = db.Column(db.ForeignKey('user_ticks.id'), nullable=False)
    send_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(255))
    crux_angle = db.Column(Enum(CruxAngle))
    crux_energy = db.Column(Enum(CruxEnergyType))
    binned_code = db.Column(db.Integer, nullable=False)
    num_attempts = db.Column(db.Integer)
    days_attempts = db.Column(db.Integer)
    description = db.Column(db.Text)

class UserTicks(BaseModel):
    __tablename__ = 'user_ticks'
    __table_args__ = (
        db.Index('ix_user_ticks_compound', 'user_id', 'tick_date'),  # UUID + date composite index
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
    
    # Settings - Core Context additions
    climbing_goals = db.Column(db.Text)
    years_climbing = db.Column(db.Integer)
    current_training_description = db.Column(db.Text)
    interests = db.Column(db.JSON)
    injury_information = db.Column(db.Text)
    additional_notes = db.Column(db.Text)
    
    # Advanced Settings - Experience Base Metrics
    total_climbs = db.Column(db.Integer)
    favorite_discipline = db.Column(Enum(ClimbingDiscipline))
    preferred_crag_last_year = db.Column(db.String(255))
    

    # Advanced Settings - Performance Metrics 
    highest_sport_grade_tried = db.Column(db.String(255))
    highest_trad_grade_tried = db.Column(db.String(255))
    highest_boulder_grade_tried = db.Column(db.String(255))
    highest_grade_sport_sent_clean_on_lead = db.Column(db.String(255))
    highest_grade_tr_sent_clean = db.Column(db.String(255))
    highest_grade_trad_sent_clean_on_lead = db.Column(db.String(255))
    highest_grade_boulder_sent_clean = db.Column(db.String(255))
    onsight_grade_sport = db.Column(db.String(255))
    onsight_grade_trad = db.Column(db.String(255))
    flash_grade_boulder = db.Column(db.String(255))
    grade_pyramid_sport = db.Column(db.JSON)
    grade_pyramid_trad = db.Column(db.JSON)
    grade_pyramid_boulder = db.Column(db.JSON)
    
    # Advanced Settings - Training Context modifications
    current_training_frequency = db.Column(db.String(255))  # Renamed from training_frequency
    typical_session_length = db.Column(Enum(SessionLength, values_callable=lambda x: [e.value for e in x]))
    typical_session_intensity = db.Column(db.String(255))  # New Field
    home_equipment = db.Column(db.Text)  # New Field replacing has_hangboard and has_home_wall
    access_to_commercial_gym = db.Column(db.Boolean, default=False)  # Renamed from goes_to_gym
    supplemental_training = db.Column(db.Text)  # New Field
    training_history = db.Column(db.Text)  # New Field
    
    # Advanced Settings - Lifestyle
    physical_limitations = db.Column(db.Text)
    sleep_score = db.Column(Enum(SleepScore, values_callable=lambda x: [e.value for e in x]))
    nutrition_score = db.Column(Enum(NutritionScore, values_callable=lambda x: [e.value for e in x]))
    
    
    # Advanced Settings - Recent Activity 
    activity_last_30_days = db.Column(db.Integer)
    current_projects = db.Column(db.JSON)
    recent_favorite_routes = db.Column(db.JSON)
    
    # Advanced Settings - Style Preferences
    favorite_angle = db.Column(Enum(CruxAngle, values_callable=lambda x: [e.value for e in x]))
    weakest_angle = db.Column(Enum(CruxAngle, values_callable=lambda x: [e.value for e in x]))
    strongest_angle = db.Column(Enum(CruxAngle, values_callable=lambda x: [e.value for e in x]))
    favorite_energy_type = db.Column(Enum(CruxEnergyType, values_callable=lambda x: [e.value for e in x]))
    weakest_energy_type = db.Column(Enum(CruxEnergyType, values_callable=lambda x: [e.value for e in x]))
    strongest_energy_type = db.Column(Enum(CruxEnergyType, values_callable=lambda x: [e.value for e in x]))
    favorite_hold_types = db.Column(Enum(HoldType, values_callable=lambda x: [e.value for e in x]))
    weakest_hold_types = db.Column(Enum(HoldType, values_callable=lambda x: [e.value for e in x]))
    strongest_hold_types = db.Column(Enum(HoldType, values_callable=lambda x: [e.value for e in x]))
    

    # Metadata
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    current_info_as_of = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
