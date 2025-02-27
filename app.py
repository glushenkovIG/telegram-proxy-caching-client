import os
import logging
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask and SQLAlchemy
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
app.secret_key = os.environ.get("SESSION_SECRET")

# Initialize SQLAlchemy
db.init_app(app)

# Create tables
with app.app_context():
    import models
    db.create_all()
    logger.info("Database tables created")

@app.route('/')
def index():
    """Display messages with pagination"""
    try:
        from models import TelegramMessage
        page = request.args.get('page', 1, type=int)
        per_page = 50

        messages = TelegramMessage.query\
            .order_by(TelegramMessage.timestamp.desc())\
            .paginate(page=page, per_page=per_page)

        return render_template('index.html',
                             messages=messages.items,
                             pagination=messages,
                             total_messages=TelegramMessage.query.count())
    except Exception as e:
        logger.error(f"Error loading messages: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def status():
    """Check application status"""
    try:
        from models import TelegramMessage
        count = TelegramMessage.query.count()
        latest = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).first()

        return jsonify({
            'status': 'healthy',
            'messages_collected': count,
            'latest_message_time': latest.timestamp.isoformat() if latest else None
        })
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

if __name__ == "__main__":
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=True)