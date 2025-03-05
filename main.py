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
        ChatPhoto, UserEmpty
    )

    if isinstance(entity, User):
        if isinstance(entity, UserEmpty):
            return 'deleted_account'
        return 'private'
    elif isinstance(entity, Chat) or isinstance(entity, ChatForbidden):
        return 'group'
    elif isinstance(entity, Channel) or isinstance(entity, ChannelForbidden):
        if getattr(entity, 'megagroup', False):
            return 'supergroup'
        return 'channel'
    return 'unknown'


async def collect_messages():
    """Main collection function"""
    try:
        session_path = 'ton_collector_session.session'
        if not os.path.exists(session_path):
            logger.error("No session file found. Please run the setup first to authenticate.")
            return

        # Get API credentials - hardcoded for now to ensure they're set
        # You should move these to environment variables in production
        api_id = 12345678  # Replace with your actual API ID
        api_hash = "your_api_hash_here"  # Replace with your actual API hash

        # Use existing session
        client = TelegramClient(session_path, api_id, api_hash)

        await client.connect()
        try:
            is_authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=30)
            if not is_authorized:
                logger.error("Session exists but unauthorized. Please run the setup first")
                return
        except asyncio.TimeoutError:
            logger.error("Connection timeout. Reconnecting...")
            await client.disconnect()
            await asyncio.sleep(5)
            await client.connect()
            is_authorized = await client.is_user_authorized()
            if not is_authorized:
                logger.error("Session exists but unauthorized after retry. Please run the setup first")
                return

        logger.info("Successfully connected using existing session")

        # Get all dialogs with a larger limit to ensure we get external channels
        dialogs = await client.get_dialogs(limit=200)  # Increased from default
        logger.info(f"Found {len(dialogs)} dialogs")

        # Store the total accessible channels count for later use
        app.total_accessible_channels = len(dialogs)

        # Log all dialog titles to debug
        dialog_titles = [getattr(d, 'title', str(getattr(d, 'id', 'unknown'))) for d in dialogs]
        logger.info(f"Dialog titles: {', '.join(dialog_titles[:20])}...")

        # Process each dialog
        for dialog in dialogs:
            try:
                if not hasattr(dialog, 'id'):
                    logger.warning("Skipping dialog without ID")
                    continue

                channel_id = str(dialog.id)
                channel_title = getattr(dialog, 'title', channel_id)

                # Use improved dialog type detection
                dialog_type = get_proper_dialog_type(dialog.entity)

                # Check if it's a TON Dev channel
                is_ton_dev = should_be_ton_dev(channel_title)

                # Process ALL channels, saving messages from every dialog
                logger.info(f"Processing {dialog_type}: {channel_title} (is_ton_dev={is_ton_dev})")

                # Get latest message ID from database
                with app.app_context():
                    # Force immediate processing of more messages (increased limit)
                    message_limit = 200  # Increased for more history

                    # Get latest stored message for this channel
                    latest_msg = TelegramMessage.query.filter_by(
                        channel_id=channel_id
                    ).order_by(TelegramMessage.message_id.desc()).first()

                    latest_id = latest_msg.message_id if latest_msg else 0
                    logger.info(f"Latest message ID in database for {channel_title}: {latest_id}")

                    # Process messages
                    message_count = 0
                    async for message in client.iter_messages(dialog, limit=message_limit):
                        if message.id <= latest_id and latest_id != 0:
                            logger.info(f"Skipping message {message.id} in {channel_title} - already processed")
                            continue  # Skip this message but check others

                        # Save ALL messages with text content, regardless of channel type
                        if message.text:
                            try:
                                # Check if message is outgoing
                                is_outgoing = getattr(message, 'out', False)

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
                                message_count += 1
                                logger.info(f"Saved message {message.id} from {channel_title} ({dialog_type}, {'outbox' if is_outgoing else 'inbox'})")
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
    consecutive_errors = 0
    while True:
        try:
            # Add more detailed progress reporting
            logger.info("=== STARTING COLLECTION CYCLE ===")

            # Get current counts for progress tracking
            with app.app_context():
                before_count = TelegramMessage.query.count()
                before_ton_count = TelegramMessage.query.filter_by(is_ton_dev=True).count()

            # Run collection
            await collect_messages()

            # Report how many new messages were collected
            with app.app_context():
                after_count = TelegramMessage.query.count()
                after_ton_count = TelegramMessage.query.filter_by(is_ton_dev=True).count()

                new_messages = after_count - before_count
                new_ton_messages = after_ton_count - before_ton_count

                logger.info(f"Collection complete - Added {new_messages} total messages ({new_ton_messages} TON messages)")
                logger.info(f"Database now has {after_count} total messages ({after_ton_count} TON messages)")
                logger.info("Waiting 10 seconds until next collection...")

            # Reset error counter on successful run
            consecutive_errors = 0
            await asyncio.sleep(10)  # Check more frequently
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Error in main loop: {str(e)}", exc_info=True)

            # Add escalating backoff for repeated errors
            retry_wait = min(5 * consecutive_errors, 60)  # Cap at 60 seconds
            logger.info(f"Retrying collection in {retry_wait} seconds... (error count: {consecutive_errors})")

            # If many consecutive errors, try to reconnect the session
            if consecutive_errors > 5:
                logger.warning("Multiple consecutive errors, attempting to restart the collector...")
                # Kill the current session and force a new connection on next cycle
                try:
                    os.system("rm -f ton_collector_session.session-journal")  # Clear session journal
                except Exception as se:
                    logger.error(f"Error clearing session journal: {str(se)}")

            await asyncio.sleep(retry_wait)

# Function to start the collector in a separate thread
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

        # Convert to dictionary for easier template access
        dialog_counts = {
            'total': 0,
            'private': {'count': 0, 'messages': 0},
            'group': {'count': 0, 'messages': 0},
            'supergroup': {'count': 0, 'messages': 0},
            'channel': {'count': 0, 'messages': 0},
            'unknown': {'count': 0, 'messages': 0},
            'deleted_account': {'count': 0, 'messages': 0} #added for new dialog type
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
            'group': {'count': 0, 'messages': 0},
            'supergroup': {'count': 0, 'messages': 0},
            'channel': {'count': 0, 'messages': 0},
            'unknown': {'count': 0, 'messages': 0},
            'deleted_account': {'count': 0, 'messages': 0} #added for new dialog type
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
                'total_messages': TelegramMessage.query.filter(
                    TelegramMessage.timestamp >= start_of_day,
                    TelegramMessage.timestamp < end_of_day
                ).count(),
                'ton_messages': TelegramMessage.query.filter(
                    TelegramMessage.timestamp >= start_of_day,
                    TelegramMessage.timestamp < end_of_day,
                    TelegramMessage.is_ton_dev == True
                ).count(),
                'by_type': {}
            }

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

            stats.append(daily_stats)

        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Run the application
if __name__ == "__main__":
    with app.app_context():
        try:
            # NEVER recreate database, only add missing columns
            logger.info("Checking database schema - NO RECREATION")

            # Check if table exists
            inspector = db.inspect(db.engine)
            if 'telegram_messages' in inspector.get_table_names():
                # Check if columns exist
                columns = [col['name'] for col in inspector.get_columns('telegram_messages')]

                # Add missing is_outgoing column if needed
                if 'is_outgoing' not in columns:
                    logger.info("Adding is_outgoing column to existing table")
                    with db.engine.connect() as conn:
                        conn.execute(db.text("ALTER TABLE telegram_messages ADD COLUMN is_outgoing BOOLEAN DEFAULT FALSE"))
                        conn.commit()

                # Add missing dialog_type column if needed
                if 'dialog_type' not in columns:
                    logger.info("Adding dialog_type column to existing table")
                    with db.engine.connect() as conn:
                        conn.execute(db.text("ALTER TABLE telegram_messages ADD COLUMN dialog_type VARCHAR(20)"))
                        conn.commit()

                logger.info("Table exists and schema is up to date")
            else:
                # Only create tables if they don't exist at all
                logger.info("Tables don't exist, creating initial schema")
                db.create_all()
        except Exception as e:
            logger.error(f"Error checking database schema: {str(e)}")
            # Don't recreate anything on error
            pass

    # Start collector in a separate thread if not running in reloader
    if not is_running_from_reloader():
        logger.info("Starting simplified Telegram collector")
        collector_thread = threading.Thread(target=start_collector_thread, daemon=True)
        collector_thread.start()

    # Let gunicorn handle the server
    if os.environ.get('FLASK_ENV') != 'production':
        logger.info("Starting Flask development server on port 5000")
        app.run(host="0.0.0.0", port=5000, debug=False)