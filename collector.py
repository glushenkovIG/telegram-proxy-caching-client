import os
import asyncio
import logging
import threading
from datetime import datetime, timedelta
from telethon import TelegramClient
from flask import current_app

from app import db
from models import TelegramMessage
from utils import should_be_ton_dev, get_proper_dialog_type

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global collector thread reference
collector_thread = None

def get_session_path():
    """Get the session file path with proper fallback"""
    repl_home = os.environ.get('REPL_HOME')
    if not repl_home:
        logger.warning("REPL_HOME not set, using current directory")
        repl_home = os.getcwd()
    return os.path.join(repl_home, 'ton_collector_session.session')

def create_telegram_client():
    """Create and configure a Telegram client"""
    try:
        api_id = int(os.environ.get('TELEGRAM_API_ID'))
        api_hash = os.environ.get('TELEGRAM_API_HASH')

        if not api_id or not api_hash:
            logger.error("Missing Telegram API credentials")
            return None

        session_path = get_session_path()
        client = TelegramClient(session_path,
                              api_id=api_id,
                              api_hash=api_hash,
                              system_version="4.16.30-vxCUSTOM",
                              device_model="Replit Deployment",
                              app_version="1.0")
        return client
    except Exception as e:
        logger.error(f"Failed to create Telegram client: {str(e)}")
        return None

async def setup_telegram_session():
    """Set up a new Telegram session"""
    try:
        session_path = get_session_path()
        logger.info(f"Setting up Telegram session at: {session_path}")

        phone = os.environ.get('TELEGRAM_PHONE', '')
        logger.info(f"Got phone number: {phone}")

        client = create_telegram_client()
        if not client:
            return False

        try:
            await asyncio.wait_for(client.connect(), timeout=30)
            logger.info("Connected to Telegram servers")
        except asyncio.TimeoutError:
            logger.error("Timeout connecting to Telegram servers")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {str(e)}")
            return False

        if not await client.is_user_authorized():
            try:
                if not phone.startswith('+'):
                    phone = '+' + phone

                code_sent = await client.send_code_request(phone)
                logger.info("Verification code sent successfully")

                if hasattr(code_sent, 'phone_code_hash'):
                    os.environ['TELEGRAM_PHONE_HASH'] = code_sent.phone_code_hash
                    logger.info("Stored phone code hash for verification")

                return True

            except Exception as e:
                logger.error(f"Error during code request: {str(e)}")
                await client.disconnect()
                return False
        else:
            logger.info("Already authorized, no need for verification code")
            await client.disconnect()
            return True

    except Exception as e:
        logger.error(f"Error setting up Telegram session: {str(e)}")
        return False

async def collect_messages():
    """Main collection function"""
    client = None
    try:
        session_path = get_session_path()

        # Check if session exists and is not empty
        if not os.path.exists(session_path) or os.path.getsize(session_path) == 0:
            logger.error("Session file not found or empty. Please run setup first")
            return

        client = create_telegram_client()
        if not client:
            logger.error("Failed to create Telegram client")
            return

        await client.connect()

        if not await client.is_user_authorized():
            logger.error("Session unauthorized. Please run setup first")
            if os.environ.get('REPLIT_DEPLOYMENT', False):
                logger.info("Deployment environment detected, removing invalid session file")
                if os.path.exists(session_path):
                    os.remove(session_path)
            return

        logger.info("Successfully connected using existing session")

        while True:
            try:
                dialogs = await client.get_dialogs(limit=200)
                logger.info(f"Found {len(dialogs)} dialogs")

                for dialog in dialogs:
                    try:
                        if not hasattr(dialog, 'id'):
                            continue

                        channel_id = str(dialog.id)
                        channel_title = getattr(dialog, 'title', channel_id)

                        entity = dialog.entity
                        dialog_type = get_proper_dialog_type(entity)

                        logger.info(f"Dialog: {channel_title}")
                        logger.info(f"Latest message date from Telethon: {getattr(dialog.message, 'date', 'Unknown')}")

                        with current_app.app_context():
                            latest_msg = TelegramMessage.query.filter_by(channel_id=channel_id).order_by(TelegramMessage.message_id.desc()).first()
                            latest_id = latest_msg.message_id if latest_msg else 0
                            logger.debug(f"Processing {channel_title} from message_id > {latest_id}")
                            logger.debug(f"Latest message in DB: {latest_msg.timestamp if latest_msg else 'None'}")

                            message_batch = []
                            async for message in client.iter_messages(dialog, limit=20):
                                if message.id <= latest_id and latest_id != 0:
                                    logger.debug(f"Skipping message {message.id} - already processed")
                                    continue

                                if message.text:
                                    try:
                                        is_outgoing = getattr(message, 'out', False)
                                        is_ton_dev = should_be_ton_dev(channel_title)

                                        new_msg = TelegramMessage(
                                            message_id=message.id,
                                            channel_id=channel_id,
                                            channel_title=channel_title,
                                            content=message.text,
                                            timestamp=message.date,
                                            is_ton_dev=is_ton_dev,
                                            is_outgoing=is_outgoing,
                                            dialog_type=dialog_type)
                                        db.session.add(new_msg)
                                        message_batch.append(message.id)
                                    except Exception as e:
                                        logger.error(f"Error preparing message: {str(e)}")

                            if message_batch:
                                try:
                                    db.session.commit()
                                    logger.info(f"Saved {len(message_batch)} new messages from {channel_title}")
                                except Exception as e:
                                    logger.error(f"Error saving messages batch: {str(e)}")
                                    db.session.rollback()

                    except Exception as e:
                        logger.error(f"Error processing dialog {getattr(dialog, 'title', 'Unknown')}: {str(e)}")
                        continue

                logger.info("Completed collection cycle, sleeping for 30 seconds")
                await asyncio.sleep(30)

            except Exception as e:
                logger.error(f"Error in collection cycle: {str(e)}")
                await asyncio.sleep(60)

    except Exception as e:
        logger.error(f"Fatal collector error: {str(e)}")
    finally:
        if client:
            await client.disconnect()
            logger.info("Disconnected Telegram client")

def start_collector_thread():
    """Collector thread starter"""
    logger.info("Initializing collector thread")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(collector_loop())

def ensure_single_collector():
    """Ensure only one collector thread is running"""
    global collector_thread

    if collector_thread and collector_thread.is_alive():
        logger.info("Collector thread already running")
        return

    logger.info("Starting new collector thread")
    collector_thread = threading.Thread(target=start_collector_thread, daemon=True)
    collector_thread.start()
    logger.info("Collector thread started successfully")

async def collector_loop():
    """Main collector loop with backoff"""
    consecutive_errors = 0
    while True:
        try:
            logger.info("Starting collection cycle")
            await collect_messages()
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            retry_wait = min(30 * 2**consecutive_errors, 600)  # Longer backoff
            logger.error(f"Error in collector loop (attempt {consecutive_errors}): {str(e)}")
            if "unauthorized" in str(e).lower():
                logger.error("Session is not authorized. Please visit /setup to authenticate.")
                await asyncio.sleep(60)  # Wait longer for unauthorized errors
            else:
                logger.info(f"Retrying in {retry_wait} seconds...")
                await asyncio.sleep(retry_wait)