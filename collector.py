
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
        # Get channels
        channels = []
        try:
            # First attempt to get channels directly from Config.TON_CHANNELS
            logger.info("Trying to fetch channels from configured list")
            for channel_title in Config.TON_CHANNELS:
                try:
                    entity = await client.get_entity(channel_title)
                    if hasattr(entity, 'id') and hasattr(entity, 'title'):
                        channels.append(entity)
                        logger.info(f"Successfully added channel: {entity.title}")
                except Exception as e:
                    logger.error(f"Error getting entity for {channel_title}: {str(e)}")
            
            # If no channels found, try an alternative approach
            if not channels:
                logger.info("No channels found from config list, trying dialogs method")
                try:
                    # Try to get channels using a safer method
                    dialogs = await client.get_dialogs(limit=50)  # Limit to reduce rate limiting issues
                    
                    # Ensure we have a proper iterable
                    if isinstance(dialogs, list):
                        for dialog in dialogs:
                            if hasattr(dialog, 'is_channel') and dialog.is_channel:
                                channels.append(dialog)
                                logger.info(f"Added channel from dialogs: {dialog.title}")
                    else:
                        logger.warning(f"Dialogs object isn't a list, type: {type(dialogs)}")
                except Exception as dialog_err:
                    logger.error(f"Error iterating dialogs: {str(dialog_err)}")
        except Exception as e:
            logger.error(f"Error getting channels: {str(e)}")
        
        logger.info(f"Found {len(channels)} channels")
        
        for channel in channels:
            try:
                with app.app_context():
                    # Check latest stored message
                    latest_msg = TelegramMessage.query.filter_by(
                        channel_id=str(channel.id)
                    ).order_by(TelegramMessage.message_id.desc()).first()
                    
                    latest_id = latest_msg.message_id if latest_msg else 0
                    
                    logger.info(f"Checking channel {channel.title} for new messages after ID {latest_id}")
                    
                    # Get messages
                    async for message in client.iter_messages(channel, min_id=latest_id):
                        if message.text:
                            # Store message
                            with app.app_context():
                                new_msg = TelegramMessage(
                                    message_id=message.id,
                                    channel_id=str(channel.id),
                                    channel_title=channel.title,
                                    content=message.text,
                                    timestamp=message.date
                                )
                                db.session.add(new_msg)
                                db.session.commit()
                            logger.info(f"Saved message {message.id} from {channel.title}")
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
    max_backoff = 900  # Max 15 minutes
    
    while True:
        try:
            logger.info(f"Starting message collection cycle...")
            await collect_messages()
            logger.info(f"Collection complete. Waiting {backoff_time} seconds before next collection...")
            # Reset backoff on success
            backoff_time = 60
            await asyncio.sleep(backoff_time)
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            # Implement exponential backoff to avoid rate limits
            logger.info(f"Backing off for {backoff_time} seconds...")
            await asyncio.sleep(backoff_time)
            backoff_time = min(backoff_time * 2, max_backoff)

if __name__ == "__main__":
    asyncio.run(main())
