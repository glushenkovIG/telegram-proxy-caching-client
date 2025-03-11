from flask import render_template, jsonify, request
from app import app, db, logger
from collector import ensure_single_collector
from models import TelegramMessage
from datetime import datetime, timedelta
import atexit
import os

@app.route('/')
def index():
    # Check if session is valid - use Replit's persistent storage path
    session_path = os.path.join(os.environ.get('REPL_HOME', ''), 'ton_collector_session.session')
    session_valid = os.path.exists(session_path) and os.path.getsize(session_path) > 0

    # Fetch data for Telegram Cache Proxy dashboard
    messages = []
    all_count = 0
    ton_count = 0
    channels = []
    last_3_days_count = 0
    last_7_days_count = 0
    channel_activity = []
    last_7_days_activity = []

    try:
        # Get total message count
        all_count = db.session.query(TelegramMessage).count()

        # Get TON dev message count
        ton_count = db.session.query(TelegramMessage).filter_by(is_ton_dev=True).count()

        # Get last 3 days statistics
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        last_3_days_count = db.session.query(TelegramMessage).filter(
            TelegramMessage.timestamp >= three_days_ago
        ).count()

        # Get last 7 days statistics
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        last_7_days_count = db.session.query(TelegramMessage).filter(
            TelegramMessage.timestamp >= seven_days_ago
        ).count()

        # Get message leaderboard by incoming and outgoing messages (overall)
        channel_activity = db.session.query(
            TelegramMessage.channel_title,
            db.func.count(TelegramMessage.id).filter(TelegramMessage.is_outgoing == False).label('incoming'),
            db.func.count(TelegramMessage.id).filter(TelegramMessage.is_outgoing == True).label('outgoing'),
            db.func.count(TelegramMessage.id).label('total')
        ).group_by(TelegramMessage.channel_title).order_by(db.desc('total')).limit(10).all()

        # Get last 7 days activity leaderboard
        last_7_days_activity = db.session.query(
            TelegramMessage.channel_title,
            db.func.count(TelegramMessage.id).filter(TelegramMessage.is_outgoing == False).label('incoming'),
            db.func.count(TelegramMessage.id).filter(TelegramMessage.is_outgoing == True).label('outgoing'),
            db.func.count(TelegramMessage.id).label('total')
        ).filter(
            TelegramMessage.timestamp >= seven_days_ago
        ).group_by(TelegramMessage.channel_title).order_by(db.desc('total')).limit(10).all()

        # Get channel statistics
        channels = db.session.query(
            TelegramMessage.channel_title,
            db.func.count(TelegramMessage.id).label('count'),
            db.func.bool_or(TelegramMessage.is_ton_dev).label('is_ton_dev')
        ).group_by(TelegramMessage.channel_title).order_by(db.desc('count')).all()

        # Get the 100 most recent messages
        messages = db.session.query(TelegramMessage).order_by(
            TelegramMessage.timestamp.desc()
        ).limit(100).all()

        logger.info(f"Loaded {len(messages)} messages and {len(channels)} channels for display")
    except Exception as e:
        logger.error(f"Error loading data for UI: {str(e)}")

    return render_template('index.html', 
                          messages=messages, 
                          all_count=all_count,
                          ton_count=ton_count,
                          last_3_days_count=last_3_days_count,
                          last_7_days_count=last_7_days_count,
                          channel_activity=channel_activity,
                          last_7_days_activity=last_7_days_activity,
                          channels=channels,
                          session_valid=session_valid)

@app.route('/status')
def status():
    """Health check endpoint"""
    return jsonify({"status": "running"})

@app.route('/setup')
def setup():
    """Setup page for creating a new Telegram session"""
    # Check if session exists in Replit's persistent storage
    session_path = os.path.join(os.environ.get('REPL_HOME', ''), 'ton_collector_session.session')
    session_exists = os.path.exists(session_path)
    is_deployment = os.environ.get('REPLIT_DEPLOYMENT', False)

    return render_template('setup.html', 
                         session_exists=session_exists,
                         is_deployment=is_deployment)

@app.route('/setup_process', methods=['POST'])
def setup_process():
    """Process the setup form and create a new session"""
    try:
        api_id = request.form.get('api_id')
        api_hash = request.form.get('api_hash')
        phone = request.form.get('phone')

        # Store credentials temporarily for session creation
        os.environ['TELEGRAM_API_ID'] = api_id
        os.environ['TELEGRAM_API_HASH'] = api_hash

        # Restart collector to create new session
        if collector_thread and collector_thread.is_alive():
            logger.info("Stopping existing collector thread...")
            # The thread will exit gracefully on next iteration

        return jsonify({
            "status": "success",
            "message": "Configuration saved successfully. Please restart the collector."
        })
    except Exception as e:
        logger.error(f"Setup process failed: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Setup failed: {str(e)}"
        }), 500

@app.route('/setup_complete')
def setup_complete():
    """Setup completion page"""
    return render_template('setup_complete.html')


# Start the collector thread when the app starts
collector_thread = None

def start_collector():
    """Initialize and start the collector thread"""
    global collector_thread
    try:
        ensure_single_collector()
        from collector import collector_thread as ct
        collector_thread = ct
        logger.info("Collector thread started successfully")
    except Exception as e:
        logger.error(f"Failed to start collector: {str(e)}")
        # Don't let collector failure prevent web server from starting
        pass

# Register cleanup function
def cleanup():
    """Cleanup function to be called on shutdown"""
    if collector_thread and collector_thread.is_alive():
        logger.info("Shutting down collector thread...")

if __name__ == "__main__":
    try:
        # Initialize database first
        with app.app_context():
            db.create_all()

        # Start collector with app context
        with app.app_context():
            start_collector()

        # Register cleanup
        atexit.register(cleanup)

        # Start Flask server
        port = int(os.environ.get("PORT", 5000))
        logger.info(f"Starting Flask server on port {port}")
        app.run(host="0.0.0.0", port=port, debug=True)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise