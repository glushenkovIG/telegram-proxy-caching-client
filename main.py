
from flask import render_template, jsonify
from app import app, db, logger
from models import TelegramMessage
from collector import ensure_single_collector
import atexit
import os

@app.route('/')
def index():
    # Fetch recent messages to display
    messages = []
    all_count = 0
    try:
        # Get total count
        all_count = db.session.query(TelegramMessage).count()
        
        # Get the 100 most recent messages
        messages = db.session.query(TelegramMessage).order_by(
            TelegramMessage.timestamp.desc()
        ).limit(100).all()
        logger.info(f"Loaded {len(messages)} messages for display out of {all_count} total")
    except Exception as e:
        logger.error(f"Error loading messages for UI: {str(e)}")
    
    return render_template('index.html', messages=messages, all_count=all_count)

@app.route('/status')
def status():
    return jsonify({"status": "running"})

@app.route('/database')
def database_stats():
    try:
        # Get total message count
        all_count = db.session.query(TelegramMessage).count()
        
        # Get TON dev message count
        ton_count = db.session.query(TelegramMessage).filter_by(is_ton_dev=True).count()
        
        # Get channel statistics
        # Using bool_or instead of max for boolean aggregation
        channels_query = db.session.query(
            TelegramMessage.channel_title,
            db.func.count(TelegramMessage.id).label('count'),
            db.func.bool_or(TelegramMessage.is_ton_dev).label('is_ton_dev')
        ).group_by(TelegramMessage.channel_title).order_by(db.desc('count')).all()
        
        # Get count of accessible channels
        total_accessible_channels = len(channels_query)
        
        return render_template(
            'database.html',
            all_count=all_count,
            ton_count=ton_count,
            channels=channels_query,
            total_accessible_channels=total_accessible_channels
        )
    except Exception as e:
        logger.error(f"Error loading database stats: {str(e)}")
        return f"Error loading database stats: {str(e)}", 500

# Start the collector thread when the app starts
collector_thread = None

def start_collector():
    global collector_thread
    try:
        # Start collector in background
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
