import os
import logging
import asyncio
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database base class
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///messages.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize database with app
db.init_app(app)

# Define model
class TelegramMessage(db.Model):
    __tablename__ = 'telegram_messages'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, nullable=False)
    channel_id = db.Column(db.String(100), nullable=False)
    channel_title = db.Column(db.String(200))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_ton_dev = db.Column(db.Boolean, default=False)

# Initialize database tables if they don't exist
with app.app_context():
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    if not inspector.has_table('telegram_messages'):
        db.create_all()
        logger.info("Database tables created for the first time")
    else:
        logger.info("Using existing database tables")

# Utility function to check if a channel is TON-related
def should_be_ton_dev(channel_title):
    if not channel_title:
        return False

    # List of known TON channel names or keywords
    ton_keywords = [
        "ton", "telegram open network", "the open network", 
        "telegram developers", "tact language"
    ]

    # Exact matches for known TON channels
    ton_channels = [
        "ton dev chat", "ton dev chat (en)", "ton dev chat (ру)", 
        "ton dev chat (中文)", "ton dev news", "ton status", 
        "ton community", "ton society chat", "ton research",
        "ton contests", "ton tact language chat", "ton jobs", 
        "telegram developers community", "botnews", 
        "testnet ton status", "hackers league hackathon",
        "ton society id", "ton data hub"
    ]

    channel_lower = channel_title.lower()

    # Check if it's an exact match
    if channel_lower in ton_channels:
        return True

    # Check for keyword match
    for keyword in ton_keywords:
        if keyword in channel_lower:
            return True

    return False

# Flask routes - only show TON dev messages
@app.route('/')
def index():
    # Only get TON dev messages
    messages = TelegramMessage.query.filter_by(is_ton_dev=True).order_by(TelegramMessage.timestamp.desc()).limit(100).all()
    return render_template('index.html', messages=messages)

@app.route('/status')
def status():
    try:
        message_count = TelegramMessage.query.count()
        ton_dev_count = TelegramMessage.query.filter_by(is_ton_dev=True).count()

        channel_count = db.session.query(TelegramMessage.channel_title)\
                              .distinct()\
                              .count()
        latest_message = TelegramMessage.query\
            .order_by(TelegramMessage.timestamp.desc())\
            .first()

        return jsonify({
            'status': 'healthy',
            'messages_collected': message_count,
            'ton_dev_messages': ton_dev_count,
            'channels_monitored': channel_count,
            'latest_message_time': latest_message.timestamp.isoformat() if latest_message else None,
        })
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# Run the Flask app
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)