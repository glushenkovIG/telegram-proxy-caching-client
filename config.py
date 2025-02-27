import os

class Config:
    # Telegram API settings with hardcoded test values for development
    TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID', '12345')  # Replace with your actual API ID
    TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', 'your-api-hash-here')  # Replace with your actual API Hash
    TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE', '')

    # List of channel usernames or IDs to monitor
    # Add the channels you want to monitor here
    TON_CHANNELS = [
        'tonblockchain',
        'tondev', 
        'toncoin',
        # Add more channels as needed
    ]

    # Target folder for Telegram messages (using Saved Messages for testing)
    TARGET_FOLDER = 'me'  # This will target Saved Messages folder

    # Database settings
    DATABASE_URL = os.environ.get('DATABASE_URL')

    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')