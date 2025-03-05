
import os
import asyncio
import logging
import threading
from datetime import datetime
from telethon import TelegramClient
from flask import Flask, render_template, request, jsonify
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
    if not channel_title:
        return False
        
    # List of known TON-related keywords
    ton_keywords = [
        'ton', 'telegram open network', 'the open network', 
        'telegram developers', 'tact language'
    ]

    # Exact matches for known TON channels
    ton_channels = [
        'ton dev chat', 'ton dev chat (en)', 'ton dev chat (ру)', 
        'ton dev chat (中文)', 'ton dev news', 'ton status', 
        'ton community', 'ton society chat', 'ton research',
        'ton contests', 'ton tact language chat', 'ton jobs', 
        'telegram developers community', 'botnews', 
        'testnet ton status', 'hackers league hackathon',
        'ton society id', 'ton data hub'
    ]

    channel_lower = channel_title.lower()

    # Check if it's an exact match
    if channel_lower in ton_channels:
        return True

    # Check for keyword match
    for keyword in ton_keywords:
        if keyword in channel_lower:
            return True

    return False

# Telegram collector function
async def collect_messages():
    """Main collection function"""
    try:
        session_path = 'ton_collector_session.session'
        if not os.path.exists(session_path):
            logger.error("No session file found. Please run the setup first to authenticate.")
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
            logger.error("Session exists but unauthorized. Please run the setup first")
            return

        logger.info("Successfully connected using existing session")

        # Get all dialogs
        dialogs = await client.get_dialogs()
        logger.info(f"Found {len(dialogs)} dialogs")

        # Process each dialog
        for dialog in dialogs:
            try:
                if not hasattr(dialog, 'id'):
                    logger.warning("Skipping dialog without ID")
                    continue

                channel_id = str(dialog.id)
                channel_title = getattr(dialog, 'title', channel_id)

                # Check if it's a TON Dev channel
                is_ton_dev = should_be_ton_dev(channel_title)

                # Process ALL channels, saving messages from every dialog
                logger.info(f"Processing channel: {channel_title} (is_ton_dev={is_ton_dev})")

                # Get latest message ID from database
                with app.app_context():
                    # Get most recent messages (increased limit for better coverage)
                    message_limit = 20

                    latest_msg = TelegramMessage.query.filter_by(
                        channel_id=channel_id
                    ).order_by(TelegramMessage.message_id.desc()).first()

                    latest_id = latest_msg.message_id if latest_msg else 0
                    logger.info(f"Latest message ID in database for {channel_title}: {latest_id}")

                    # Process messages
                    message_count = 0
                    async for message in client.iter_messages(dialog, limit=message_limit):
                        if message.id <= latest_id:
                            logger.info(f"Skipping message {message.id} in {channel_title} - already processed")
                            continue  # Changed from break to continue to process more messages

                        if message.text:
                            try:
                                new_msg = TelegramMessage(
                                    message_id=message.id,
                                    channel_id=channel_id,
                                    channel_title=channel_title,
                                    content=message.text,
                                    timestamp=message.date,
                                    is_ton_dev=is_ton_dev
                                )
                                db.session.add(new_msg)
                                db.session.commit()
                                message_count += 1
                                logger.info(f"Saved message {message.id} from {channel_title}")
                            except Exception as e:
                                logger.error(f"Error saving message: {str(e)}")
                                db.session.rollback()
                    
                    logger.info(f"Processed {message_count} new messages from {channel_title}")

            except Exception as e:
                logger.error(f"Error processing dialog {getattr(dialog, 'title', 'unknown')}: {str(e)}")
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
            logger.error(f"Error in main loop: {str(e)}", exc_info=True)
            logger.info("Retrying collection in 30 seconds...")
            await asyncio.sleep(30)  # Shorter retry on error

# Function to start the collector in a separate thread
def start_collector_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(collector_loop())

# Define routes
@app.route('/')
def index():
    # Default view shows ALL messages - no filter by default
    show_ton_only = request.args.get('ton_only', 'false').lower() == 'true'
    
    if show_ton_only:
        # User requested TON-only filter
        messages = TelegramMessage.query.filter_by(is_ton_dev=True).order_by(TelegramMessage.timestamp.desc()).limit(100).all()
    else:
        # Get ALL messages, without filtering
        messages = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).limit(100).all()
    
    # Count stats
    ton_count = TelegramMessage.query.filter_by(is_ton_dev=True).count()
    all_count = TelegramMessage.query.count()
    
    return render_template('index.html', 
                          messages=messages, 
                          ton_count=ton_count,
                          all_count=all_count,
                          show_ton_only=show_ton_only)

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Interactive setup for Telegram API credentials"""
    if request.method == 'POST':
        api_id = request.form.get('api_id')
        api_hash = request.form.get('api_hash')
        phone = request.form.get('phone')
        
        # Set environment variables
        os.environ['TELEGRAM_API_ID'] = api_id
        os.environ['TELEGRAM_API_HASH'] = api_hash
        
        return render_template('setup_complete.html')
    
    return render_template('setup.html')

@app.route('/database')
def database_info():
    """View database info"""
    ton_count = TelegramMessage.query.filter_by(is_ton_dev=True).count()
    all_count = TelegramMessage.query.count()
    
    channels = db.session.query(
        TelegramMessage.channel_id,
        TelegramMessage.channel_title,
        TelegramMessage.is_ton_dev,
        db.func.count(TelegramMessage.id).label('count')
    ).group_by(
        TelegramMessage.channel_id,
        TelegramMessage.channel_title,
        TelegramMessage.is_ton_dev
    ).all()
    
    return render_template('database.html', 
                          ton_count=ton_count,
                          all_count=all_count,
                          channels=channels)

# Run the application
if __name__ == "__main__":
    with app.app_context():
        # Use existing tables
        logger.info("Using existing database tables")
        # Create tables if they don't exist
        db.create_all()

    # Start collector in a separate thread
    logger.info("Starting simplified Telegram collector and server")
    collector_thread = threading.Thread(target=start_collector_thread, daemon=True)
    collector_thread.start()

    # Start Flask server on a specific port to avoid conflicts
    app.run(host="0.0.0.0", port=3000, debug=False)
