from app import db

class BaseModel(db.Model):
    __abstract__ = True  

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class BinnedCodeDict(BaseModel):
    __tablename__ = 'binned_code_dict'
    binned_code = db.Column(db.Integer, primary_key=True)
    binned_grade = db.Column(db.String(50), nullable=False)

class BoulderPyramid(BaseModel):
    __tablename__ = 'boulder_pyramid'
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
    discipline = db.Column(db.String(255))
    length_category = db.Column(db.String(255))
    season_category = db.Column(db.String(255))
    route_url = db.Column(db.String(255))
    user_grade = db.Column(db.String(255))
    username = db.Column(db.String(255))
    route_characteristic = db.Column(db.String(255))
    num_attempts = db.Column(db.Integer)
    route_style = db.Column(db.String(255))

class SportPyramid(BaseModel):
    __tablename__ = 'sport_pyramid'
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
    discipline = db.Column(db.String(255))
    length_category = db.Column(db.String(255))
    season_category = db.Column(db.String(255))
    route_url = db.Column(db.String(255))
    user_grade = db.Column(db.String(255))
    username = db.Column(db.String(255))
    route_characteristic = db.Column(db.String(255))
    num_attempts = db.Column(db.Integer)
    route_style = db.Column(db.String(255))

class TradPyramid(BaseModel):
    __tablename__ = 'trad_pyramid'
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
    discipline = db.Column(db.String(255))
    length_category = db.Column(db.String(255))
    season_category = db.Column(db.String(255))
    route_url = db.Column(db.String(255))
    user_grade = db.Column(db.String(255))
    username = db.Column(db.String(255))
    route_characteristic = db.Column(db.String(255))
    num_attempts = db.Column(db.Integer)
    route_style = db.Column(db.String(255))

class UserTicks(BaseModel):
    __tablename__ = 'user_ticks'
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
    discipline = db.Column(db.String(255))
    send_bool = db.Column(db.Boolean)
    length_category = db.Column(db.String(255))
    season_category = db.Column(db.String(255))
    username = db.Column(db.String(255))
    route_url = db.Column(db.String(255)) 