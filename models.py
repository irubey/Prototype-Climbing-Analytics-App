from flask_sqlalchemy import SQLAlchemy
from datetime import date
import json

db = SQLAlchemy()

class BaseModel(db.Model):
    __abstract__ = True  

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class UserMeta(BaseModel):
    __tablename__ = 'user_meta'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    user_ticks = db.relationship('UserTicks', back_populates='user')


class Locations(BaseModel):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(255))
    gps = db.Column(db.Integer)
    gym_crag = db.Column(db.Boolean)
    area_group = db.Column(db.String(255))
    routes = db.relationship('Routes', back_populates='location')


class GradeCode(BaseModel):
    __tablename__ = 'grade_order_dict'
    code = db.Column(db.Integer, primary_key=True)
    grade = db.Column(db.String(50), nullable=False)
    routes = db.relationship('Routes', back_populates='grade')


class Routes(BaseModel):
    __tablename__ = 'routes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    location = db.relationship('Locations', back_populates='routes')
    length = db.Column(db.Integer)
    character = db.Column(db.String(255))
    style = db.Column(db.String(255))
    grade_code = db.Column(db.Integer, db.ForeignKey('grade_order_dict.code'))
    grade = db.relationship('GradeCode', back_populates='routes')
    discipline = db.Column(db.String(255))
    quality = db.Column(db.Float)
    tags = db.relationship('Tags', secondary='route_tags', back_populates='routes')


class Tags(BaseModel):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    tag_name = db.Column(db.String(100), unique=True)
    routes = db.relationship('Routes', secondary='route_tags', back_populates='tags')


class UserTicks(BaseModel):
    __tablename__ = 'user_ticks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_meta.id'))
    user = db.relationship('UserMeta', back_populates='user_ticks')

    route_id = db.Column(db.Integer, db.ForeignKey('routes.id'))
    agg_route = db.relationship('Routes')  # Aggregate route information

    # User-specific fields
    tick_date = db.Column(db.Date, nullable=False)
    tick_route_name = db.Column(db.String(255), nullable = False)
    tick_route_length = db.Column(db.Integer)
    num_attempts = db.Column(db.Integer)
    num_sends = db.Column(db.Integer)
    tick_route_grade = db.Column(db.String(255))
    tick_route_style = db.Column(db.String(255))
    tick_route_character = db.Column(db.String(255))
    tick_discipline = db.Column(db.String(255))
    tick_route_quality = db.Column(db.Float)
    tick_location = db.Column(db.String(255))
    tick_notes = db.Column(db.String(255))
    tick_tags = db.Column(db.String(255))


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.strftime('%Y-%m-%d') 
        return super(CustomJSONEncoder, self).default(obj)
