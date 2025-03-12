from flask import render_template, jsonify, request
from app import app, db, logger
from collector import ensure_single_collector, setup_telegram_session
from models import TelegramMessage
from datetime import datetime, timedelta
import atexit
import os
import json
import asyncio
import sys

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
    """Process the setup form and send verification code"""
    try:
        data = request.get_json()
        phone = data.get('phone')

        if not phone:
            return jsonify({
                "status": "error",
                "message": "Phone number is required"
            }), 400

        # Store phone number temporarily for session creation
        os.environ['TELEGRAM_PHONE'] = phone

        # Start the Telegram session setup asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(setup_telegram_session())
        loop.close()

        if result:
            return jsonify({
                "status": "code_sent",
                "message": "Verification code sent to your Telegram app"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to send verification code"
            }), 500

    except Exception as e:
        logger.error(f"Setup process failed: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Setup failed: {str(e)}"
        }), 500

@app.route('/verify_code', methods=['POST'])
def verify_code():
    """Verify the Telegram authentication code"""
    try:
        data = request.get_json()
        code = data.get('code')

        if not code:
            return jsonify({"status": "error", "message": "No verification code provided"}), 400

        # Store verification code temporarily
        os.environ['TELEGRAM_CODE'] = code

        # Restart collector to create new session
        if collector_thread and collector_thread.is_alive():
            logger.info("Stopping existing collector thread...")
            # The thread will exit gracefully on next iteration

        return jsonify({
            "status": "success",
            "message": "Authentication successful"
        })
    except Exception as e:
        logger.error(f"Code verification failed: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Verification failed: {str(e)}"
        }), 500

@app.route('/setup_complete')
def setup_complete():
    """Setup completion page"""
    return render_template('setup_complete.html')

@app.route('/restart_collector', methods=['POST'])
def restart_collector():
    """Restart the collector thread"""
    try:
        # Check if session exists in Replit's persistent storage
        session_path = os.path.join(os.environ.get('REPL_HOME', ''), 'ton_collector_session.session')
        
        # If the session is invalid, try to remove it
        if os.path.exists(session_path):
            logger.info(f"Removing existing session file: {session_path}")
            os.remove(session_path)
            
        # Restart the collector
        start_collector()
        
        return jsonify({"success": True, "message": "Collector restarted successfully"})
    except Exception as e:
        logger.error(f"Failed to restart collector: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


# Start the collector thread when the app starts
collector_thread = None

def start_collector():
    """Initialize and start the collector thread"""
    global collector_thread
    try:
        # Stop existing collector if running
        if collector_thread and collector_thread.is_alive():
            logger.info("Stopping existing collector thread...")
            # The thread will exit gracefully on next iteration
        
        # Reload the collector module to refresh state
        import importlib
        importlib.reload(sys.modules['collector'])
        
        # Start new collector thread
        ensure_single_collector()
        from collector import collector_thread as ct
        collector_thread = ct
        logger.info("Collector thread started successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to start collector: {str(e)}")
        # Don't let collector failure prevent web server from starting
        return False

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