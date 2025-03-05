import os
import asyncio
import logging
from telethon import TelegramClient
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import app and db
from app import db, app, TelegramMessage, should_be_ton_dev

async def collect_messages():
    """Main collection function"""
    try:
        session_path = 'ton_collector_session.session'
        if not os.path.exists(session_path):
            logger.error("No session file found. Please run telegram_client.py first to authenticate.")
            return

        # Get API credentials from environment
        api_id = int(os.environ.get("TELEGRAM_API_ID", 0))
        api_hash = os.environ.get("TELEGRAM_API_HASH", "")

        if not api_id or not api_hash:
            logger.error("Telegram API credentials not configured")
            return

        # Use existing session
        client = TelegramClient(session_path, api_id, api_hash)

        await client.connect()
        if not await client.is_user_authorized():
            logger.error("Session exists but unauthorized. Please run telegram_client.py first")
            return

        logger.info("Successfully connected using existing session")

        # Get all dialogs
        dialogs = await client.get_dialogs()
        logger.info(f"Found {len(dialogs)} dialogs")

        # Process each dialog
        for dialog in dialogs:
            try:
                if not hasattr(dialog, 'id'):
                    continue

                channel_id = str(dialog.id)
                channel_title = getattr(dialog, 'title', channel_id)

                # Check if it's a TON Dev channel
                is_ton_dev = should_be_ton_dev(channel_title)

                # Process all channels, but mark TON Dev ones specially
                logger.info(f"Processing channel: {channel_title} (is_ton_dev={is_ton_dev})")

                # Get latest message ID from database
                with app.app_context():
                    latest_msg = TelegramMessage.query.filter_by(
                        channel_id=channel_id
                    ).order_by(TelegramMessage.message_id.desc()).first()

                    latest_id = latest_msg.message_id if latest_msg else 0

                    # Get 10 most recent messages
                    message_limit = 10

                    # Get only the 10 most recent messages
                    async for message in client.iter_messages(dialog, limit=message_limit):
                        if message.id <= latest_id:
                            logger.debug(f"Skipping message {message.id} in {channel_title} - already processed")
                            break

                        if message.text:
                            try:
                                new_msg = TelegramMessage(
                                    message_id=message.id,
                                    channel_id=channel_id,
                                    channel_title=channel_title,
                                    content=message.text,
                                    timestamp=message.date,
                                    is_ton_dev=is_ton_dev  # Mark appropriately
                                )
                                db.session.add(new_msg)
                                db.session.commit()
                                logger.info(f"Saved message from {channel_title}")
                            except Exception as e:
                                logger.error(f"Error saving message: {str(e)}")
                                db.session.rollback()

            except Exception as e:
                logger.error(f"Error processing dialog {channel_title}: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Collection error: {str(e)}")
    finally:
        if 'client' in locals() and client:
            await client.disconnect()

async def main():
    """Main loop with backoff"""
    while True:
        try:
            logger.info("Starting collection cycle...")
            await collect_messages()
            logger.info("Collection complete, waiting 120 seconds...")
            await asyncio.sleep(120)  # Check every 2 minutes
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())