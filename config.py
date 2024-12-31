import os
import secrets

class Config:
    # Generate a secure random secret key
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Database configuration
    database_url = os.environ.get('DATABASE_URL')
    print(f"Environment variables:")
    print(f"DATABASE_URL: {database_url}")
    print(f"All env vars: {dict(os.environ)}")
    
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        print(f"Converted DATABASE_URL: {database_url}")
    
    SQLALCHEMY_DATABASE_URI = database_url or 'sqlite:///climbing.db'
    print(f"Final SQLALCHEMY_DATABASE_URI: {SQLALCHEMY_DATABASE_URI}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SQLAlchemy configuration - optimized for free tier
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 3,  # Reduced from 5
        'max_overflow': 2,  # Reduced from 5
        'pool_timeout': 20,  # Reduced from 30
        'pool_recycle': 900,  # 15 minutes instead of 30
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 10,
            'keepalives': 1,
            'keepalives_idle': 15,  # Reduced from 30
            'keepalives_interval': 5,  # Reduced from 10
            'keepalives_count': 3  # Reduced from 5
        }
    }
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes instead of 1 hour
    
    # Query monitoring
    SQLALCHEMY_RECORD_QUERIES = True
    DATABASE_QUERY_TIMEOUT = 20  # Reduced from 110 seconds 