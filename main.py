import logging
import os
from flask import Flask
from app import app, db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting simplified Telegram collector and server")

if __name__ == "__main__":
    with app.app_context():
        # Ensure database tables exist
        db.create_all()
    # ALWAYS serve the app on port 5000
    app.run(host='0.0.0.0', port=5000)