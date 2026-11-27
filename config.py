import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'finora-default-secret-key-2026-safe')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Check MySQL settings
    mysql_user = os.environ.get('MYSQL_USER')
    mysql_password = os.environ.get('MYSQL_PASSWORD', '')
    mysql_host = os.environ.get('MYSQL_HOST', 'localhost')
    mysql_port = os.environ.get('MYSQL_PORT', '3306')
    mysql_db = os.environ.get('MYSQL_DB', 'finora_db')
    
    explicit_db_url = os.environ.get('DATABASE_URL')
    
    if explicit_db_url:
        SQLALCHEMY_DATABASE_URI = explicit_db_url
    elif mysql_user:
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_db}"
    else:
        # Seamless SQLite database default inside project folder
        sqlite_path = BASE_DIR / 'finora.db'
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{sqlite_path.as_posix()}"
        
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True
    }
