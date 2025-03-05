import threading
import os
import time
import logging
from app import app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_flask():
    from app import app
    app.run(host="0.0.0.0", port=5000, debug=False)

def run_collector():
    # Wait for Flask app to initialize
    time.sleep(5)
    # Verify database tables exist but don't recreate them
    from app import app, db
    with app.app_context():
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            if not inspector.has_table('telegram_messages'):
                db.create_all()
                logger.info("Database tables created for the first time")
            else:
                logger.info("Using existing database schema")
        except Exception as e:
            logger.error(f"Error checking database tables: {str(e)}")
    
    import asyncio
    from collector import main
    asyncio.run(main())

if __name__ == "__main__":
    logger.info("Starting Telegram Collector System")

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Flask server started in background")

    # Run collector in main thread
    run_collector()