
import os
import logging
import asyncio
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Blueprint
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

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
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
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
        logger.info(f"Channel '{channel_title}' exactly matched TON channel: {channel_lower}")
        return True
    
    # Check for keyword match
    for keyword in ton_keywords:
        if keyword in channel_lower:
            logger.info(f"Channel '{channel_title}' matched TON keyword: {keyword}")
            return True
    
    return False

# Telegram message collector
async def collect_messages():
    """Main collection function"""
    try:
        session_path = 'ton_collector_session.session'
        if not os.path.exists(session_path):
            logger.error("No session file found. Please authenticate first.")
            return

        # Config values should be set in environment variables
        api_id = int(os.environ.get("TELEGRAM_API_ID", 0))
        api_hash = os.environ.get("TELEGRAM_API_HASH", "")
        
        if not api_id or not api_hash:
            logger.error("Telegram API credentials not configured")
            return

        # Use existing session
        client = TelegramClient(session_path, api_id, api_hash)

        await client.connect()
        if not await client.is_user_authorized():
            logger.error("Session exists but unauthorized. Please authenticate first")
            await client.disconnect()
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
                    
                    # Limit to 10 messages per channel for initial fetch
                    message_limit = 10
                    
                    # Get only the most recent messages
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
        if 'client' in locals() and client:
            await client.disconnect()

# Main collector loop
async def main_collector():
    """Main loop with backoff and status reporting"""
    while True:
        try:
            logger.info("Starting collection cycle...")
            await collect_messages()
            logger.info("Collection complete, waiting 120 seconds...")
            await asyncio.sleep(120)  # Check every 2 minutes
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            await asyncio.sleep(60)

# Thread function to run the collector
def run_collector_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_collector())

# Flask routes
@app.route('/')
def index():
    # Get filter from query parameters
    filter_type = request.args.get('filter', 'all')  # Default to ALL messages

    # Base query
    query = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).limit(100)

    # Apply filter
    if filter_type == 'ton_dev':
        query = query.filter_by(is_ton_dev=True)
    # 'all' filter doesn't need additional conditions

    messages = query.all()
    return render_template('index.html', messages=messages, current_filter=filter_type)

@app.route('/ton-dev')
def ton_dev():
    """View showing only TON Dev messages"""
    return index()

@app.route('/status')
def status():
    try:
        message_count = TelegramMessage.query.count()
        ton_dev_count = TelegramMessage.query.filter_by(is_ton_dev=True).count()
        non_ton_dev_count = message_count - ton_dev_count
        
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
            'non_ton_dev_messages': non_ton_dev_count,
            'channels_monitored': channel_count,
            'latest_message_time': latest_message.timestamp.isoformat() if latest_message else None,
        })
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# Telegram client setup (just for reference, moved into a simplified function)
def setup_telegram_client():
    """Interactive setup for Telegram client"""
    import sys
    
    print("Setting up Telegram client...")
    api_id = input("Enter your Telegram API ID: ")
    api_hash = input("Enter your Telegram API Hash: ")
    
    client = TelegramClient('ton_collector_session', int(api_id), api_hash)

    async def authenticate():
        await client.connect()
        if not await client.is_user_authorized():
            phone = input("Enter your phone number (with country code): ")
            await client.send_code_request(phone)
            code = input("Enter the code you received: ")
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                password = input("Enter your 2FA password: ")
                await client.sign_in(password=password)
        
        print("Successfully authenticated!")
        await client.disconnect()
    
    asyncio.run(authenticate())
    return True

# Main entry point
if __name__ == "__main__":
    # Start collector in a separate thread
    collector_thread = threading.Thread(target=run_collector_thread)
    collector_thread.daemon = True
    collector_thread.start()
    
    # ALWAYS serve the app on port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
