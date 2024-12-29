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
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour 