import os
import asyncio
import logging
import threading
from datetime import datetime, timedelta
from telethon import TelegramClient
from flask import current_app
import sys
from app import db
from models import TelegramMessage
from utils import should_be_ton_dev, get_proper_dialog_type

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global collector thread reference
collector_thread = None


async def setup_telegram_session():
    """Set up a new Telegram session"""
    try:
        # Use Replit's persistent storage for session
        session_path = os.path.join(os.environ.get('REPL_HOME', ''),
                                    'ton_collector_session.session')
        logger.info(f"Setting up Telegram session at: {session_path}")

        # Get credentials from environment
        api_id = int(os.environ.get('TELEGRAM_API_ID', 0))
        api_hash = os.environ.get('TELEGRAM_API_HASH', '')
        phone = os.environ.get('TELEGRAM_PHONE', '')

        logger.info(f"Got phone number: {phone}")
        logger.debug(f"Using API ID: {api_id}")

        if not all([api_id, api_hash, phone]):
            logger.error("Missing required credentials:")
            logger.error(f"API ID present: {bool(api_id)} (got: {api_id})")
            logger.error(
                f"API Hash present: {bool(api_hash)} (got: {'[hidden]' if api_hash else 'None'})"
            )
            logger.error(
                f"Phone present: {bool(phone)} (got: {phone if phone else 'None'})"
            )
            return False

        # Remove existing session if it exists
        if os.path.exists(session_path):
            try:
                os.remove(session_path)
                logger.info(f"Removed existing session file for clean start")
            except Exception as e:
                logger.warning(f"Could not remove existing session: {str(e)}")

        logger.info("Creating TelegramClient with provided credentials")
        # Initialize client with proper error handling
        try:
            client = TelegramClient(session_path,
                                    api_id=api_id,
                                    api_hash=api_hash)
        except Exception as e:
            logger.error(f"Failed to create TelegramClient: {str(e)}")
            return False

        # Connect with timeout handling
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
                logger.info(f"Sending code request to: {phone}")
                # Send code request with proper formatting
                # Make sure the phone is in international format (with +)
                if not phone.startswith('+'):
                    phone = '+' + phone

                # Send the code request
                code_sent = await client.send_code_request(phone)
                logger.info(
                    f"Verification code sent successfully: {code_sent}")

                # Store the phone hash if available
                if hasattr(code_sent, 'phone_code_hash'):
                    os.environ[
                        'TELEGRAM_PHONE_HASH'] = code_sent.phone_code_hash
                    logger.info("Stored phone code hash for verification")

                # At this point, we return True to indicate the code was sent
                # The actual sign-in will happen in the verify_code endpoint
                return True

            except Exception as e:
                logger.error(f"Error during code request: {str(e)}")
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                logger.error(e)
                logger.error("File: %s Lineno: %s", fname, exc_tb.tb_lineno)
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
    from app import app
    client = None
    try:
        # Get app reference but don't enter context yet
        from app import app
            # Use Replit's persistent storage for session
            session_path = os.path.join(os.environ.get('REPL_HOME', ''),
                                    'ton_collector_session.session')

        # Check if deployment environment
        is_deployment = os.environ.get('REPLIT_DEPLOYMENT', False)
        if is_deployment and os.path.exists(session_path):
            logger.info(
                "Deployment environment detected, checking session validity")

        # Check if session exists and is not empty
        if not os.path.exists(session_path) or os.path.getsize(
                session_path) == 0:
            logger.error(
                "Session file not found or empty. Please run setup first")
            if os.path.exists(session_path):
                os.remove(session_path)
                logger.info("Removed invalid session file")
            return False

        # Validate session file permissions
        try:
            os.chmod(session_path, 0o600)
        except Exception as e:
            logger.warning(f"Could not set session file permissions: {e}")

        try:
            # Get API credentials from environment variables
            api_id = int(os.environ.get('TELEGRAM_API_ID'))
            api_hash = os.environ.get('TELEGRAM_API_HASH')

            if not api_id or not api_hash or not session_path:
                logger.error("Missing API credentials")
                return False

            # Initialize client with proper credentials
            client = TelegramClient(session_path,
                                    api_id=api_id,
                                    api_hash=api_hash)
            await client.connect()

            if not await client.is_user_authorized():
                logger.error("Session unauthorized. Please run setup first")
                # If in production environment, delete the invalid session
                if os.environ.get('REPLIT_DEPLOYMENT', False):
                    logger.info(
                        "Deployment environment detected, removing invalid session file"
                    )
                    if os.path.exists(session_path):
                        os.remove(session_path)
                return False

            logger.info("Successfully connected using existing session")

            while True:  # Continuous collection loop
                try:
                    # Get all dialogs
                    dialogs = await client.get_dialogs(limit=200)
                    logger.info(f"Found {len(dialogs)} dialogs")

                    # Process each dialog
                    for dialog in dialogs:
                        try:
                            if not hasattr(dialog, 'id'):
                                continue

                            channel_id = str(dialog.id)
                            channel_title = getattr(dialog, 'title',
                                                    channel_id)

                            # Get dialog type
                            entity = dialog.entity
                            dialog_type = get_proper_dialog_type(entity)

                            # Log dialog's latest message info from Telethon
                            logger.info(f"Dialog: {channel_title}")
                            logger.info(
                                f"Latest message date from Telethon: {getattr(dialog.message, 'date', 'Unknown')}"
                            )

                            # Get latest messages with proper app context
                            with app.app_context():
                                # Get latest stored message ID
                                latest_msg = TelegramMessage.query.filter_by(
                                    channel_id=channel_id).order_by(
                                        TelegramMessage.message_id.desc(
                                        )).first()

                                latest_id = latest_msg.message_id if latest_msg else 0
                                logger.debug(
                                    f"Processing {channel_title} from message_id > {latest_id}"
                                )
                                logger.debug(
                                    f"Latest message in DB: {latest_msg.timestamp if latest_msg else 'None'}"
                                )

                                # Process new messages with smaller batch size
                                message_batch = []
                                async for message in client.iter_messages(
                                        dialog, limit=20):
                                    if message.id <= latest_id and latest_id != 0:
                                        logger.debug(
                                            f"Skipping message {message.id} - already processed"
                                        )
                                        continue  # Skip processed messages

                                    if message.text:  # Only process text messages
                                        try:
                                            is_outgoing = getattr(
                                                message, 'out', False)
                                            is_ton_dev = should_be_ton_dev(
                                                channel_title)

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
                                            logger.error(
                                                f"Error preparing message: {str(e)}"
                                            )

                                # Commit all messages for this dialog at once
                                if message_batch:
                                    try:
                                        db.session.commit()
                                        logger.info(
                                            f"Saved {len(message_batch)} new messages from {channel_title}"
                                        )
                                    except Exception as e:
                                        logger.error(
                                            f"Error saving messages batch: {str(e)}"
                                        )
                                        db.session.rollback()

                        except Exception as e:
                            exc_type, exc_obj, exc_tb = sys.exc_info()
                            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                            logger.error(e)
                            logger.error("File: %s Lineno: %s", fname, exc_tb.tb_lineno)
                            logger.error(
                                f"Error processing dialog {getattr(dialog, 'title', 'Unknown')}: {str(e)}"
                            )
                            continue

                    # Short sleep between collection cycles
                    logger.info(
                        "Completed collection cycle, sleeping for 30 seconds")
                    await asyncio.sleep(30)

                except Exception as e:
                    logger.error(f"Error in collection cycle: {str(e)}")
                    await asyncio.sleep(60)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logger.error(e)
            logger.error("File: %s Lineno: %s", fname, exc_tb.tb_lineno)
            logger.error(f"Error connecting with existing session: {str(e)}")

            # Handle Telegram session errors for deployment
            if any(
                    x in str(e).lower() for x in
                ["authorization key", "ip addresses", "connection", "session"
                 ]):
                logger.warning(
                    "Session invalidated or connection issue - removing session file"
                )
                if os.path.exists(session_path):
                    os.remove(session_path)
                    logger.info(
                        f"Removed invalid session file: {session_path}")

                # Clear any cached connection data
                try:
                    import telethon.sessions
                    telethon.sessions.SQLiteSession.delete(session_path)
                except Exception as sess_e:
                    logger.warning(
                        f"Could not clean session with Telethon: {str(sess_e)}"
                    )

                # Notify about required action
                logger.warning(
                    "ACTION REQUIRED: Please visit the setup page to create a new session"
                )

            return False

    except Exception as e:
        logger.error(f"Fatal collector error: {str(e)}")
        return False
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
    collector_thread = threading.Thread(target=start_collector_thread,
                                        daemon=True)
    collector_thread.start()
    logger.info("Collector thread started successfully")


async def collector_loop():
    """Main collector loop with backoff"""
    from app import app
    consecutive_errors = 0
    while True:  # Continuous collection loop
        try:
            logger.info("Starting collection cycle")
            with app.app_context():
            result = await collect_messages()
            if result is False:  # If collection failed due to auth
                logger.info("Collection stopped due to authentication issue")
                await asyncio.sleep(60)  # Wait before retry
                continue
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            retry_wait = min(30 * 2**consecutive_errors, 600)  # Longer backoff
            logger.error(
                f"Error in collector loop (attempt {consecutive_errors}): {str(e)}"
            )
            if "unauthorized" in str(e).lower():
                logger.error(
                    "Session is not authorized. Please visit /setup to authenticate."
                )
                await asyncio.sleep(60)  # Wait longer for unauthorized errors
            else:
                logger.info(f"Retrying in {retry_wait} seconds...")
                await asyncio.sleep(retry_wait)
