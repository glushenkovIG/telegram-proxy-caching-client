from datetime import datetime
from app import db

class TelegramMessage(db.Model):
    __tablename__ = 'telegram_messages'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, nullable=False)
    channel_id = db.Column(db.String(255), nullable=False)
    channel_title = db.Column(db.String(255))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime)
    is_ton_dev = db.Column(db.Boolean, default=False)
    is_outgoing = db.Column(db.Boolean, default=False)
    dialog_type = db.Column(db.String(50))
    sender_id = db.Column(db.String(255))
    sender_username = db.Column(db.String(255))