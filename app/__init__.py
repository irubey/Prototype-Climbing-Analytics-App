from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config
import os

# Initialize Flask app with correct template and static paths
app = Flask(__name__, 
           template_folder='../templates',
           static_folder='../static')

app.config.from_object(Config)
db = SQLAlchemy(app)

from app import routes, models

with app.app_context():
    db.create_all()
