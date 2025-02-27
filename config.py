import os

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'dev-secret-key')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///messages.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Telegram
    TELEGRAM_API_ID = os.environ.get('TELEGRAM_API_ID')
    TELEGRAM_API_HASH = os.environ.get('TELEGRAM_API_HASH')
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    # Rate Limiting
    RATELIMIT_DEFAULT = "100 per day"
    RATELIMIT_STORAGE_URL = "memory://"
    
    # Target channels/groups
    TARGET_CHANNELS = [
        'tondev',
        # Add other TON dev channels here
    ]
