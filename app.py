import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import atexit

collector_thread = None


def start_collector():
    """Initialize and start the collector thread"""
    global collector_thread
    logger.info("Starting collector thread...")
    try:
        # Stop existing collector if running
        if collector_thread and collector_thread.is_alive():
            logger.info("Stopping existing collector thread...")
            # The thread will exit gracefully on next iteration
            import time
            time.sleep(1)  # Give a brief moment for thread to clean up

        # Check if session exists and is valid
        session_path = os.path.join(os.environ.get('REPL_HOME', ''),
                                    'ton_collector_session.session')
        session_valid = os.path.exists(session_path) and os.path.getsize(
            session_path) > 0

        if not session_valid:
            logger.warning(
                "No valid session found. Collector will start but may not collect messages until setup is complete."
            )

        # Reload the collector module to refresh state
        import importlib
        import sys
        if 'collector' in sys.modules:
            importlib.reload(sys.modules['collector'])

        # Start new collector thread
        from collector import ensure_single_collector
        ensure_single_collector()

        # Get the updated thread reference
        from collector import collector_thread as ct
        collector_thread = ct

        # Verify the thread was created and is running
        if collector_thread and collector_thread.is_alive():
            logger.info("Collector thread started successfully")
            return True
        else:
            logger.error("Collector thread was not started properly")
            return False
    except Exception as e:
        logger.error(f"Failed to start collector: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # Don't let collector failure prevent web server from starting
        return False


# Register cleanup function
def cleanup():
    """Cleanup function to be called on shutdown"""
    if collector_thread and collector_thread.is_alive():
        logger.info("Shutting down collector thread...")


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Initialize database base class
class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# configure the database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Added from original

# initialize the app with the extension, flask-sqlalchemy >= 3.0.x
db.init_app(app)

with app.app_context():
    # Make sure to import the models here or their tables won't be created
    import models  # noqa: F401
    try:
        db.create_all()

        start_collector()

        # Register cleanup
        atexit.register(cleanup)

    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise
