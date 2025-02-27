import os

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'dev-secret-key')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///messages.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Telegram
    TELEGRAM_API_ID = 26162406
    TELEGRAM_API_HASH = '7a005c82feee57d782a7e2f8399ddaf6'
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    # Rate Limiting
    RATELIMIT_DEFAULT = "100 per day"
    RATELIMIT_STORAGE_URL = "memory://"
    
    # Target channels/groups
    TARGET_CHANNELS = [
        'tondev',
        'toncoin',
        'tondev_eng',
        # Add other TON dev channels here
    ]