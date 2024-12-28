import os
import secrets

class Config:
    # Generate a secure random secret key
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Database configuration
    database_url = os.environ.get('DATABASE_URL')
    print(f"Initial DATABASE_URL: {database_url}")
    
    # If DATABASE_URL is not set but we have individual components, construct it
    if not database_url:
        db_user = os.environ.get('POSTGRES_USER')
        db_pass = os.environ.get('POSTGRES_PASSWORD')
        db_host = os.environ.get('POSTGRES_HOST')
        db_name = os.environ.get('POSTGRES_DB')
        
        if all([db_user, db_pass, db_host, db_name]):
            database_url = f"postgresql://{db_user}:{db_pass}@{db_host}/{db_name}"
            print(f"Constructed DATABASE_URL from components")
    
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        print(f"Converted DATABASE_URL: {database_url}")
    
    SQLALCHEMY_DATABASE_URI = database_url or 'sqlite:///climbing.db'
    print(f"Final SQLALCHEMY_DATABASE_URI: {SQLALCHEMY_DATABASE_URI}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour 