import os
import asyncio
import logging
import threading
from datetime import datetime
from telethon import TelegramClient
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database base class
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///messages.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# Define model
class TelegramMessage(db.Model):
    __tablename__ = 'telegram_messages'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, nullable=False)
    channel_id = db.Column(db.String(100), nullable=False)
    channel_title = db.Column(db.String(200))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_ton_dev = db.Column(db.Boolean, default=False)

# TON Dev detector function
def should_be_ton_dev(channel_title):
    """Determine if a channel title indicates a TON developer channel"""
    ton_dev_keywords = [
        'ton dev', 'telegram developers', 'ton development',
        'ton developers', 'ton community', 'ton research',
        'ton jobs', 'ton tact', 'ton data hub', 'ton society',
        'hackers league', 'ton status', 'ton contests'
    ]

    channel_title_lower = channel_title.lower()

    # Exact channel matches
    exact_matches = [
        'ton dev chat', 'ton dev news', 'ton dev chat (中文)',
        'ton dev chat (en)', 'ton dev chat (py)', 'ton dev chat (ру)',
        'telegram developers community', 'ton society chat',
        'ton data hub chat', 'ton tact language chat',
        'hackers league hackathon', 'ton research',
        'ton community', 'ton jobs', 'ton status',
        'testnet ton status', 'ton contests', 'botnews',
        'the open network'
    ]

    for match in exact_matches:
        if channel_title_lower == match.lower():
            logger.info(f"Channel '{channel_title}' exactly matched TON channel: {match}")
            return True

    # Keyword-based matches
    for keyword in ton_dev_keywords:
        if keyword.lower() in channel_title_lower:
            logger.info(f"Channel '{channel_title}' matched TON keyword: {keyword}")
            return True

    return False

# Telegram collector function
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

# Collector main loop
async def collector_loop():
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

# Function to start the collector in a separate thread
def start_collector_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(collector_loop())

# Define routes
@app.route('/')
def index():
    # Get all messages, with option to filter
    show_ton_only = True  # Can be made into a query parameter if needed

    if show_ton_only:
        # Only get TON dev messages
        messages = TelegramMessage.query.filter_by(is_ton_dev=True).order_by(TelegramMessage.timestamp.desc()).limit(100).all()
    else:
        # Get all messages
        messages = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).limit(100).all()

    return render_template('index.html', messages=messages)

@app.route('/all')
def all_messages():
    # Get all messages without filtering
    messages = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).limit(100).all()
    return render_template('index.html', messages=messages)

# Run the application
if __name__ == "__main__":
    # Create tables if they don't exist
    with app.app_context():
        db.create_all()
        logger.info("Application created successfully")

    # Start collector in a separate thread
    logger.info("Starting simplified Telegram collector and server")
    collector_thread = threading.Thread(target=start_collector_thread, daemon=True)
    collector_thread.start()

    # Start Flask server
    app.run(host="0.0.0.0", port=5000)