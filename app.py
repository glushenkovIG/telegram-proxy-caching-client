import os
import logging
from flask import Flask, render_template
from models import db, TelegramMessage

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)

    # Configure database
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

    # Initialize database
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

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
        logger.info("Database tables created successfully")
    app.run(host="0.0.0.0", port=5000, debug=True)