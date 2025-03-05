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
        # Ensure tables are created
        with app.app_context():
            try:
                db.create_all()
                logger.info("Database tables created/verified")
            except Exception as e:
                logger.error(f"Error creating database tables: {str(e)}")
                return
                
        session_path = 'ton_collector_session.session'
        if not os.path.exists(session_path):
            logger.error("No session file found. Please run telegram_client.py first to authenticate.")
            return

        # Use existing session
        client = TelegramClient(session_path, 
                            Config.TELEGRAM_API_ID, 
                            Config.TELEGRAM_API_HASH)

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

                if is_ton_dev:
                    logger.info(f"Processing TON Dev channel: {channel_title}")

                    # Get latest message ID from database
                    with app.app_context():
                        latest_msg = TelegramMessage.query.filter_by(
                            channel_id=channel_id
                        ).order_by(TelegramMessage.message_id.desc()).first()

                        latest_id = latest_msg.message_id if latest_msg else 0
                        
                        # Use larger limit for TON channels
                        message_limit = 200 if is_ton_dev else 100
                        logger.info(f"Collecting messages from {channel_title} (is_ton_dev={is_ton_dev}), limit={message_limit}")

                        # Get new messages
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
                                        is_ton_dev=True
                                    )
                                    db.session.add(new_msg)
                                    db.session.commit()
                                    logger.info(f"Saved new message {message.id} from {channel_title}")
                                except Exception as e:
                                    logger.error(f"Error saving message {message.id} from {channel_title}: {str(e)}")
                                    db.session.rollback()
                            else:
                                logger.debug(f"Skipping message {message.id} in {channel_title} - no text content")

            except Exception as e:
                logger.error(f"Error processing dialog {getattr(dialog, 'title', 'Unknown')}: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Collection error: {str(e)}")
    finally:
        if client:
            await client.disconnect()

async def check_database_status():
    """Check database status and report metrics"""
    with app.app_context():
        try:
            total_messages = TelegramMessage.query.count()
            latest_message = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).first()
            latest_time = latest_message.timestamp if latest_message else "No messages"
            
            channels = db.session.query(TelegramMessage.channel_id, 
                                       TelegramMessage.channel_title, 
                                       db.func.count(TelegramMessage.id).label('count'))\
                                .group_by(TelegramMessage.channel_id)\
                                .all()
            
            logger.info(f"Database Status: {total_messages} total messages")
            logger.info(f"Latest message timestamp: {latest_time}")
            logger.info("Channel statistics:")
            for channel in channels:
                logger.info(f"  - {channel.channel_title}: {channel.count} messages")
                
        except Exception as e:
            logger.error(f"Error checking database status: {str(e)}")

async def main():
    """Main loop with backoff and status reporting"""
    cycle_count = 0
    while True:
        try:
            cycle_count += 1
            logger.info(f"Starting collection cycle #{cycle_count}...")
            await collect_messages()
            
            # Every 5 cycles, check database status
            if cycle_count % 5 == 0:
                await check_database_status()
                
            logger.info("Collection complete, waiting 60 seconds...")
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())