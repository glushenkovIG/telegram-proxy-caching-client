import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize SQLAlchemy
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    # Configure database
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

    # Initialize extensions
    db.init_app(app)

    @app.route('/')
    def index():
        try:
            messages = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).all()
            logger.info(f"Retrieved {len(messages)} messages from database")
            return render_template('index.html', messages=messages)
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return f"Error loading messages: {str(e)}", 500

    return app

# Create app instance
app = create_app()

# Create tables within app context
with app.app_context():
    from models import TelegramMessage  # Import here to avoid circular imports
    db.create_all()
    logger.info("Database tables created successfully")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)