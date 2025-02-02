from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, TextAreaField, IntegerField, DateField
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
    # Core Progression Metrics
    highest_sport_grade_tried = StringField('Highest Sport Grade Tried')
    highest_trad_grade_tried = StringField('Highest Trad Grade Tried')
    highest_boulder_grade_tried = StringField('Highest Boulder Grade Tried')
    total_climbs = IntegerField('Total Climbs', validators=[Optional(), NumberRange(min=0)])
    favorite_discipline = SelectField('Favorite Discipline', 
        choices=[(d.name, d.value) for d in ClimbingDiscipline],
        validators=[Optional()])
    years_climbing_outside = IntegerField('Years Climbing Outside',
        validators=[Optional(), NumberRange(min=0)])
    preferred_crag_last_year = StringField('Preferred Crag Last Year')

    # Training Context
    training_frequency = StringField('Training Frequency')
    typical_session_length = SelectField('Typical Session Length',
        choices=[(s.name, s.value) for s in SessionLength],
        validators=[Optional()])
    has_hangboard = BooleanField('Do you have a hangboard?')
    has_home_wall = BooleanField('Do you have a home wall?')
    goes_to_gym = BooleanField('Do you regularly climb at a gym?')

    # Performance Metrics
    highest_grade_sport_sent_clean_on_lead = StringField('Highest Sport Lead Send')
    highest_grade_tr_sent_clean = StringField('Highest TR Send')
    highest_grade_trad_sent_clean_on_lead = StringField('Highest Trad Lead Send')
    highest_grade_boulder_sent_clean = StringField('Highest Boulder Send')
    onsight_grade_sport = StringField('Sport Onsight Grade')
    onsight_grade_trad = StringField('Trad Onsight Grade')
    flash_grade_boulder = StringField('Boulder Flash Grade')

    # Injury History
    current_injuries = TextAreaField('Current Injuries')
    injury_history = TextAreaField('Past Injuries')
    physical_limitations = TextAreaField('Physical Limitations')

    # Goals and Preferences
    climbing_goals = TextAreaField('Climbing Goals', validators=[Optional()])
    willing_to_train_indoors = BooleanField('Willing to train indoors?')

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

    # Lifestyle
    sleep_score = SelectField('Sleep Quality',
        choices=[(s.name, s.value) for s in SleepScore],
        validators=[Optional()])
    nutrition_score = SelectField('Nutrition Quality',
        choices=[(n.name, n.value) for n in NutritionScore],
        validators=[Optional()])

    # Additional Notes
    additional_notes = TextAreaField('Additional Notes')

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
 