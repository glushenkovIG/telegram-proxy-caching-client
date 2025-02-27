import os
import logging
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy
db = SQLAlchemy(model_class=Base)

# create the app
app = Flask(__name__)

# configure the PostgreSQL database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 20,
    "max_overflow": 5
}
app.secret_key = os.environ.get("SESSION_SECRET")

# initialize the app with the extension
db.init_app(app)

with app.app_context():
    # Make sure to import the models here or their tables won't be created
    import models  # noqa: F401
    db.create_all()
    logger.info("Database tables created successfully")

@app.route('/')
def index():
    try:
        from models import TelegramMessage
        messages = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).limit(100).all()
        logger.info(f"Retrieved {len(messages)} messages from database")
        return render_template('index.html', messages=messages)
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return f"Error loading messages: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)