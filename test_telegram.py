import os
import asyncio
from telethon import TelegramClient
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_telegram_connection():
    """Test if we can get new messages from Telegram"""
    try:
        # Use existing session
        session_path = 'ton_collector_session.session'
        api_id = os.environ.get('TELEGRAM_API_ID')
        api_hash = os.environ.get('TELEGRAM_API_HASH')

        if not api_id or not api_hash:
            logger.error("API credentials not found in environment variables")
            return

        client = TelegramClient(session_path, api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            logger.error("Session unauthorized")
            return

        logger.info("Successfully connected to Telegram")

        # Get dialogs without caching
        dialogs = await client.get_dialogs(limit=5, cache=False)
        logger.info(f"Found {len(dialogs)} dialogs")

        # Check each dialog's latest message
        for dialog in dialogs:
            title = getattr(dialog, 'title', str(dialog.id))
            latest_msg = dialog.message
            if latest_msg:
                logger.info(f"Dialog: {title}")
                logger.info(f"Latest message date: {latest_msg.date}")
                logger.info(f"Message text: {latest_msg.text[:100] if latest_msg.text else 'No text'}")
                logger.info("-" * 50)

            # Get a few recent messages
            messages = await client.get_messages(dialog, limit=5)
            logger.info(f"Recent messages from {title}:")
            for msg in messages:
                if msg and msg.text:
                    logger.info(f"Message ID: {msg.id}, Date: {msg.date}, Text: {msg.text[:50]}")
            logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
    finally:
        if 'client' in locals() and client:
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_telegram_connection())