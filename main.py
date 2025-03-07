import os
import asyncio
import logging
import threading
import socket
import time
from datetime import datetime, timedelta
from telethon import TelegramClient
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from telethon.tl.types import Channel, Chat, User
from werkzeug.serving import is_running_from_reloader
from collector import ensure_single_collector

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def wait_for_port_availability(port, max_retries=5, retry_delay=2):
    """Wait for port to become available with retries"""
    for attempt in range(max_retries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                s.close()  # Explicitly close the socket
                return True
            except socket.error as e:
                logger.warning(f"Port {port} not available, attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                continue
    return False

# Initialize database base class
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

try:
    # Create Flask app
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///messages.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    db.init_app(app)

except Exception as e:
    logger.error(f"Error during Flask app initialization: {str(e)}", exc_info=True)
    raise

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


@app.route('/api/collector-status')
def collector_status():
    try:
        # Get the most recent message timestamp
        latest_msg = TelegramMessage.query.order_by(
            TelegramMessage.timestamp.desc()
        ).first()

        if not latest_msg:
            return jsonify({
                'status': 'inactive',
                'last_message_time': None
            })

        # Calculate time since last message
        now = datetime.utcnow()
        minutes_since_last = int((now - latest_msg.timestamp).total_seconds() / 60)

        # Get count of messages in the last hour
        recent_messages = TelegramMessage.query.filter(
            TelegramMessage.timestamp >= now - timedelta(hours=1)
        ).count()

        # Determine collector status
        if minutes_since_last <= 60:  # Within last hour
            status = 'active'
        else:
            status = 'inactive'

        return jsonify({
            'status': status,
            'recent_messages': recent_messages,
            'minutes_since_last': minutes_since_last,
            'last_message_time': latest_msg.timestamp.isoformat()
        })

    except Exception as e:
        logger.error(f"Error in collector status: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

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
            logger.error(f"Database setup error: {str(e)}", exc_info=True)
            raise

    # Wait for port availability
    if not wait_for_port_availability(5000):
        logger.error("Could not bind to port 5000 after maximum retries")
        raise RuntimeError("Port 5000 is unavailable")

    # Start the Flask server
    try:
        logger.info("Starting Flask server on port 5000")
        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        logger.error(f"Flask server error: {str(e)}", exc_info=True)
        raise