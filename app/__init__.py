from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import Config
import os
from sqlalchemy.sql import text
from whitenoise import WhiteNoise
import logging
from logging.handlers import RotatingFileHandler
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Initialize Flask app with correct template and static paths
app = Flask(__name__, 
           template_folder='../templates',
           static_folder='../static')

# Set up logging
if not os.path.exists('logs'):
    os.mkdir('logs')

file_handler = RotatingFileHandler('logs/climbapp.log', maxBytes=10240000, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('ClimbApp startup')

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

# Debug prints
app.logger.info(f"Database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")
app.logger.info(f"SQLAlchemy Engine Options: {app.config['SQLALCHEMY_ENGINE_OPTIONS']}")

db = SQLAlchemy(app)

# Log database events
@event.listens_for(Engine, "connect")
def connect(dbapi_connection, connection_record):
    app.logger.info("Database connection established")

@event.listens_for(Engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    app.logger.info("Database connection checked out from pool")

@event.listens_for(Engine, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    app.logger.info("Database connection checked in to pool")

@event.listens_for(Engine, "close")
def close(dbapi_connection, connection_record):
    app.logger.info("Database connection closed")

from app import routes, models

# Create tables and initialize database
with app.app_context():
    try:
        # Only create tables if they don't exist
        db.create_all()
        
        # Initialize sequences for PostgreSQL if needed
        if 'postgresql' in str(app.config['SQLALCHEMY_DATABASE_URI']):
            app.logger.info("Initializing PostgreSQL sequences...")
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
                app.logger.info("PostgreSQL sequences initialized successfully")
            except Exception as e:
                app.logger.warning(f"Failed to initialize sequences: {e}")
                db.session.rollback()
        else:
            app.logger.info("Not using PostgreSQL, skipping sequence initialization")
            
        # Initialize binned code dict if empty
        from app.models import BinnedCodeDict
        from app.services.grade_processor import GradeProcessor
        from app.services.database_service import DatabaseService
        
        if not BinnedCodeDict.query.first():
            app.logger.info("Initializing binned code dictionary...")
            grade_processor = GradeProcessor()
            DatabaseService.init_binned_code_dict(grade_processor.binned_code_dict)
            app.logger.info("Binned code dictionary initialized successfully")
            
    except Exception as e:
        app.logger.error(f"Error during initialization: {e}")
        raise e
