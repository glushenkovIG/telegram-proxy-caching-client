from flask import render_template
from app import app, logger
from collector import ensure_single_collector
import atexit

@app.route('/')
def index():
    return render_template('index.html')

# Start the collector thread when the app starts
collector_thread = None

def start_collector():
    global collector_thread
    # Start collector in background
    ensure_single_collector()
    from collector import collector_thread as ct
    collector_thread = ct
    
# Register cleanup function
def cleanup():
    if collector_thread and collector_thread.is_alive():
        logger.info("Shutting down collector thread...")
        # We can't directly stop a thread, but we can try to terminate the process

if __name__ == "__main__":
    # Start collector with app context
    with app.app_context():
        start_collector()
    
    # Register cleanup
    atexit.register(cleanup)

    # Start Flask server
    app.run(host="0.0.0.0", port=5000, debug=True)