import os

class Config:
    # Telegram API settings with hardcoded test values for development
    TELEGRAM_API_ID = os.environ.get('TELEGRAM_API_ID') or '12345'  # Replace with your actual API ID
    TELEGRAM_API_HASH = os.environ.get('TELEGRAM_API_HASH') or 'your-api-hash-here'  # Replace with your actual API Hash
    TELEGRAM_PHONE = os.environ.get('TELEGRAM_PHONE')

    # Target TON dev channels
    TON_CHANNELS = [
        'TON Dev News',
        'TON Developers Community',
        'TON Society Chat',
        'TON Dev Chat',
        'TON Data Hub Chat',
        'TON Community',
        'TON Tact Language Chat',
        'TON Research',
        'TON Status'
    ]

    # Target folder for Telegram messages (using Saved Messages for testing)
    TARGET_FOLDER = 'me'  # This will target Saved Messages folder

    # Database settings
    DATABASE_URL = os.environ.get('DATABASE_URL')

    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')