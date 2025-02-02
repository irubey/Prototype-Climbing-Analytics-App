import os
import secrets
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()

class Config:
    # Generate a secure random secret key
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Database configuration - prioritize local URL in development
    if os.environ.get('FLASK_ENV') == 'development':
        database_url = os.environ.get('LOCAL_DATABASE_URL') or os.environ.get('DATABASE_URL')
    else:
        database_url = os.environ.get('PRODUCTION_DATABASE_URL') or os.environ.get('LOCAL_DATABASE_URL')
    
    if not database_url:
        raise ValueError("No database URL configured. Set DATABASE_URL or LOCAL_DATABASE_URL in .env")
    
    # Convert postgres:// to postgresql:// if needed
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SQLAlchemy configuration - optimized for free tier
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 3,
        'max_overflow': 2,
        'pool_timeout': 20,
        'pool_recycle': 900,
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 10,
            'keepalives': 1,
            'keepalives_idle': 15,
            'keepalives_interval': 5,
            'keepalives_count': 3
        }
    }
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes
    
    # Query monitoring
    SQLALCHEMY_RECORD_QUERIES = True
    DATABASE_QUERY_TIMEOUT = 20 

    # Flask Mail configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('GMAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('GMAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('GMAIL_DEFAULT_SENDER')

    # Stripe configuration
    STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
    STRIPE_PRICE_ID_BASIC = os.environ.get('STRIPE_PRICE_ID_BASIC')
    STRIPE_PRICE_ID_PREMIUM = os.environ.get('STRIPE_PRICE_ID_PREMIUM')

    # Logging Configuration
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_LEVEL = logging.DEBUG
    LOG_FILE = 'logs/climbapp.log'
    LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5

    # CSRF Configuration
    WTF_CSRF_ENABLED = True
    WTF_CSRF_CHECK_DEFAULT = True
    WTF_CSRF_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']

    @staticmethod
    def init_app(app):
        # Ensure logs directory exists
        os.makedirs('logs', exist_ok=True)
        
        # Configure logging
        formatter = logging.Formatter(Config.LOG_FORMAT)
        
        # File handler
        file_handler = RotatingFileHandler(
            Config.LOG_FILE,
            maxBytes=Config.LOG_MAX_SIZE,
            backupCount=Config.LOG_BACKUP_COUNT
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(Config.LOG_LEVEL)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(Config.LOG_LEVEL)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(Config.LOG_LEVEL)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Set SQLAlchemy logging to WARNING
        logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
        
        app.logger.info('Logging system initialized')
