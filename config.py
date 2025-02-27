import os

class Config:
    # Telegram API credentials
    TELEGRAM_API_ID = os.environ.get('TELEGRAM_API_ID', '26162406')
    TELEGRAM_API_HASH = os.environ.get('TELEGRAM_API_HASH', '7a005c82feee57d782a7e2f8399ddaf6')
    TELEGRAM_PHONE = os.environ.get('TELEGRAM_PHONE', '+41762636496')

    # Target folder for Telegram messages (using Saved Messages for testing)
    TARGET_FOLDER = 'me'  # This will target Saved Messages folder

    # Database settings
    DATABASE_URL = os.environ.get('DATABASE_URL')

    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')