import os
import logging
import socket
from flask import Flask, render_template, request, jsonify
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
        page = request.args.get('page', 1, type=int)
        per_page = 50  # Show 50 messages per page

        # Get total message count
        total_messages = TelegramMessage.query.count()

        # Get paginated messages
        pagination = TelegramMessage.query\
            .order_by(TelegramMessage.timestamp.desc())\
            .paginate(page=page, per_page=per_page)

        logger.info(f"Retrieved {len(pagination.items)} messages from database (page {page})")
        return render_template('index.html', 
                             messages=pagination.items,
                             pagination=pagination,
                             total_messages=total_messages)
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def status():
    try:
        from models import TelegramMessage
        message_count = TelegramMessage.query.count()
        latest_message = TelegramMessage.query\
            .order_by(TelegramMessage.timestamp.desc())\
            .first()

        return jsonify({
            'status': 'healthy',
            'total_messages': message_count,
            'latest_message_time': latest_message.timestamp.isoformat() if latest_message else None
        })
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except socket.error:
            return True

if __name__ == "__main__":
    port = 5000
    retries = 3

    while retries > 0 and is_port_in_use(port):
        logger.warning(f"Port {port} is in use, waiting 5 seconds before retry...")
        import time
        time.sleep(5)
        retries -= 1

    if is_port_in_use(port):
        logger.error(f"Could not bind to port {port} after {3-retries} retries")
        import sys
        sys.exit(1)

    app.run(host="0.0.0.0", port=port, debug=True)