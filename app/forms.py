from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, TextAreaField, IntegerField, DateField
from wtforms.validators import DataRequired, Email, EqualTo, Optional, NumberRange, validators
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
    favorite_discipline = SelectField('Favorite Discipline', 
        choices=[(d.name, d.value) for d in ClimbingDiscipline] + [('', 'Not Specified')],
        validators=[Optional()])
    years_climbing_outside = IntegerField('Years Climbing Outside',
        validators=[Optional(), NumberRange(min=0)])
    preferred_crag_last_year = StringField('Preferred Crag Last Year')

    # Training Context
    training_frequency = SelectField('Training Frequency',
        choices=[
            ('', 'Select Frequency'),
            ('1-2x', '1-2 Times/Week'),
            ('3-4x', '3-4 Times/Week'),
            ('5+', '5+ Times/Week')
        ], validators=[Optional()])
    typical_session_length = SelectField('Typical Session Length',
        choices=[(s.name, s.value) for s in SessionLength] + [('', 'Not Specified')],
        validators=[Optional()])
    has_hangboard = BooleanField('Do you have a hangboard?')
    has_home_wall = BooleanField('Do you have a home wall?')
    goes_to_gym = BooleanField('Do you regularly climb at a gym?')

    # Injury History
    current_injuries = TextAreaField('Current Injuries')
    injury_history = TextAreaField('Past Injuries')
    physical_limitations = TextAreaField('Physical Limitations')

    # Goals and Preferences
    climbing_goals = TextAreaField('Climbing Goals', validators=[Optional()])
    willing_to_train_indoors = BooleanField('Willing to train indoors?')

    # Style Preferences
    favorite_angle = SelectField('Favorite Angle',
        choices=[(a.name, a.value) for a in CruxAngle] + [('', 'Not Specified')],
        validators=[Optional()])
    strongest_angle = SelectField('Strongest Angle',
        choices=[(a.name, a.value) for a in CruxAngle] + [('', 'Not Specified')],
        validators=[Optional()])
    weakest_angle = SelectField('Weakest Angle',
        choices=[(a.name, a.value) for a in CruxAngle] + [('', 'Not Specified')],
        validators=[Optional()])
    favorite_energy_type = SelectField('Preferred Energy System',
        choices=[(e.name, e.value) for e in CruxEnergyType] + [('', 'Not Specified')],
        validators=[Optional()])
    favorite_hold_types = SelectField('Favorite Hold Type',
        choices=[(h.name, h.value) for h in HoldType] + [('', 'Not Specified')],
        validators=[Optional()])

    # Lifestyle
    sleep_score = SelectField('Sleep Quality',
        choices=[(s.name, s.value) for s in SleepScore] + [('', 'Not Specified')],
        validators=[Optional()])
    nutrition_score = SelectField('Nutrition Quality',
        choices=[(n.name, n.value) for n in NutritionScore] + [('', 'Not Specified')],
        validators=[Optional()])

    # Additional Notes
    additional_notes = TextAreaField('Additional Notes')

    submit = SubmitField('Save Profile')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set empty default for optional selects
        for field in [self.favorite_discipline, self.typical_session_length,
                    self.favorite_angle, self.strongest_angle, self.weakest_angle,
                    self.favorite_energy_type, self.favorite_hold_types,
                    self.sleep_score, self.nutrition_score]:
            field.choices.insert(0, ('', 'Not Specified'))


class PyramidEntryForm(FlaskForm):
    # Required fields
    route_name = StringField('Route Name', validators=[validators.DataRequired()])
    discipline = SelectField('Discipline', choices=[
        ('', 'Select Discipline'),
        ('sport', 'Sport'),
        ('trad', 'Trad'), 
        ('boulder', 'Boulder')
    ], validators=[validators.DataRequired()])
    route_grade = StringField('Route Grade', validators=[validators.DataRequired()])
    
    # Optional fields with validation
    first_send_date = DateField('First Send Date', default=date.today(),
                               validators=[validators.Optional()])
    length = IntegerField('Length (meters)', validators=[
        validators.Optional(),
        validators.NumberRange(min=0, max=1000)
    ])
    num_attempts = IntegerField('Attempts', default=1, validators=[
        validators.NumberRange(min=1)
    ])
    num_sends = IntegerField('Sends', default=1, validators=[
        validators.NumberRange(min=1)
    ])
    crux_energy = SelectField('Crux Energy Type',
        choices=[(e.name, e.value) for e in CruxEnergyType] + [('', 'Not Specified')],
        validators=[validators.Optional()])
    crux_angle = SelectField('Crux Angle',
        choices=[(a.name, a.value) for a in CruxAngle] + [('', 'Not Specified')],
        validators=[validators.Optional()])
    location = StringField('Location')
    
    submit = SubmitField('Save Route')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add empty option to selects
        for field in [self.crux_energy, self.crux_angle]:
            field.choices.insert(0, ('', 'Not Specified'))
            
    def validate_route_grade(self, field):
        """Validate grade using GradeProcessor"""
        grade = field.data
        valid_grades = GradeProcessor().routes_grade_list + GradeProcessor().boulders_grade_list
        if grade not in valid_grades:
            raise validators.ValidationError('Invalid climbing grade format')