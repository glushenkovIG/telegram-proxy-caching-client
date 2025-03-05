
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
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize database with app
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

# Initialize database tables if they don't exist
with app.app_context():
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    if not inspector.has_table('telegram_messages'):
        db.create_all()
        logger.info("Database tables created for the first time")
    else:
        logger.info("Using existing database tables")

# Utility function to check if a channel is TON-related
def should_be_ton_dev(channel_title):
    if not channel_title:
        return False

    # List of known TON channel names or keywords
    ton_keywords = [
        "ton", "telegram open network", "the open network", 
        "telegram developers", "tact language"
    ]

    # Exact matches for known TON channels
    ton_channels = [
        "ton dev chat", "ton dev chat (en)", "ton dev chat (ру)", 
        "ton dev chat (中文)", "ton dev news", "ton status", 
        "ton community", "ton society chat", "ton research",
        "ton contests", "ton tact language chat", "ton jobs", 
        "telegram developers community", "botnews", 
        "testnet ton status", "hackers league hackathon",
        "ton society id", "ton data hub"
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

                # Process all channels, storing all messages
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
                                    is_ton_dev=is_ton_dev  # Mark TON dev channels for filtering
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
def start_collector():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(collector_loop())

# Flask routes - show both TON dev messages and all messages
@app.route('/')
def index():
    # Get filter from query parameters
    filter_type = request.args.get('filter', 'ton_dev')  # Default to TON Dev

    # Base query
    query = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).limit(100)

    # Apply filter
    if filter_type == 'ton_dev':
        query = query.filter_by(is_ton_dev=True)
    # 'all' filter doesn't need additional conditions

    messages = query.all()
    return render_template('index.html', messages=messages, current_filter=filter_type)

@app.route('/status')
def status():
    try:
        message_count = TelegramMessage.query.count()
        ton_dev_count = TelegramMessage.query.filter_by(is_ton_dev=True).count()

        channel_count = db.session.query(TelegramMessage.channel_title)\
                              .distinct()\
                              .count()
        latest_message = TelegramMessage.query\
            .order_by(TelegramMessage.timestamp.desc())\
            .first()

        return jsonify({
            'status': 'healthy',
            'messages_collected': message_count,
            'ton_dev_messages': ton_dev_count,
            'channels_monitored': channel_count,
            'latest_message_time': latest_message.timestamp.isoformat() if latest_message else None,
        })
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# Main entry point
if __name__ == "__main__":
    logger.info("Starting simplified Telegram collector and server")
    
    # Start collector in a background thread
    collector_thread = threading.Thread(target=start_collector, daemon=True)
    collector_thread.start()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5000)
