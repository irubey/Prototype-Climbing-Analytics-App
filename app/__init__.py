from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import Config
import os
from sqlalchemy.sql import text
from whitenoise import WhiteNoise

# Initialize Flask app with correct template and static paths
app = Flask(__name__, 
           template_folder='../templates',
           static_folder='../static')

# Configure WhiteNoise for static files
app.wsgi_app = WhiteNoise(app.wsgi_app, root=os.path.join(os.path.dirname(__file__), '../static/'), prefix='static/')

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

# Add SQLAlchemy engine configuration
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,  # Maximum number of connections in the pool
    'pool_timeout': 30,  # Seconds to wait before giving up on getting a connection
    'pool_recycle': 1800,  # Recycle connections after 30 minutes
    'pool_pre_ping': True,  # Enable connection health checks
    'max_overflow': 10,  # Allow up to 10 connections beyond pool_size
    'connect_args': {
        'connect_timeout': 10,  # Timeout for establishing new connections
        'keepalives': 1,  # Enable TCP keepalive
        'keepalives_idle': 30,  # Seconds before sending keepalive
        'keepalives_interval': 10,  # Seconds between keepalives
        'keepalives_count': 5  # Failed keepalives before dropping connection
    }
}

# Debug prints
print("Database URL:", app.config['SQLALCHEMY_DATABASE_URI'])
print("Is PostgreSQL?", 'postgresql' in str(app.config['SQLALCHEMY_DATABASE_URI']))

db = SQLAlchemy(app)

from app import routes, models

# Create tables and initialize database
with app.app_context():
    try:
        # Only create tables if they don't exist
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
            
        # Initialize binned code dict if empty
        from app.models import BinnedCodeDict
        from app.services.grade_processor import GradeProcessor
        from app.services.database_service import DatabaseService
        
        if not BinnedCodeDict.query.first():
            print("Initializing binned code dictionary...")
            grade_processor = GradeProcessor()
            DatabaseService.init_binned_code_dict(grade_processor.binned_code_dict)
            print("Binned code dictionary initialized successfully")
            
    except Exception as e:
        print(f"Error during initialization: {e}")
        raise e
