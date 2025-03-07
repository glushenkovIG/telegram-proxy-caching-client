
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
    try:
        # Get the 10 most recent messages
        messages = db.session.query(TelegramMessage).order_by(
            TelegramMessage.timestamp.desc()
        ).limit(10).all()
        logger.info(f"Loaded {len(messages)} messages for display")
    except Exception as e:
        logger.error(f"Error loading messages for UI: {str(e)}")
    
    return render_template('index.html', messages=messages)

@app.route('/status')
def status():
    return jsonify({"status": "running"})

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
