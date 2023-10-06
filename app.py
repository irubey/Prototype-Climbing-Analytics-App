from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, and_
from sqlalchemy.orm.exc import NoResultFound
from initial_calculations import perform_calculations
import pandas as pd
import json
from datetime import date
from collections import defaultdict
import os
from dotenv import load_dotenv

#load environmental variables
load_dotenv()


app = Flask(__name__)
app.static_folder = 'static'


#Debug Setup
if os.environ.get("FLASK_ENV") == "production":
    app.config["DEBUG"] = False
else:
    app.config["DEBUG"] = True

#Database Setup
database_url = os.getenv("DATABASE_URL")
#Replace postgres:// with postgresql:// in the URL
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

#Class Setup for SQL tables
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
    lead_style = db.Column(db.String(255))
    cur_max_rp_sport = db.Column(db.Integer)
    cur_max_rp_trad = db.Column(db.Integer)
    cur_max_boulder = db.Column(db.Integer)
    difficulty_category = db.Column(db.String(255))
    discipline = db.Column(db.String(255))
    send_bool = db.Column(db.Boolean) # tinyint(1) typically maps to Boolean
    length_category = db.Column(db.String(255))
    season_category = db.Column(db.String(255))
    username = db.Column(db.String(255))
    route_url = db.Column(db.String(255))

class_dict = {
    'user_ticks': UserTicks,
    'sport_pyramid': SportPyramid,
    'trad_pyramid': TradPyramid,
    'boulder_pyramid': BoulderPyramid,
    'binned_code_dict': BinnedCodeDict
}

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')  # format the date as you see fit
        return super(CustomJSONEncoder, self).default(obj)

#Helper Functions

def update_row_in_table(table_name, row_id, data):
    # Fetch the table class from the class_dict using table_name
    model_class = class_dict.get(table_name)
    if not model_class:
        raise ValueError(f"No model found for table name: {table_name}")

    try:
        # Query for the row with the given row_id
        instance = db.session.query(model_class).filter_by(id=row_id).one()

        # Update the attributes of the instance
        for key, value in data.items():
            setattr(instance, key, value)

        # Commit the changes
        db.session.commit()
        
    except NoResultFound:
        raise ValueError(f"No row found in {table_name} with id {row_id}")

    except AttributeError as e:
        raise ValueError(f"Invalid attribute for table {table_name}: {e}")

def update_calculated_data(calculated_data):

    def save_dataframe_to_table(df, table_name):
        model_class = class_dict.get(table_name)
        if not model_class:
            raise ValueError(f"No model found for table name: {table_name}")

        for _, row in df.iterrows():
            data_dict = row.where(pd.notnull(row), None).to_dict()

            # Check if a row with the given username, route_name, and tick_date already exists
            exists = db.session.query(model_class).filter_by(
                username=data_dict['username'],
                route_name=data_dict['route_name'], 
                tick_date=data_dict['tick_date']
            ).first()

            if not exists:  # If row doesn't exist, then insert it
                new_entry = model_class(**data_dict)
                db.session.add(new_entry)

        db.session.commit()

    save_dataframe_to_table(calculated_data['sport_pyramid'], 'sport_pyramid')
    save_dataframe_to_table(calculated_data['trad_pyramid'], 'trad_pyramid')
    save_dataframe_to_table(calculated_data['boulder_pyramid'], 'boulder_pyramid')
    save_dataframe_to_table(calculated_data['user_ticks'], 'user_ticks')

def retrieve_data_from_table(table_name, username=None):
    ModelClass = class_dict.get(table_name)
    if not ModelClass:
        raise ValueError(f"Unknown table: {table_name}")

    if table_name == 'binned_code_dict':
        data = db.session.query(ModelClass).all()
    else:
        data = db.session.query(ModelClass).filter_by(username=username).all()

    return [convert_to_dict(obj) for obj in data]

def convert_to_dict(obj):
    """Convert an ORM object to a dictionary."""
    return {column.key: getattr(obj, column.key) for column in obj.__table__.columns}

def convert_data_to_json(username):
    def retrieve_and_serialize(model_class, username=None):
        if username:
            records = db.session.query(model_class).filter_by(username=username).all()
        else:
            records = db.session.query(model_class).all()
        return json.dumps([record.as_dict() for record in records], cls=CustomJSONEncoder)

    sport_pyramid = retrieve_and_serialize(SportPyramid, username)
    trad_pyramid = retrieve_and_serialize(TradPyramid, username)
    boulder_pyramid = retrieve_and_serialize(BoulderPyramid, username)
    user_ticks = retrieve_and_serialize(UserTicks, username)
    binned_code_dict = retrieve_and_serialize(BinnedCodeDict)  # No username for this table

    return sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, binned_code_dict


    # Define the tables to clear
    tables_to_clear = [UserTicks, SportPyramid, TradPyramid, BoulderPyramid]
    
    # Iterate through the tables and delete all rows
    for table in tables_to_clear:
        # Use the delete() method to delete all rows from the table
        db.session.query(table).delete()
    
    # Commit the changes to the database
    db.session.commit()

#ROUTES
@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Retrieve first input from the form
        first_input = request.form.get('first_input')

        # Perform calculations on the first input
        sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, username = perform_calculations(first_input)

        # Update the calculated data 
        update_calculated_data({
            'sport_pyramid': sport_pyramid,
            'trad_pyramid': trad_pyramid,
            'boulder_pyramid': boulder_pyramid,
            'user_ticks': user_ticks
        })

        # Redirect the user to the pyramid_input route with the calculated data and first input
        return redirect(url_for('userviz', username=username))

    return render_template('index.html')

@app.route("/terms-privacy")
def terms_and_privacy():
    return render_template('termsAndPrivacy.html')

@app.route("/userviz")
def userviz():
    # Retrieve the username from the query parameters
    username = request.args.get('username')

    return render_template('userViz.html', username = username)

@app.route("/performance-pyramid")
def performance_pyramid():
    # Retrieve the username from the query parameters
    username = request.args.get('username')

    sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, binned_code_dict =convert_data_to_json(username)

    return render_template('performancePyramid.html', username = username, sport_pyramid = sport_pyramid, trad_pyramid = trad_pyramid, boulder_pyramid = boulder_pyramid, user_ticks = user_ticks, binned_code_dict = binned_code_dict)

@app.route("/pyramid-input", methods=['GET', 'POST'])
def pyramid_input():
    if request.method == 'POST':
        form_data = request.form.to_dict(flat=True)
        structured_data = defaultdict(lambda: defaultdict(dict))
        
        # Retrieve the username for redirection, and remove it from form_data
        username = form_data.pop('username', None)

        for key, value in form_data.items():
            parts = key.split('_')
            pyramid_prefix = parts[0]  # Get the prefix like sport, trad, or boulder
            attribute = '_'.join(parts[1:-1])
            row_id = parts[-1]
            structured_data[pyramid_prefix][row_id][attribute] = value

        # Update the database with the structured data
        for pyramid_prefix, pyramid_data in structured_data.items():
            for row_id, data in pyramid_data.items():
                update_row_in_table(f'{pyramid_prefix}_pyramid', row_id, data)

        return redirect(url_for('performance_characteristics', username=username))

    username = request.args.get('username')
    sport_pyramid = retrieve_data_from_table('sport_pyramid', username)
    trad_pyramid = retrieve_data_from_table('trad_pyramid', username)
    boulder_pyramid = retrieve_data_from_table('boulder_pyramid', username)
    

    return render_template('pyramidInputs.html', username=username, sport_pyramid=sport_pyramid, trad_pyramid=trad_pyramid, boulder_pyramid=boulder_pyramid)

@app.route("/performance-characteristics")
def performance_characteristics():
    # Retrieve the username from the query parameters
    username = request.args.get('username')

    sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, binned_code_dict =convert_data_to_json(username)

    return render_template('performanceCharacteristics.html', username = username, sport_pyramid = sport_pyramid, trad_pyramid = trad_pyramid, boulder_pyramid = boulder_pyramid, user_ticks = user_ticks, binned_code_dict = binned_code_dict)

@app.route("/base-volume")
def base_volume():
    # Retrieve the username from the query parameters
    username = request.args.get('username')

    sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, binned_code_dict =convert_data_to_json(username)

    return render_template('baseVolume.html', username = username, sport_pyramid = sport_pyramid, trad_pyramid = trad_pyramid, boulder_pyramid = boulder_pyramid, user_ticks = user_ticks, binned_code_dict = binned_code_dict)

@app.route("/when-where")
def when_where():
    # Retrieve the username from the query parameters
    username = request.args.get('username')

    sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, binned_code_dict =convert_data_to_json(username)

    return render_template('whenWhere.html', username = username, sport_pyramid = sport_pyramid, trad_pyramid = trad_pyramid, boulder_pyramid = boulder_pyramid, user_ticks = user_ticks, binned_code_dict = binned_code_dict)

@app.route("/progression")
def progression():
    # Retrieve the username from the query parameters
    username = request.args.get('username')

    sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, binned_code_dict =convert_data_to_json(username)

    return render_template('progression.html', username = username, sport_pyramid = sport_pyramid, trad_pyramid = trad_pyramid, boulder_pyramid = boulder_pyramid, user_ticks = user_ticks, binned_code_dict = binned_code_dict)

if __name__ == "__main__":
    app.run

