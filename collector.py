
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
        try:
            dialogs = await client.get_dialogs()
            # Make sure dialogs is actually iterable before proceeding
            if hasattr(dialogs, '__iter__'):
                channels = [d for d in dialogs if d.is_channel]
            else:
                logger.error(f"Dialogs object is not iterable: {type(dialogs)}")
                # Try alternative approach to get channels
                channels = []
                for channel_title in Config.TON_CHANNELS:
                    try:
                        entity = await client.get_entity(channel_title)
                        if hasattr(entity, 'id') and hasattr(entity, 'title'):
                            channels.append(entity)
                    except Exception as e:
                        logger.error(f"Error getting entity for {channel_title}: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting dialogs: {str(e)}")
            channels = []
        
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
    while True:
        try:
            await collect_messages()
            logger.info("Waiting 60 seconds before next collection...")
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
