import os
import asyncio
import logging
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import after app, db, and model are fully initialized
from app import db, app
from models import TelegramMessage
from utils import should_be_ton_dev

# Load config
from config import Config

async def collect_messages():
    """Main collection function"""
    client = None
    try:
        # Check if API credentials are set properly
        if Config.TELEGRAM_API_ID == '12345' or Config.TELEGRAM_API_HASH == 'your-api-hash-here':
            logger.error("Telegram API credentials not configured. Please set proper API_ID and API_HASH in config.py or environment variables.")
            return

        session_path = 'ton_collector_session.session'
        if not os.path.exists(session_path):
            logger.warning("No session file found. Please run telegram_client.py first to authenticate.")
            return

        client = TelegramClient(session_path, 
                             Config.TELEGRAM_API_ID, 
                             Config.TELEGRAM_API_HASH)

        await client.connect()
        if not await client.is_user_authorized():
            logger.error("Session unauthorized. Please run telegram_client.py first")
            return

        logger.info("Connected to Telegram")

        # Get all dialogs
        dialogs = await client.get_dialogs(limit=200)

        # Process each dialog
        for dialog in dialogs:
            try:
                if not hasattr(dialog, 'id'):
                    continue

                channel_id = str(dialog.id)
                channel_title = getattr(dialog, 'title', channel_id)

                # Check if it's a TON Dev channel
                is_ton_dev = should_be_ton_dev(channel_title)

                if is_ton_dev:
                    logger.info(f"Processing TON Dev channel: {channel_title}")

                    # Get latest message ID from database
                    with app.app_context():
                        latest_msg = TelegramMessage.query.filter_by(
                            channel_id=channel_id
                        ).order_by(TelegramMessage.message_id.desc()).first()

                        latest_id = latest_msg.message_id if latest_msg else 0

                        # Get new messages
                        async for message in client.iter_messages(dialog, limit=100):
                            if message.id <= latest_id:
                                break

                            if message.text:
                                try:
                                    new_msg = TelegramMessage(
                                        message_id=message.id,
                                        channel_id=channel_id,
                                        channel_title=channel_title,
                                        content=message.text,
                                        timestamp=message.date,
                                        is_ton_dev=True
                                    )
                                    db.session.add(new_msg)
                                    db.session.commit()
                                    logger.info(f"Saved new message from {channel_title}")
                                except Exception as e:
                                    logger.error(f"Error saving message: {str(e)}")
                                    db.session.rollback()

            except Exception as e:
                logger.error(f"Error processing dialog {getattr(dialog, 'title', 'Unknown')}: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Collection error: {str(e)}")
    finally:
        if client:
            await client.disconnect()

async def main():
    """Main loop with backoff"""
    while True:
        try:
            logger.info("Starting collection cycle...")
            await collect_messages()
            logger.info("Collection complete, waiting 60 seconds...")
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())