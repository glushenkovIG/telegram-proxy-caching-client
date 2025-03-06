import os
import asyncio
import logging
import threading
from datetime import datetime, timedelta
from telethon import TelegramClient
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from telethon.tl.types import Channel, Chat, User
from werkzeug.serving import is_running_from_reloader

# Configure logging
logging.basicConfig(level=logging.DEBUG)  # Changed to DEBUG for more info
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
    is_outgoing = db.Column(db.Boolean, default=False)  # False = inbox, True = outbox
    dialog_type = db.Column(db.String(20))  # 'private', 'group', 'channel', 'supergroup'

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

def get_proper_dialog_type(entity):
    """Get the proper dialog type using Telethon's type system"""
    from telethon.tl.types import (
        User, Chat, Channel,
        ChatForbidden, ChannelForbidden,
        ChatPhoto, UserEmpty, Bot
    )

    logger.info(f"Detecting type for entity: {type(entity)} with attributes: {dir(entity)}")

    try:
        # For Channels (supergroups/broadcasts)
        if isinstance(entity, Channel):
            broadcast = getattr(entity, 'broadcast', False)
            megagroup = getattr(entity, 'megagroup', False)
            username = getattr(entity, 'username', None)
            logger.info(f"Channel {entity.id} attributes - broadcast: {broadcast}, megagroup: {megagroup}, username: {username}")

            if broadcast and not megagroup:
                return 'channel'
            elif megagroup:
                if username:
                    return 'public_supergroup'
                return 'private_supergroup'
            return 'channel'  # Default for channels

        # For Users (private chats/bots)
        elif isinstance(entity, User):
            if getattr(entity, 'bot', False):
                return 'bot'
            if getattr(entity, 'deleted', False) or isinstance(entity, UserEmpty):
                return 'deleted_account'
            return 'private'

        # For Small Groups
        elif isinstance(entity, (Chat, ChatForbidden)):
            return 'group'

        # Unknown type - log details for debugging
        logger.error(f"Unknown entity type: {type(entity).__name__}, dir: {dir(entity)}")
        return 'unknown'

    except Exception as e:
        logger.error(f"Error in get_proper_dialog_type: {str(e)}")
        return 'unknown'

async def collect_messages():
    """Main collection function"""
    client = None
    try:
        session_path = 'ton_collector_session.session'

        # Get API credentials from environment
        api_id = os.environ.get('TELEGRAM_API_ID')
        api_hash = os.environ.get('TELEGRAM_API_HASH')

        if not api_id or not api_hash:
            logger.error("Missing API credentials in environment variables")
            return

        # Use existing session
        client = TelegramClient(session_path, api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            logger.error("Session unauthorized. Please run setup first")
            return

        logger.info("Successfully connected and authorized")

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
                        channel_title = getattr(dialog, 'title', channel_id)

                        # Get dialog type
                        entity = dialog.entity
                        dialog_type = get_proper_dialog_type(entity)

                        # Get latest messages
                        with app.app_context():
                            # Get latest stored message ID
                            latest_msg = TelegramMessage.query.filter_by(
                                channel_id=channel_id
                            ).order_by(TelegramMessage.message_id.desc()).first()

                            latest_id = latest_msg.message_id if latest_msg else 0
                            logger.debug(f"Processing {channel_title} from message_id > {latest_id}")

                            # Process new messages with smaller batch size
                            async for message in client.iter_messages(dialog, limit=20):
                                if message.id <= latest_id and latest_id != 0:
                                    continue  # Skip processed messages

                                if message.text:  # Only process text messages
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
                                            dialog_type=dialog_type
                                        )
                                        db.session.add(new_msg)
                                        db.session.commit()
                                        logger.debug(f"Saved message {message.id} from {channel_title}")
                                    except Exception as e:
                                        logger.error(f"Error saving message: {str(e)}")
                                        db.session.rollback()

                    except Exception as e:
                        logger.error(f"Error processing dialog {channel_title}: {str(e)}")
                        continue

                # Short sleep between collection cycles
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

# Main collector loop with backoff
async def collector_loop():
    consecutive_errors = 0
    while True:
        try:
            logger.info("Starting collection cycle")
            await collect_messages()
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            retry_wait = min(5 * 2 ** consecutive_errors, 300)
            logger.error(f"Error in collector loop (attempt {consecutive_errors}): {str(e)}")
            logger.info(f"Retrying in {retry_wait} seconds...")
            await asyncio.sleep(retry_wait)

# Collector thread starter
def start_collector_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(collector_loop())

# Define routes
@app.route('/')
def index():
    # Get filter parameters
    show_ton_only = request.args.get('ton_only', 'false').lower() == 'true'
    show_outbox_only = request.args.get('outbox_only', 'false').lower() == 'true'

    try:
        # Build query based on filters
        query = TelegramMessage.query

        if show_ton_only:
            query = query.filter_by(is_ton_dev=True)
        if show_outbox_only:
            query = query.filter_by(is_outgoing=True)

        # Get messages with filters applied
        messages = query.order_by(TelegramMessage.timestamp.desc()).limit(100).all()

        # Get message statistics
        ton_count = TelegramMessage.query.filter_by(is_ton_dev=True).count()
        all_count = TelegramMessage.query.count()
        outbox_count = TelegramMessage.query.filter_by(is_outgoing=True).count()

        # Get dialog statistics with detailed counts
        dialog_stats = db.session.query(
            TelegramMessage.dialog_type,
            db.func.count(db.distinct(TelegramMessage.channel_id)).label('dialog_count'),
            db.func.count(TelegramMessage.id).label('message_count')
        ).group_by(TelegramMessage.dialog_type).all()

        # Update dialog_counts dictionary initialization
        dialog_counts = {
            'total': 0,
            'private': {'count': 0, 'messages': 0},
            'bot': {'count': 0, 'messages': 0},
            'group': {'count': 0, 'messages': 0},
            'channel': {'count': 0, 'messages': 0},
            'public_supergroup': {'count': 0, 'messages': 0},
            'private_supergroup': {'count': 0, 'messages': 0},
            'deleted_account': {'count': 0, 'messages': 0},
            'unknown': {'count': 0, 'messages': 0}
        }

        # Populate dialog counts
        for dialog_type, dialog_count, message_count in dialog_stats:
            if dialog_type in dialog_counts:
                dialog_counts[dialog_type] = {
                    'count': dialog_count,
                    'messages': message_count
                }
            else:
                dialog_counts['unknown'] = {
                    'count': dialog_count,
                    'messages': message_count
                }
            dialog_counts['total'] += dialog_count

        # Add last message timestamp for proper updates
        latest_msg = TelegramMessage.query.order_by(
            TelegramMessage.timestamp.desc()
        ).first()

        last_update = latest_msg.timestamp.isoformat() if latest_msg else None


    except Exception as e:
        logger.error(f"Database error in index route: {str(e)}", exc_info=True)
        messages = []
        ton_count = 0
        all_count = 0
        outbox_count = 0
        dialog_counts = {
            'total': 0,
            'private': {'count': 0, 'messages': 0},
            'bot': {'count': 0, 'messages': 0},
            'group': {'count': 0, 'messages': 0},
            'channel': {'count': 0, 'messages': 0},
            'public_supergroup': {'count': 0, 'messages': 0},
            'private_supergroup': {'count': 0, 'messages': 0},
            'deleted_account': {'count': 0, 'messages': 0},
            'unknown': {'count': 0, 'messages': 0}
        }
        last_update = None

    return render_template('index.html',
                         messages=messages,
                         ton_count=ton_count,
                         all_count=all_count,
                         outbox_count=outbox_count,
                         dialog_counts=dialog_counts,
                         show_ton_only=show_ton_only,
                         show_outbox_only=show_outbox_only,
                         last_update=last_update)

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

    # Set this value based on your last collection run
    # or call async function to get it (more complex)
    total_accessible_channels = getattr(app, 'total_accessible_channels', 0)

    return render_template('database.html',
                          ton_count=ton_count,
                          all_count=all_count,
                          channels=channels,
                          total_accessible_channels=total_accessible_channels)

# Add statistics endpoint for AJAX updates
@app.route('/api/stats')
def get_stats():
    try:
        # Get last 3 days stats
        now = datetime.utcnow()
        stats = []

        for days_ago in range(3):
            date = now - timedelta(days=days_ago)
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)

            daily_stats = {
                'date': start_of_day.strftime('%Y-%m-%d'),
                'total_messages': 0,
                'ton_messages': 0,
                'by_type': {}
            }
            
            # Safely get counts with error handling
            try:
                daily_stats['total_messages'] = TelegramMessage.query.filter(
                    TelegramMessage.timestamp >= start_of_day,
                    TelegramMessage.timestamp < end_of_day
                ).count()
                
                daily_stats['ton_messages'] = TelegramMessage.query.filter(
                    TelegramMessage.timestamp >= start_of_day,
                    TelegramMessage.timestamp < end_of_day,
                    TelegramMessage.is_ton_dev == True
                ).count()
                
                # Get counts by dialog type
                dialog_types = db.session.query(
                    TelegramMessage.dialog_type,
                    db.func.count(TelegramMessage.id)
                ).filter(
                    TelegramMessage.timestamp >= start_of_day,
                    TelegramMessage.timestamp < end_of_day
                ).group_by(TelegramMessage.dialog_type).all()

                for dtype, count in dialog_types:
                    daily_stats['by_type'][dtype or 'unknown'] = count
            except Exception as inner_e:
                logger.error(f"Error collecting daily stats: {str(inner_e)}")
                # Don't fail the whole request, just log the error

            stats.append(daily_stats)

        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}", exc_info=True)
        return jsonify({'error': str(e), 'status': 'error'}), 200  # Return 200 to avoid CORS issues


# Run the application
if __name__ == "__main__":
    with app.app_context():
        try:
            # Check database schema
            inspector = db.inspect(db.engine)
            if 'telegram_messages' not in inspector.get_table_names():
                logger.info("Creating initial database schema")
                db.create_all()

        except Exception as e:
            logger.error(f"Database setup error: {str(e)}")

    # Start collector in a separate thread if not running in reloader
    if not is_running_from_reloader():
        logger.info("Starting collector thread in production mode")
        collector_thread = threading.Thread(target=start_collector_thread, daemon=False)  # Changed to non-daemon
        collector_thread.start()

    # Start the Flask server
    if os.environ.get('FLASK_ENV') == 'production':
        # Let gunicorn handle the server
        pass
    else:
        app.run(host="0.0.0.0", port=5000, debug=False)

@app.route('/api/collector-status')
def collector_status():
    """Check collector status"""
    try:
        # Count messages in the last hour to see if collector is working
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        recent_messages = TelegramMessage.query.filter(
            TelegramMessage.timestamp >= one_hour_ago
        ).count()
        
        # Get latest message timestamp
        latest_msg = TelegramMessage.query.order_by(
            TelegramMessage.timestamp.desc()
        ).first()
        
        last_message_time = latest_msg.timestamp if latest_msg else None
        time_since_last = None
        
        if last_message_time:
            time_since_last = (now - last_message_time).total_seconds() / 60  # minutes
        
        return jsonify({
            'status': 'active' if recent_messages > 0 else 'inactive',
            'recent_messages': recent_messages,
            'last_message_time': last_message_time.isoformat() if last_message_time else None,
            'minutes_since_last': round(time_since_last, 1) if time_since_last else None
        })
    except Exception as e:
        logger.error(f"Error checking collector status: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500
