from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, TextAreaField, IntegerField, DateField, SelectMultipleField
from wtforms.validators import DataRequired, Email, EqualTo, Optional, NumberRange, InputRequired, ValidationError
from app.models import (ClimbingDiscipline, SessionLength, CruxAngle,
                       CruxEnergyType, HoldType, SleepScore, NutritionScore)
from app.services.grade_processor import GradeProcessor
from datetime import date


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    mtn_project_profile_url = StringField('Mountain Project Profile URL')
    submit = SubmitField('Sign Up')

class ClimberSummaryForm(FlaskForm):
    # Core Context
    climbing_goals = TextAreaField('Climbing Goals', validators=[Optional()])
    years_climbing = IntegerField('Years Climbing', validators=[Optional(), NumberRange(min=0)])
    current_training_description = TextAreaField('Current Training Description', validators=[Optional()])
    interests = SelectMultipleField('Interests', 
        choices=[
            ('outdoor_sport', 'Outdoor Sport'),
            ('indoor_sport', 'Indoor Sport'),
            ('outdoor_trad', 'Outdoor Trad'),
            ('indoor_tr', 'Indoor Top Rope'),
            ('outdoor_boulder', 'Outdoor Boulder'),
            ('indoor_boulder', 'Indoor Boulder'),
            ('board_climbing', 'Board Climbing'),
            ('competition_boulder', 'Competition Boulder'),
            ('alpine_multipitch', 'Alpine Multipitch'),
            ('sport_multipitch', 'Sport Multipitch'),
            ('trad_multipitch', 'Trad Multipitch')
        ],
        validators=[Optional()])
    injury_information = TextAreaField('Injury Information', validators=[Optional()])
    additional_notes = TextAreaField('Additional Notes', validators=[Optional()])

    # Experience Base Metrics
    total_climbs = IntegerField('Total Climbs', validators=[Optional(), NumberRange(min=0)])
    favorite_discipline = SelectField('Favorite Discipline', 
        choices=[(d.name, d.value) for d in ClimbingDiscipline],
        validators=[Optional()])
    preferred_crag_last_year = StringField('Preferred Crag Last Year', validators=[Optional()])

    # Performance Metrics
    highest_sport_grade_tried = StringField('Highest Sport Grade Tried', validators=[Optional()])
    highest_trad_grade_tried = StringField('Highest Trad Grade Tried', validators=[Optional()])
    highest_boulder_grade_tried = StringField('Highest Boulder Grade Tried', validators=[Optional()])
    highest_grade_sport_sent_clean_on_lead = StringField('Highest Sport Lead Send', validators=[Optional()])
    highest_grade_tr_sent_clean = StringField('Highest TR Send', validators=[Optional()])
    highest_grade_trad_sent_clean_on_lead = StringField('Highest Trad Lead Send', validators=[Optional()])
    highest_grade_boulder_sent_clean = StringField('Highest Boulder Send', validators=[Optional()])
    onsight_grade_sport = StringField('Sport Onsight Grade', validators=[Optional()])
    onsight_grade_trad = StringField('Trad Onsight Grade', validators=[Optional()])
    flash_grade_boulder = StringField('Boulder Flash Grade', validators=[Optional()])

    # Training Context
    current_training_frequency = SelectField('Training Frequency', 
        choices=[
            ('1-2x/week', '1-2x/week'),
            ('2-3x/week', '2-3x/week'),
            ('3-4x/week', '3-4x/week'),
            ('4-5x/week', '4-5x/week'),
            ('5+/week', '5+/week')
        ],
        validators=[Optional()])
    typical_session_length = SelectField('Typical Session Length',
        choices=[(s.name, s.value) for s in SessionLength],
        validators=[Optional()])
    typical_session_intensity = SelectField('Session Intensity',
        choices=[
            ('Light', 'Light'),
            ('Moderate', 'Moderate'),
            ('Hard', 'Hard'),
            ('Very Hard', 'Very Hard')
        ],
        validators=[Optional()])
    home_equipment = TextAreaField('Home Equipment', validators=[Optional()])
    access_to_commercial_gym = BooleanField('Access to Commercial Gym')
    supplemental_training = TextAreaField('Supplemental Training', validators=[Optional()])
    training_history = TextAreaField('Training History', validators=[Optional()])

    # Lifestyle
    physical_limitations = TextAreaField('Physical Limitations', validators=[Optional()])
    sleep_score = SelectField('Sleep Quality',
        choices=[(s.name, s.value) for s in SleepScore],
        validators=[Optional()])
    nutrition_score = SelectField('Nutrition Quality',
        choices=[(n.name, n.value) for n in NutritionScore],
        validators=[Optional()])

    # Recent Activity
    activity_last_30_days = IntegerField('Activity Last 30 Days', validators=[Optional(), NumberRange(min=0)])

    # Style Preferences
    favorite_angle = SelectField('Favorite Angle',
        choices=[(a.name, a.value) for a in CruxAngle],
        validators=[Optional()])
    strongest_angle = SelectField('Strongest Angle',
        choices=[(a.name, a.value) for a in CruxAngle],
        validators=[Optional()])
    weakest_angle = SelectField('Weakest Angle',
        choices=[(a.name, a.value) for a in CruxAngle],
        validators=[Optional()])
    favorite_energy_type = SelectField('Preferred Energy System',
        choices=[(e.name, e.value) for e in CruxEnergyType],
        validators=[Optional()])
    strongest_energy_type = SelectField('Strongest Energy System',
        choices=[(e.name, e.value) for e in CruxEnergyType],
        validators=[Optional()])
    weakest_energy_type = SelectField('Weakest Energy System',
        choices=[(e.name, e.value) for e in CruxEnergyType],
        validators=[Optional()])
    favorite_hold_types = SelectField('Favorite Hold Type',
        choices=[(h.name, h.value) for h in HoldType],
        validators=[Optional()])
    strongest_hold_types = SelectField('Strongest Hold Type',
        choices=[(h.name, h.value) for h in HoldType],
        validators=[Optional()])
    weakest_hold_types = SelectField('Weakest Hold Type',
        choices=[(h.name, h.value) for h in HoldType],
        validators=[Optional()])

    submit = SubmitField('Save Profile')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set empty default for optional selects
        for field in self.__class__.__dict__.items():
            if isinstance(field[1], SelectField):
                field[1].choices.insert(0, ('', 'Not Specified'))

    def validate_grade_fields(self, field):
        """Validate climbing grade format"""
        if not field.data:
            return
        grade_processor = GradeProcessor()
        valid_grades = grade_processor.routes_grade_list + grade_processor.boulders_grade_list
        if field.data not in valid_grades:
            raise ValidationError('Invalid climbing grade format')


class LogbookConnectionForm(FlaskForm):
    profile_url = StringField('Mountain Project Profile URL', 
        validators=[
            DataRequired(message="Please enter a Mountain Project profile URL"),
            # Custom validator for Mountain Project URL format
        ])
    submit = SubmitField('Analyze')

    def validate_profile_url(self, field):
        """Validate Mountain Project URL format"""
        if not field.data:
            return
            
        value = field.data.strip()
        if not value.startswith(('http://', 'https://')):
            value = 'https://' + value
            field.data = value

        if 'mountainproject.com/user/' not in value.lower():
            raise ValidationError('Please enter a valid Mountain Project profile URL')

        try:
            url_parts = value.split('/')
            user_idx = url_parts.index('user')
            user_id = url_parts[user_idx + 1]
            if not user_id or not user_id.isdigit():
                raise ValidationError('Invalid Mountain Project URL format')
        except (ValueError, IndexError):
            raise ValidationError('Invalid Mountain Project URL format')
 