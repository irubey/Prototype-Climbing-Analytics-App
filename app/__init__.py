from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import Config
import os
from sqlalchemy.sql import text

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

# Debug prints
print("Database URL:", app.config['SQLALCHEMY_DATABASE_URI'])
print("Is PostgreSQL?", 'postgresql' in str(app.config['SQLALCHEMY_DATABASE_URI']))

db = SQLAlchemy(app)

from app import routes, models

# Create tables and initialize database
with app.app_context():
    try:
        # Drop all tables if they exist (for clean initialization)
        db.drop_all()
        # Create all tables fresh
        db.create_all()
        
        # Initialize sequences for PostgreSQL if needed
        if 'postgresql' in str(app.config['SQLALCHEMY_DATABASE_URI']):
            print("Initializing PostgreSQL sequences...")
            try:
                db.session.execute(text("""
                    CREATE SEQUENCE IF NOT EXISTS user_ticks_id_seq;
                    CREATE SEQUENCE IF NOT EXISTS sport_pyramid_id_seq;
                    CREATE SEQUENCE IF NOT EXISTS trad_pyramid_id_seq;
                    CREATE SEQUENCE IF NOT EXISTS boulder_pyramid_id_seq;
                    
                    ALTER TABLE user_ticks ALTER COLUMN id SET DEFAULT nextval('user_ticks_id_seq');
                    ALTER TABLE sport_pyramid ALTER COLUMN id SET DEFAULT nextval('sport_pyramid_id_seq');
                    ALTER TABLE trad_pyramid ALTER COLUMN id SET DEFAULT nextval('trad_pyramid_id_seq');
                    ALTER TABLE boulder_pyramid ALTER COLUMN id SET DEFAULT nextval('boulder_pyramid_id_seq');
                    
                    SELECT setval('user_ticks_id_seq', 1, false);
                    SELECT setval('sport_pyramid_id_seq', 1, false);
                    SELECT setval('trad_pyramid_id_seq', 1, false);
                    SELECT setval('boulder_pyramid_id_seq', 1, false);
                """))
                db.session.commit()
                print("PostgreSQL sequences initialized successfully")
            except Exception as e:
                print(f"Warning: Failed to initialize sequences: {e}")
                db.session.rollback()
        else:
            print("Not using PostgreSQL, skipping sequence initialization")
    except Exception as e:
        print(f"Error initializing database: {e}")
        db.session.rollback()
