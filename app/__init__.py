from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_caching import Cache
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from config import Config
import os
from sqlalchemy.sql import text
from whitenoise import WhiteNoise
import logging
from logging.handlers import RotatingFileHandler
from sqlalchemy import event
from sqlalchemy.engine import Engine
import stripe

# Initialize Flask extensions
db = SQLAlchemy()
cache = Cache(config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
})
mail = Mail()
login_manager = LoginManager()
login_manager.login_view = 'main.login'
bcrypt = Bcrypt()
stripe.api_version = ' 2024-09-30.acacia'  

from app.models import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_app():
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static',
                static_url_path='/static')
    
    # Load configuration
    app.config.from_object(Config)
    
    # Configure Stripe AFTER loading config
    stripe.api_key = app.config.get('STRIPE_API_KEY')
    stripe.max_network_retries = 3  # Recommended for reliability
    
    # Initialize extensions with app
    db.init_app(app)
    cache.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    # Register Blueprints or routes
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    # Set up logging
    logging.basicConfig(level=logging.DEBUG)  # Enable all debug messages

    # Remove existing file handler setup
    app.logger.handlers.clear()

    # Create new file handler
    file_handler = RotatingFileHandler(
        'logs/climbapp.log', 
        maxBytes=10240000, 
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.DEBUG)

    # Add handler to root logger
    logging.getLogger().addHandler(file_handler)

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
    
    # Set up SQLAlchemy event listeners
    @event.listens_for(Engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        app.logger.info("Database connection checked out from pool")
    
    @event.listens_for(Engine, "checkin")
    def receive_checkin(dbapi_connection, connection_record):
        app.logger.info("Database connection checked in to pool")
    
    @event.listens_for(Engine, "close")
    def close(dbapi_connection, connection_record):
        app.logger.info("Database connection closed")
    

    # Create tables and initialize database
    with app.app_context():
        from app import models
        try:
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
                        CREATE SEQUENCE IF NOT EXISTS user_uploads_id_seq;
                        
                        ALTER TABLE user_ticks ALTER COLUMN id SET DEFAULT nextval('user_ticks_id_seq');
                        ALTER TABLE sport_pyramid ALTER COLUMN id SET DEFAULT nextval('sport_pyramid_id_seq');
                        ALTER TABLE trad_pyramid ALTER COLUMN id SET DEFAULT nextval('trad_pyramid_id_seq');
                        ALTER TABLE boulder_pyramid ALTER COLUMN id SET DEFAULT nextval('boulder_pyramid_id_seq');
                        ALTER TABLE user_uploads ALTER COLUMN id SET DEFAULT nextval('user_uploads_id_seq');
    
                        SELECT setval('user_ticks_id_seq', 1, false);
                        SELECT setval('sport_pyramid_id_seq', 1, false);
                        SELECT setval('trad_pyramid_id_seq', 1, false);
                        SELECT setval('boulder_pyramid_id_seq', 1, false);
                        SELECT setval('user_uploads_id_seq', 1, false);
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
    
    return app
