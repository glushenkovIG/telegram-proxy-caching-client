import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database base class
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def create_app():
    app = Flask(__name__)

    # Configure database
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.secret_key = os.environ.get("SESSION_SECRET")

    # Initialize database with app
    db.init_app(app)

    with app.app_context():
        # Import models here to avoid circular imports
        from models import TelegramMessage  # noqa: F401
        
        # Check if tables exist before creating them
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if not inspector.has_table('telegram_messages'):
            db.create_all()
            logger.info("Database tables created for the first time")
        else:
            logger.info("Using existing database tables")

        # Register blueprints after models are created
        from routes import bp
        app.register_blueprint(bp)

    return app

# Create application instance
app = create_app()
logger.info("Application created successfully")

if __name__ == "__main__":
    # ALWAYS serve the app on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)