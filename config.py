import os
import secrets
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Generate a secure random secret key
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Database configuration - prioritize production URL if available
    database_url = os.environ.get('PRODUCTION_DATABASE_URL') or os.environ.get('LOCAL_DATABASE_URL')
    
    if not database_url:
        raise ValueError("No database URL configured. Set PRODUCTION_DATABASE_URL or LOCAL_DATABASE_URL in .env")
    
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