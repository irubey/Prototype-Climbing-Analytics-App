from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import Config
import os

# Initialize Flask app with correct template and static paths
app = Flask(__name__, 
           template_folder='../templates',
           static_folder='../static')

# Enable CORS with specific configuration
CORS(app, resources={
    r"/*": {
        "origins": ["http://127.0.0.1:5001", "http://localhost:5001", "https://*.onrender.com"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

app.config.from_object(Config)
db = SQLAlchemy(app)

from app import routes, models

with app.app_context():
    db.create_all()
