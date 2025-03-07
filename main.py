from flask import render_template
from app import app, db, logger
from collector import ensure_single_collector
import atexit

@app.route('/')
def index():
    return render_template('index.html')

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
        logger.info("Starting Flask server on port 5000")
        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise