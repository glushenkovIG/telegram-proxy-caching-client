import os
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Create Flask app
app = Flask(__name__)

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize database
db = SQLAlchemy(app)

# Message model
class TelegramMessage(db.Model):
    __tablename__ = 'telegram_messages'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, nullable=False)
    channel_id = db.Column(db.String(100), nullable=False)
    channel_title = db.Column(db.String(200))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_ton_dev = db.Column(db.Boolean, default=False)

# Create tables
try:
    with app.app_context():
        db.create_all()
        print("Database tables created successfully")
except Exception as e:
    print(f"Database initialization error: {str(e)}")
    # Don't fail on startup, just log the error

@app.route('/')
def index():
    try:
        total_count = TelegramMessage.query.count()
        ton_count = TelegramMessage.query.filter_by(is_ton_dev=True).count()
        return f"Server running. Total messages: {total_count} (TON Dev messages: {ton_count})"
    except Exception as e:
        app.logger.error(f"Database error: {str(e)}")
        return f"Database error: {str(e)}", 500

if __name__ == "__main__":
    try:
        # First try port 5000
        app.run(host='0.0.0.0', port=5000, debug=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print("Port 5000 is in use, trying port 8080...")
            # If port 5000 is busy, use 8080
            app.run(host='0.0.0.0', port=8080, debug=False)
        else:
            raise