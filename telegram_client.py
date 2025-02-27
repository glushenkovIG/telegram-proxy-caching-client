
import asyncio
import os
import logging
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load config
from config import Config

async def main():
    # Check if API credentials are set properly
    if Config.TELEGRAM_API_ID == '12345' or Config.TELEGRAM_API_HASH == 'your-api-hash-here':
        logger.error("Telegram API credentials not configured. Please set proper API_ID and API_HASH in config.py or environment variables.")
        return

    client = TelegramClient('ton_collector_session', 
                          Config.TELEGRAM_API_ID, 
                          Config.TELEGRAM_API_HASH)
    
    await client.connect()
    
    if not await client.is_user_authorized():
        logger.info("No user logged in - starting authentication process")
        
        if not Config.TELEGRAM_PHONE:
            phone = input("Enter your phone (with country code): ")
        else:
            phone = Config.TELEGRAM_PHONE
            
        await client.send_code_request(phone)
        code = input("Enter the code you received: ")
        
        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input("Enter your 2FA password: ")
            await client.sign_in(password=password)
            
        logger.info("Successfully authenticated!")
    else:
        logger.info("Already authenticated")
        me = await client.get_me()
        logger.info(f"Logged in as: {me.first_name} (@{me.username})")
    
    # List available dialogs (channels, groups, users)
    dialogs = await client.get_dialogs()
    logger.info(f"Found {len(dialogs)} dialogs")
    
    print("\nAvailable Telegram Channels:")
    channels = [d for d in dialogs if d.is_channel]
    for i, dialog in enumerate(channels[:20], 1):  # Show first 20 channels
        print(f"{i}. {dialog.name} (ID: {dialog.id})")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
