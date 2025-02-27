
import os
import asyncio
import logging
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from datetime import datetime

# Import after app, db, and model are fully initialized
from app import db, TelegramMessage, app

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
            # Collect recent messages from all dialogs
            dialogs = await client.get_dialogs(limit=100)
            
            # Store all dialogs, not just channels
            all_dialogs = []
            if isinstance(dialogs, list):
                all_dialogs = dialogs
                logger.info(f"Found {len(all_dialogs)} total dialogs")
            else:
                logger.warning(f"Dialogs object isn't a list, type: {type(dialogs)}")
                # Try to get individual dialogs instead
                try:
                    entities = []
                    for entity_id in [
                        # Add some known entities by ID to try
                        "tonblockchain", "tondev", "toncoin"
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
        
        # Process all dialogs, not just channels
        for dialog in all_dialogs:
            try:
                dialog_id = getattr(dialog, 'id', None)
                dialog_title = getattr(dialog, 'title', str(dialog_id))
                
                if not dialog_id:
                    logger.warning(f"Dialog missing ID, skipping: {dialog}")
                    continue
                
                logger.info(f"Processing dialog: {dialog_title}")
                
                with app.app_context():
                    # Check latest stored message
                    latest_msg = TelegramMessage.query.filter_by(
                        channel_id=str(dialog_id)
                    ).order_by(TelegramMessage.message_id.desc()).first()
                    
                    latest_id = latest_msg.message_id if latest_msg else 0
                    
                    logger.info(f"Checking {dialog_title} for new messages after ID {latest_id}")
                    
                    # Get recent messages (limit to avoid too many at once)
                    message_count = 0
                    async for message in client.iter_messages(dialog, limit=50, min_id=latest_id):
                        if message.text:
                            # Store message
                            with app.app_context():
                                new_msg = TelegramMessage(
                                    message_id=message.id,
                                    channel_id=str(dialog_id),
                                    channel_title=dialog_title,
                                    content=message.text,
                                    timestamp=message.date
                                )
                                db.session.add(new_msg)
                                db.session.commit()
                            message_count += 1
                            if message_count % 10 == 0:
                                logger.info(f"Saved {message_count} messages from {dialog_title}")
                    
                    if message_count > 0:
                        logger.info(f"Total saved {message_count} messages from {dialog_title}")
            except Exception as e:
                logger.error(f"Error processing channel {channel.title}: {str(e)}")
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
