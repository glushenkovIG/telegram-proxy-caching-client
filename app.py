import os
from datetime import datetime
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

# Create Flask app
app = Flask(__name__)

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize database
db = SQLAlchemy(app)

# Import and register routes
from routes import bp
app.register_blueprint(bp)

# Message model
class TelegramMessage(db.Model):
    __tablename__ = 'telegram_messages'  # Explicitly set table name

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, nullable=False)
    channel_id = db.Column(db.String(100), nullable=False)
    channel_title = db.Column(db.String(200))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_ton_dev = db.Column(db.Boolean, default=False)

# Create tables
with app.app_context():
    # db.drop_all()  # Commented out to preserve existing data
    db.create_all()
    try:
        msg_count = TelegramMessage.query.count()
        print(f"Database connected successfully. Current message count: {msg_count}")
    except Exception as e:
        print(f"Database connection error on startup: {str(e)}")

# Routes are now handled by the blueprint

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)