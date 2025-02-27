import os
import asyncio
import logging
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from datetime import datetime

# Import after app, db, and model are fully initialized
from app import db, app
from models import TelegramMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load config
from config import Config

async def start_client():
    try:
        # Check if API credentials are set properly
        if Config.TELEGRAM_API_ID == '12345' or Config.TELEGRAM_API_HASH == 'your-api-hash-here':
            logger.error("Telegram API credentials not configured. Please set proper API_ID and API_HASH in config.py or environment variables.")
            return None

        session_path = 'ton_collector_session.session'
        # Use existing session
        if os.path.exists(session_path):
            logger.info(f"Using existing session: {session_path}")
        else:
            logger.warning("No session file found. Please run telegram_client.py first to authenticate.")
            return None

        client = TelegramClient(session_path, 
                              Config.TELEGRAM_API_ID, 
                              Config.TELEGRAM_API_HASH)

        await client.connect()
        # Check if user is already authorized
        if not await client.is_user_authorized():
            logger.error("Session unauthorized. Please run telegram_client.py first")
            return None

        logger.info(f"Client connected successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize client: {str(e)}")
        return None

async def collect_messages():
    client = await start_client()
    if not client:
        return

    try:
        # Collect all dialogs without pre-filtering
        logger.info("Getting all dialogs without pre-filtering")
        try:
            # Use a larger limit to get more channels
            dialogs = await client.get_dialogs(limit=200)
            all_dialogs = []

            if isinstance(dialogs, list):
                all_dialogs = dialogs
                logger.info(f"Found {len(all_dialogs)} total dialogs")
            else:
                logger.warning("Dialogs object isn't a list")
                # Try to get individual dialogs instead
                try:
                    entities = []
                    for entity_id in [
                        "tonblockchain", "tondev", "toncoin", 
                        "ton_english", "TONDevelopers", "ton_ru"  # Add more channels
                    ]:
                        try:
                            entity = await client.get_entity(entity_id)
                            entities.append(entity)
                            logger.info(f"Added entity: {getattr(entity, 'title', entity_id)}")
                        except Exception as e:
                            logger.error(f"Error getting entity {entity_id}: {str(e)}")
                    all_dialogs = entities
                except Exception as e:
                    logger.error(f"Error getting individual entities: {str(e)}")
                    all_dialogs = []

        except Exception as e:
            logger.error(f"Error getting dialogs: {str(e)}")
            all_dialogs = []

        logger.info(f"Processing {len(all_dialogs)} dialogs")

        # Process all dialogs
        for dialog in all_dialogs:
            try:
                dialog_id = getattr(dialog, 'id', None)
                dialog_title = getattr(dialog, 'title', str(dialog_id))

                if not dialog_id:
                    logger.warning(f"Dialog missing ID, skipping: {dialog}")
                    continue

                logger.info(f"Processing dialog: {dialog_title}")

                # Check if it's a TON Dev channel
                is_ton_dev = False
                try:
                    # First try folder-based detection
                    folder = await client(client.get_dialogs_request())
                    is_ton_dev = any(
                        f.title.lower() in ["ton dev", "ton devs"] and any(
                            p.peer.channel_id == dialog_id for p in f.include_peers
                        ) for f in folder.folders if hasattr(f, 'title')
                    )

                    # If not in TON Dev folder, check title
                    if not is_ton_dev:
                        is_ton_dev = any(keyword.lower() in dialog_title.lower() 
                                      for keyword in ["ton dev", "ton development", "开发", "developers", "telegram developers"])
                except Exception as e:
                    logger.error(f"Error checking TON Dev status for {dialog_title}: {str(e)}")
                    # Fallback to title check
                    is_ton_dev = any(keyword.lower() in dialog_title.lower() 
                                  for keyword in ["ton dev", "ton development", "开发", "developers", "telegram developers"])

                logger.info(f"Channel {dialog_title} - TON Dev status: {is_ton_dev}")

                with app.app_context():
                    try:
                        # Check latest stored message
                        latest_msg = TelegramMessage.query.filter_by(
                            channel_id=str(dialog_id)
                        ).order_by(TelegramMessage.message_id.desc()).first()

                        latest_id = latest_msg.message_id if latest_msg else 0

                        # Get recent messages (increased limit)
                        message_count = 0
                        async for message in client.iter_messages(dialog, limit=100):
                            if message.id <= latest_id:
                                break

                            if message.text:
                                try:
                                    new_msg = TelegramMessage(
                                        message_id=message.id,
                                        channel_id=str(dialog_id),
                                        channel_title=dialog_title,
                                        content=message.text,
                                        timestamp=message.date,
                                        is_ton_dev=is_ton_dev
                                    )
                                    db.session.add(new_msg)
                                    message_count += 1

                                    if message_count % 10 == 0:
                                        db.session.commit()
                                        logger.info(f"Saved {message_count} messages from {dialog_title}")
                                except Exception as e:
                                    logger.error(f"Error saving message: {str(e)}")
                                    db.session.rollback()
                                    continue

                        if message_count > 0:
                            db.session.commit()
                            logger.info(f"Total saved {message_count} new messages from {dialog_title}")
                    except Exception as e:
                        logger.error(f"Error processing messages for {dialog_title}: {str(e)}")
                        db.session.rollback()
                        continue

            except Exception as e:
                logger.error(f"Error processing dialog: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Error in collect_messages: {str(e)}")
    finally:
        await client.disconnect()
        logger.info("Client disconnected")

async def main():
    backoff_time = 60  # Start with 60 seconds
    max_backoff = 1800  # Max 30 minutes
    consecutive_errors = 0

    while True:
        try:
            logger.info(f"Starting message collection cycle...")
            await collect_messages()
            logger.info(f"Collection complete. Waiting {backoff_time} seconds before next collection...")
            # Reset backoff on success
            backoff_time = 60
            consecutive_errors = 0
            await asyncio.sleep(backoff_time)
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Error in main loop ({consecutive_errors} in a row): {str(e)}")

            # Increase backoff time with consecutive errors
            if consecutive_errors > 1:
                backoff_time = min(backoff_time * 2, max_backoff)

            logger.info(f"Backing off for {backoff_time} seconds...")
            await asyncio.sleep(backoff_time)

if __name__ == "__main__":
    asyncio.run(main())